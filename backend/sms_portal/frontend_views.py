# sms_portal/frontend_views.py
from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.template.exceptions import TemplateDoesNotExist
from django.conf import settings
from django.utils import timezone
from django.http import HttpResponseNotFound, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .auth_utils import AuthMixin, get_user_from_request
import json
import logging
from datetime import date, datetime
from calendar import monthrange

logger = logging.getLogger(__name__)

from django.views.generic import TemplateView
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.conf import settings
from django.views import View

from sms.models import (
    SMSUsageStats,
    SMSMessage,
    Template,
    Group,
    SenderID,
    StudentContact,
    SMSRecipient,
    Campaign,
)
from sms.services import MySMSMantraService


def _base_context(request):
    """
    Standard context injected into all frontend templates.
    - API_BASE: prefix for API endpoints (default '/api' because sms.urls is mounted under 'api/')
    - now: current timestamp
    - user, user_role: user object and role (if authenticated)
    """
    api_base = getattr(settings, 'API_BASE', '/api')
    
    # Use our enhanced auth detection
    user, auth_method = get_user_from_request(request)
    user_role = getattr(user, 'role', None) if user else None

    return {
        'API_BASE': api_base,
        'now': timezone.now(),
        'user': user,
        'user_role': user_role,
        'auth_method': auth_method,
    }


class FrontendTemplateView(AuthMixin, TemplateView):
    """
    Base view for rendering frontend templates.
    - If `require_auth = True` on subclass, anonymous users are redirected to the login page.
    - Renders template and catches TemplateDoesNotExist to return a friendly 404 page.
    - Supports both Django session and JWT authentication.
    """
    require_auth = False  # set True on subclasses that must be protected

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # inject base context (api base, user info, etc.)
        context.update(_base_context(self.request))
        return context

    def get(self, request, *args, **kwargs):
        """
        Try to render the template. If the template file is missing, show custom 404.
        This forces template rendering so missing templates don't silently fail later.
        """
        try:
            response = super().get(request, *args, **kwargs)
            response.render()  # force render to catch TemplateDoesNotExist
            return response
        except TemplateDoesNotExist:
            # render a friendly 404 page (using base context)
            ctx = _base_context(request)
            return render(request, '404.html', ctx, status=404)


# -------------------------
# Page views
# -------------------------

# sms/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from datetime import datetime, timedelta
from sms.models import SMSMessage, SMSUsageStats, Template, Group, User

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.shortcuts import render
from sms.models import SMSMessage, SMSUsageStats, Template, Group


@login_required(login_url='/login/')
def DashboardView(request):
    user = request.user

    if user.role == 'admin':
        campaigns = Campaign.objects.prefetch_related('messages__recipient_logs').order_by('-created_at')[:10]
    else:
        campaigns = Campaign.objects.filter(user=user).prefetch_related('messages__recipient_logs').order_by('-created_at')[:10]

    stats = {
        'total_sent': SMSMessage.objects.filter(user=user).count(),
        'total_delivered': SMSMessage.objects.filter(user=user, status='sent').count(),
        'total_failed': SMSMessage.objects.filter(user=user, status='failed').count(),
        'remaining_credits': getattr(getattr(user, "usage_stats", None), "remaining_credits", 0),
        'monthly_stats': get_monthly_stats(SMSMessage.objects.filter(user=user))
    }

    context = {
        'stats': stats,
        'campaigns': campaigns,
        'API_BASE': '/api/',
    }

    return render(request, 'dashboard/dashboard.html', context)


# -----------------------------------------
# Helper: Build monthly stats for chart
# -----------------------------------------
def get_monthly_stats(messages):
    from collections import defaultdict

    stats = defaultdict(lambda: {'sent': 0, 'failed': 0})
    
    for msg in messages:
        # Safely pick sent_at if exists, else created_at
        date_field = msg.sent_at or msg.created_at
        if not date_field:
            continue  # skip if somehow both missing

        year = date_field.year
        month = date_field.month
        label = f"{year}-{month:02d}"

        stats[label]['sent'] += 1
        if msg.status == 'failed':
            stats[label]['failed'] += 1

    # Format for chart
    sorted_labels = sorted(stats.keys())
    return {
        'months': sorted_labels,
        'sent': [stats[k]['sent'] for k in sorted_labels],
        'failed': [stats[k]['failed'] for k in sorted_labels],
    }

