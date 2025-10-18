from django.shortcuts import render
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.http import JsonResponse, Http404
from django.template.exceptions import TemplateDoesNotExist


class FrontendTemplateView(TemplateView):
    """Base view for serving frontend HTML templates with automatic 404 handling"""
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add any common context data here
        return context
    
    def get(self, request, *args, **kwargs):
        """Override to catch missing templates and show custom 404"""
        try:
            response = super().get(request, *args, **kwargs)
            # Force render to catch template errors
            response.render()
            return response
        except TemplateDoesNotExist:
            # If template doesn't exist, render our custom 404 page
            return render(request, '404.html', status=404)


# Dashboard Views
class DashboardView(FrontendTemplateView):
    template_name = 'dashboard/dashboard.html'


# SMS Views
class SendSMSView(FrontendTemplateView):
    template_name = 'sms/send.html'


class MessageHistoryView(FrontendTemplateView):
    template_name = 'sms/message_history.html'


class MessageDetailsView(FrontendTemplateView):
    template_name = 'sms/message_details.html'


# Template Views
class TemplatesView(FrontendTemplateView):
    template_name = 'templates/templates.html'


# Settings Views
class SettingsView(FrontendTemplateView):
    template_name = 'settings/settings.html'  # This template doesn't exist, will trigger 404


class SenderIDsView(FrontendTemplateView):
    template_name = 'templates/sender_ids.html'


# User Views
class UserProfileView(FrontendTemplateView):
    template_name = 'users/profile.html'


class ActivityLogView(FrontendTemplateView):
    template_name = 'users/activity.html'


# Auth Views
class LoginView(FrontendTemplateView):
    template_name = 'auth/login.html'


class RegisterView(FrontendTemplateView):
    template_name = 'auth/register.html'


# Reports Views
class ReportsView(FrontendTemplateView):
    template_name = 'reports/reports.html'  # This doesn't exist, will trigger 404


# Contacts Views
class ContactsView(FrontendTemplateView):
    template_name = 'contacts/contacts.html'  # This doesn't exist, will trigger 404


# Home/Index View
class HomeView(FrontendTemplateView):
    template_name = 'index.html'


# Sidebar view for dynamic loading
def sidebar_view(request):
    """Return sidebar HTML for dynamic loading"""
    return render(request, 'includes/sidebar.html')


# Custom 404 view
def custom_404_view(request, exception=None):
    """Custom 404 page with sidebar - works even in debug mode"""
    return render(request, '404.html', status=404)