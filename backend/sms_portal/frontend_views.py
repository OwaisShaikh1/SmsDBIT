"""
Frontend Views for SMS Portal
Handles all HTML template rendering for the SMS management system.
All API logic should be in sms/views.py
"""

import logging
from datetime import datetime
from collections import defaultdict
import re

from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.template.exceptions import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Sum, Count, Q
from django.http import HttpResponseNotFound, HttpResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.vary import vary_on_cookie

from .auth_utils import AuthMixin, get_user_from_request
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
from sms.services import AdminAnalyticsService

User = get_user_model()
logger = logging.getLogger(__name__)


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
@ensure_csrf_cookie
def DashboardView(request):
    user = request.user

    if user.role == 'admin':
        # Admin sees all campaigns and system-wide stats
        campaigns = Campaign.objects.prefetch_related('messages__recipient_logs').order_by('-created_at')[:10]
        messages_qs = SMSMessage.objects.all()
        groups_count = Group.objects.count()
        templates_count = Template.objects.count()
        pending_templates = Template.objects.filter(status='pending').count()
    else:
        # Teachers see only their own data + universal groups
        campaigns = Campaign.objects.filter(user=user).prefetch_related('messages__recipient_logs').order_by('-created_at')[:10]
        messages_qs = SMSMessage.objects.filter(user=user)
        groups_count = Group.objects.filter(Q(is_universal=True) | Q(teacher=user)).count()
        templates_count = Template.objects.filter(Q(status='approved') | Q(user=user)).count()
        pending_templates = Template.objects.filter(user=user, status='pending').count()

    # Calculate stats based on role-filtered queryset
    # Use Sum of successful_deliveries and failed_deliveries fields, not status filtering
    from django.db.models import Sum
    totals = messages_qs.aggregate(
        total_delivered=Sum('successful_deliveries'),
        total_failed=Sum('failed_deliveries')
    )
    total_sent = messages_qs.count()
    total_delivered = totals['total_delivered'] or 0
    total_failed = totals['total_failed'] or 0
    success_rate = round((total_delivered / (total_delivered + total_failed) * 100), 1) if (total_delivered + total_failed) > 0 else 0

    stats = {
        'total_sent': total_sent,
        'total_delivered': total_delivered,
        'total_failed': total_failed,
        'success_rate': success_rate,
        'remaining_credits': getattr(getattr(user, "usage_stats", None), "remaining_credits", 0),
        'monthly_stats': get_monthly_stats(messages_qs)
    }

    context = {
        'stats': stats,
        'campaigns': campaigns,
        'API_BASE': '/api/',
        'groups_count': groups_count,
        'templates_count': templates_count,
        'pending_templates': pending_templates,
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

from sms.models import SMSMessage, Template, Campaign
from django.utils import timezone


class SendSMSView(FrontendTemplateView):
    """Frontend view for SMS sending page - renders template only.
    
    All SMS sending logic is handled by the API endpoint in sms/views.py
    """
    template_name = 'sms/send.html'
    require_auth = True


class MessageHistoryView(FrontendTemplateView):
    template_name = 'sms/message_history.html'
    require_auth = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Get campaigns with messages and recipient logs (same as dashboard)
        # Order messages by -created_at within each campaign
        from django.db.models import Prefetch
        from sms.models import SMSMessage
        
        messages_prefetch = Prefetch(
            'messages',
            queryset=SMSMessage.objects.order_by('-created_at')
        )
        
        if user.role == 'admin':
            campaigns = Campaign.objects.prefetch_related(
                messages_prefetch, 
                'messages__recipient_logs'
            ).order_by('-created_at')
        else:
            campaigns = Campaign.objects.filter(user=user).prefetch_related(
                messages_prefetch,
                'messages__recipient_logs'
            ).order_by('-created_at')

        # Calculate statistics from SMSMessage fields (same source as dashboard)
        from django.db.models import Sum
        if user.role == 'admin':
            messages_qs = SMSMessage.objects.all()
        else:
            messages_qs = SMSMessage.objects.filter(user=user)
        
        totals = messages_qs.aggregate(
            total_delivered=Sum('successful_deliveries'),
            total_failed=Sum('failed_deliveries')
        )
        total_delivered = totals['total_delivered'] or 0
        total_failed = totals['total_failed'] or 0
        total_sent = total_delivered + total_failed
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
    # Admin-only activity page. Use AdminAnalyticsService for aggregates and logs.
    user = request.user
    if not getattr(user, 'role', None) == 'admin':
        return redirect('/dashboard/')

    service = AdminAnalyticsService(user=request.user)
    admin_totals = service.get_admin_totals()
    activities = service.get_activity_logs(start=0, length=25)

    context = _base_context(request)
    context.update({'admin_totals': admin_totals, 'activities': activities})
    return render(request, 'dashboard/activity.html', context)


class LoginView(View):
    template_name = 'auth/login.html'

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        email = request.POST.get('email') or request.POST.get('username')
        password = request.POST.get('password')

        # Single generic error message
        invalid_msg = "Invalid email or password."

        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, invalid_msg)
            return render(request, self.template_name, {'error': True})

        if not user_obj.is_active:
            messages.error(
                request,
                "Your account is disabled. Please contact the administrator."
            )
            return render(request, self.template_name, {'error': True})

        user = authenticate(request, username=email, password=password)
        if user:
            login(request, user)
            return redirect(request.GET.get('next', '/dashboard/'))

        messages.error(request, invalid_msg)
        return render(request, self.template_name, {'error': True})