from sms.models import SMSMessage, Template, Campaign  # ✅ import Campaign
from django.utils import timezone


class SendSMSView(FrontendTemplateView):
    template_name = 'sms/send.html'
    require_auth = True

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            template_id = data.get('template_id')
            recipients = data.get('recipients', [])
            message = data.get('message', '')
            sender_id = data.get('sender_id', 'BOMBYS')
            campaign_id = data.get('campaign_id')

            if not recipients:
                return JsonResponse({'success': False, 'error': 'No recipients provided'}, status=400)

            # 🧩 Find or create campaign
            campaign = None
            if campaign_id and str(campaign_id).isdigit():
                try:
                    campaign = Campaign.objects.get(id=int(campaign_id), user=request.user)
                except Campaign.DoesNotExist:
                    pass

            if not campaign:
                campaign = Campaign.objects.create(
                    user=request.user,
                    title=f"Campaign {timezone.now().strftime('%d-%b %H:%M')}",
                    status="active"
                )

            # 📨 Create master SMSMessage record
            sms_message = SMSMessage.objects.create(
                user=request.user,
                campaign=campaign,
                message_text=message,
                recipients=recipients,
                total_recipients=len(recipients),
                status='pending'
            )

            logger.info(f"Sending SMS to {len(recipients)} recipients under campaign {campaign.title}")

            # 🔹 Send SMS via MySMSMantra API
            service = MySMSMantraService(user=request.user)
            result = service.send_sms_sync(
                sms_message_id=sms_message.id,
                message_text=message,
                recipients_list=recipients,
                sender_id=sender_id
            )

            if not result.get("success"):
                sms_message.status = "failed"
                sms_message.save()
                return JsonResponse({'success': False, 'error': result.get('error')}, status=500)

            # 🧾 Parse API response and save recipient details
            api_data = result.get("api_response", {}).get("Data", [])
            sent_count = 0
            failed_count = 0

            for entry in api_data:
                phone = entry.get("MobileNumber")
                api_msg_id = entry.get("MessageId")
                error_code = entry.get("MessageErrorCode")
                status = "sent" if error_code == 0 else "failed"

                # ✅ Use api_message_id instead of message_id (UUID-safe)
                SMSRecipient.objects.create(
                    message=sms_message,
                    phone_number=phone,
                    api_message_id=api_msg_id,
                    status=status,
                    submit_time=timezone.now() if status == "sent" else None,
                    error_description=entry.get("MessageErrorDescription")
                )

                if status == "sent":
                    sent_count += 1
                else:
                    failed_count += 1

            # ✅ Update SMSMessage
            sms_message.status = "sent" if sent_count > 0 else "failed"
            sms_message.sent_at = timezone.now()
            sms_message.successful_deliveries = sent_count
            sms_message.failed_deliveries = failed_count
            sms_message.save()

            # ✅ Auto-calculate Campaign statistics using update_stats()
            campaign.update_stats()
            campaign.status = "completed" if campaign.total_failed == 0 else "partial"
            campaign.save()

            logger.info(f"✅ SMS campaign '{campaign.title}' results → Sent={sent_count}, Failed={failed_count}")

            return JsonResponse({
                'success': True,
                'campaign_id': campaign.id,
                'message_id': sms_message.id,
                'delivered': sent_count,
                'failed': failed_count,
                'recipients': len(api_data),
                'api_response': api_data,
            })

        except Exception as e:
            logger.exception("Error in SendSMSView")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class MessageHistoryView(FrontendTemplateView):
    template_name = 'sms/message_history.html'
    require_auth = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Get campaigns with messages and recipient logs (same as dashboard)
        if user.role == 'admin':
            campaigns = Campaign.objects.prefetch_related('messages__recipient_logs').order_by('-created_at')
        else:
            campaigns = Campaign.objects.filter(user=user).prefetch_related('messages__recipient_logs').order_by('-created_at')

        # Calculate statistics
        total_sent = sum(camp.total_sent or 0 for camp in campaigns)
        total_delivered = sum(camp.total_delivered or 0 for camp in campaigns)
        total_failed = sum(camp.total_failed or 0 for camp in campaigns)
        success_rate = round((total_delivered / total_sent * 100), 1) if total_sent > 0 else 0

        context['campaigns'] = campaigns
        context['stats'] = {
            'total_sent': total_sent,
            'total_delivered': total_delivered,
            'total_failed': total_failed,
            'success_rate': success_rate,
        }
        return context


