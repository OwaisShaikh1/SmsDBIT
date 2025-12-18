"""Frontend URL Configuration for SMS Portal
All endpoints render HTML templates.
API endpoints (JSON) are in sms/urls.py
"""

from django.urls import path
from . import frontend_views

app_name = 'frontend'

urlpatterns = [
    # =========================================================================
    # AUTHENTICATION
    # =========================================================================
    path('login/', frontend_views.LoginView.as_view(), name='login'),
    path('logout/', frontend_views.LogoutView, name='logout'),
    path('register/', frontend_views.RegisterView.as_view(), name='register'),

    # =========================================================================
    # DASHBOARD & HOME
    # =========================================================================
    path('', frontend_views.DashboardView, name='home'),
    path('dashboard/', frontend_views.DashboardView, name='dashboard'),
    path('activity/', frontend_views.activity_page, name='activity_log'),

    # =========================================================================
    # SMS OPERATIONS
    # =========================================================================
    path('send/', frontend_views.SendSMSView.as_view(), name='send_sms'),
    path('history/', frontend_views.MessageHistoryView.as_view(), name='message_history'),
    path('message/<int:pk>/', frontend_views.MessageDetailsView.as_view(), name='message_details'),

    # =========================================================================
    # TEMPLATES
    # =========================================================================
    path('templates/', frontend_views.TemplatesView.as_view(), name='templates'),
    path('approvals/', frontend_views.template_approvals_view, name='template_approvals'),

    # =========================================================================
    # CONTACTS & GROUPS
    # =========================================================================
    path('contacts/', frontend_views.ContactsView.as_view(), name='contacts'),
    path('groups/', frontend_views.groups_management_view, name='groups_management'),

    # =========================================================================
    # USER MANAGEMENT
    # =========================================================================
    path('users/', frontend_views.manage_users, name='users_management'),
    path('profile/', frontend_views.UserProfileView.as_view(), name='user_profile'),

    # =========================================================================
    # SETTINGS & CONFIGURATION
    # =========================================================================
    path('settings/', frontend_views.settings_view, name='settings'),
    path('sender-ids/', frontend_views.sender_ids_view, name='sender_ids'),

    # =========================================================================
    # REPORTS
    # =========================================================================
    path('reports/', frontend_views.reports_view, name='reports'),

    # =========================================================================
    # PARTIALS & COMPONENTS
    # =========================================================================
    path('sidebar/', frontend_views.sidebar_view, name='sidebar'),
    path('404/', frontend_views.custom_404_view, name='custom_404'),
]
