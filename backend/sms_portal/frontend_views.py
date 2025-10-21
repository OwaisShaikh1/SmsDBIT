# sms_portal/frontend_views.py
from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.template.exceptions import TemplateDoesNotExist
from django.conf import settings
from django.utils import timezone
from django.http import HttpResponseNotFound
from .auth_utils import AuthMixin, get_user_from_request
import json
from datetime import date, datetime
from calendar import monthrange

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
)


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

    # --------------- Admin Stats ---------------
    if user.role == 'admin':
        all_messages = SMSMessage.objects.all()
        all_stats = SMSUsageStats.objects.aggregate(
            total_sent=Sum('total_sent'),
            total_delivered=Sum('total_delivered'),
            total_failed=Sum('total_failed'),
            total_cost=Sum('total_cost'),
            remaining_credits=Sum('remaining_credits')
        )

        success_rate = 0
        if all_stats['total_sent']:
            success_rate = round((all_stats['total_delivered'] / all_stats['total_sent']) * 100, 2)

        pending_templates = Template.objects.filter(status='pending').count()
        recent_messages = all_messages.order_by('-created_at')[:10]

        stats = {
            **all_stats,
            'success_rate': success_rate,
            'monthly_stats': get_monthly_stats(all_messages)
        }

    # --------------- Teacher Stats ---------------
    else:
        user_stats, _ = SMSUsageStats.objects.get_or_create(user=user)
        groups_count = Group.objects.filter(teacher=user).count()
        templates_count = Template.objects.filter(user=user, status='approved').count()
        recent_messages = SMSMessage.objects.filter(user=user).order_by('-created_at')[:10]

        stats = {
            'total_sent': user_stats.total_sent,
            'total_delivered': user_stats.total_delivered,
            'total_failed': user_stats.total_failed,
            'remaining_credits': user_stats.remaining_credits,
            'monthly_stats': get_monthly_stats(SMSMessage.objects.filter(user=user))
        }

        pending_templates = None

    # --------------- Message Context ---------------
    recent_messages_context = [
        {
            #'sender_id_name': msg.sender_id.name if msg.sender_id else '-',
            'message_text': msg.message_text,
            'total_recipients': msg.total_recipients or len(msg.recipients.split(',')),
            'status': msg.status,
            'sent_at': msg.sent_at,
            'created_at': msg.created_at,
        }
        for msg in recent_messages
    ]

    context = {
        'stats': stats,
        'pending_templates': pending_templates,
        'groups_count': locals().get('groups_count', 0),
        'templates_count': locals().get('templates_count', 0),
        'recent_messages': recent_messages_context,
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

class SendSMSView(FrontendTemplateView):
    template_name = 'sms/send.html'
    require_auth = True


class MessageHistoryView(FrontendTemplateView):
    template_name = 'sms/message_history.html'
    require_auth = True


class MessageDetailsView(FrontendTemplateView):
    template_name = 'sms/message_details.html'
    require_auth = True


class TemplatesView(FrontendTemplateView):
    template_name = 'templates/templates.html'
    require_auth = True


class SettingsView(FrontendTemplateView):
    template_name = 'settings/settings.html'
    require_auth = True


class SenderIDsView(FrontendTemplateView):
    template_name = 'sender_ids/sender_ids.html'
    require_auth = True


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


class GroupsManagementView(FrontendTemplateView):
    template_name = 'groups/groups.html'
    require_auth = True


class TemplateApprovalsView(FrontendTemplateView):
    template_name = 'approvals/approvals.html'
    require_auth = True
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Only admin users should access template approvals
        user = context.get('user')
        if user and getattr(user, 'role', None) != 'admin':
            # Redirect non-admin users to dashboard
            from django.shortcuts import redirect
            return redirect('/dashboard/')
        return context

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

        user = authenticate(request, email=email, password=password)
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


class ReportsView(FrontendTemplateView):
    template_name = 'reports/reports.html'
    require_auth = True


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