class MessageDetailsView(FrontendTemplateView):
    template_name = 'sms/message_details.html'
    require_auth = True


class TemplatesView(FrontendTemplateView):
    template_name = 'templates/templates.html'
    require_auth = True


@login_required(login_url='/login/')
def settings_view(request):
    """Settings page for authenticated users"""
    context = _base_context(request)
    return render(request, 'settings/settings.html', context)


@login_required(login_url='/login/')
def sender_ids_view(request):
    """Sender IDs page for authenticated users"""
    context = _base_context(request)
    return render(request, 'sender_ids/sender_ids.html', context)


from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model

User = get_user_model()

@login_required(login_url='/login/')
def manage_users(request):
    if request.user.role != 'admin':
        return redirect('/dashboard/')  # Non-admins shouldn't manage users
    
    users = User.objects.all().order_by('-last_login')
    stats = {
        'total': users.count(),
        'active': users.filter(is_active=True).count(),
        'admins': users.filter(role='admin').count(),
        'teachers': users.filter(role='teacher').count(),
    }
    
    context = {
        'users': users,
        'stats': stats,
    }
    return render(request, 'users/users.html', context)



class UserProfileView(FrontendTemplateView):
    template_name = 'users/profile.html'
    require_auth = True


@login_required(login_url='/login/')
def groups_management_view(request):
    """Groups management page for authenticated users"""
    context = _base_context(request)
    return render(request, 'groups/groups.html', context)


@login_required(login_url='/login/')
def template_approvals_view(request):
    """Template approvals page for admin users only"""
    # Only admin users should access template approvals
    if request.user.role != 'admin':
        return redirect('/dashboard/')
    
    context = _base_context(request)
    return render(request, 'approvals/approvals.html', context)

@login_required
def activity_page(request):
    # Placeholder data for now
    activities = [
        {'action': 'Sent SMS', 'details': 'Message sent to Class 10A', 'timestamp': timezone.now(), 'status': 'success'},
        {'action': 'Created Template', 'details': 'New template "Exam Alert" added', 'timestamp': timezone.now(), 'status': 'success'},
    ]
    return render(request, 'dashboard/activity.html', {'activities': activities})


from django.contrib.auth import authenticate, login
from django.contrib import messages

class LoginView(View):
    template_name = 'auth/login.html'

    def get(self, request, *args, **kwargs):
        # If user is already logged in → redirect to dashboard
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        email = request.POST.get('email') or request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=email, password=password)
        if user is not None:
            # Log the user in (creates Django session cookie)
            login(request, user)
            next_url = request.GET.get('next', '/dashboard/')
            return redirect(next_url)
        else:
            messages.error(request, "Invalid email or password.")
            return render(request, self.template_name, {'error': True})

# frontend_views.py
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib import messages

def LogoutView(request):
    if request.method == 'POST':
        logout(request)
        messages.success(request, "You have been logged out successfully.")
        return redirect('/login/')
    else:
        # Optional: handle accidental GET requests
        return redirect('/dashboard/')


class RegisterView(FrontendTemplateView):
    template_name = 'auth/register.html'


@login_required(login_url='/login/')
def reports_view(request):
    """Reports page for authenticated users (admins and teachers)"""
    # Both admin and teacher users can access reports
    if request.user.role not in ['admin', 'teacher']:
        return redirect('/dashboard/')
    
    context = _base_context(request)
    return render(request, 'reports/reports.html', context)


class ContactsView(FrontendTemplateView):
    template_name = 'contacts/contacts.html'
    require_auth = True


class HomeView(FrontendTemplateView):
    template_name = 'index.html'


# -------------------------
# Sidebar partial and helpers
# -------------------------
def sidebar_view(request):
    """
    Return the sidebar partial HTML. This is fetched dynamically by the front-end (common.js).
    Provide the user's role so the sidebar template can render role-specific links.
    """
    ctx = _base_context(request)
    ctx['role'] = ctx.get('user_role') or 'teacher'
    # Optionally, you can compute small counts here and pass (groups_count, templates_count, etc.)
    return render(request, 'includes/sidebar.html', ctx)


# -------------------------
# Custom 404 view
# -------------------------
def custom_404_view(request, exception=None):
    ctx = _base_context(request)
    return HttpResponseNotFound(render(request, '404.html', ctx).content)
