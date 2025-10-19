# sms_portal/frontend_views.py
from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.template.exceptions import TemplateDoesNotExist
from django.conf import settings
from django.utils import timezone
from django.http import HttpResponseNotFound
from .auth_utils import AuthMixin, get_user_from_request


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

class DashboardView(FrontendTemplateView):
    template_name = 'dashboard/dashboard.html'
    require_auth = True  # Dashboard requires authentication
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Import dashboard data builder from SMS app
        try:
            from sms.views import build_dashboard_data
            from sms.models import Template
            
            user = self.request.user
            stats = build_dashboard_data(user)
            
            context['stats'] = stats
            context['recent_messages'] = stats.get('recent_messages', [])
            
            if getattr(user, 'role', None) == 'admin':
                context['pending_templates'] = Template.objects.filter(status='pending').count()
            else:
                context['templates_count'] = stats.get('templates_count', 0)
                context['groups_count'] = stats.get('groups_count', 0)
                
        except Exception as e:
            # Fallback with empty stats if there's an error
            logger = __import__('logging').getLogger(__name__)
            logger.error(f"Error building dashboard data: {e}")
            context['stats'] = {
                'total_sent': 0,
                'total_delivered': 0,
                'total_failed': 0,
                'success_rate': 0.0,
                'remaining_credits': 0,
                'monthly_stats': {'months': [], 'sent': [], 'failed': []}
            }
            context['recent_messages'] = []
            context['templates_count'] = 0
            context['groups_count'] = 0
            context['pending_templates'] = 0
            
        return context


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


class UsersManagementView(FrontendTemplateView):
    template_name = 'users/users.html'
    require_auth = True
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Only admin users should access user management
        user = context.get('user')
        if user and getattr(user, 'role', None) != 'admin':
            # Redirect non-admin users to dashboard
            from django.shortcuts import redirect
            return redirect('/dashboard/')
        return context


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


class ActivityLogView(FrontendTemplateView):
    template_name = 'activity/activity.html'
    require_auth = True


class LoginView(FrontendTemplateView):
    template_name = 'auth/login.html'

    def dispatch(self, request, *args, **kwargs):
        # If user is already authenticated, redirect to dashboard
        user, auth_method = get_user_from_request(request)
        if user:
            return redirect('/dashboard/')
        return super().dispatch(request, *args, **kwargs)


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