def LogoutView(request):
    if request.method == 'POST':
        # Capture session key and user id to invalidate cached sidebar
        session_key = getattr(request.session, 'session_key', None)
        user_id = getattr(request.user, 'id', None)
        logout(request)
        # Invalidate both session-key keyed and user-id keyed caches (fallback)
        try:
            if session_key:
                cache.delete(f"sidebar_html_session_{session_key}")
        except Exception:
            pass
        try:
            if user_id:
                cache.delete(f"sidebar_html_user_{user_id}")
        except Exception:
            pass
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
# Sidebar partial
# -------------------------
@ensure_csrf_cookie  # Ensure CSRF cookie is set for forms in sidebar
@vary_on_cookie      # Different cache per user session
def sidebar_view(request):
    """Return sidebar partial HTML, caching it server-side per-user for performance.

    The cached HTML is keyed by user id so each authenticated user gets their
    correct links. We still set `no-store` response headers to prevent
    intermediate proxies or clients caching user-specific HTML.
    """
    user = request.user

    # Prefer session-key-based cache so cached fragment is tied to the session.
    session_key = getattr(request.session, 'session_key', None)
    cache_key = None
    if session_key:
        cache_key = f"sidebar_html_session_{session_key}"
    else:
        cache_key = f"sidebar_html_user_{getattr(user, 'id', 'anon')}"

    html = None
    try:
        html = cache.get(cache_key)
    except Exception:
        html = None

    if not html:
        context = {"role": getattr(user, 'role', 'teacher'), 'request': request}
        html = render_to_string('includes/sidebar.html', context=context, request=request)

        # Determine TTL: use session expiry age if available, otherwise default to 1 hour.
        try:
            ttl = request.session.get_expiry_age()
            # Sanity bounds
            if not isinstance(ttl, int) or ttl <= 0:
                ttl = 60 * 60
        except Exception:
            ttl = 60 * 60

        try:
            cache.set(cache_key, html, ttl)
        except Exception:
            pass

    response = HttpResponse(html)
    # Prevent intermediate caches from storing per-user HTML
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


# -------------------------
# Custom 404 view
# -------------------------
def custom_404_view(request, exception=None):
    ctx = _base_context(request)
    return HttpResponseNotFound(render(request, '404.html', ctx).content)


