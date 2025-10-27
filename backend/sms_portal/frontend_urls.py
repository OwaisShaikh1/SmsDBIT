# sms_portal/frontend_urls.py
from django.urls import path
from . import frontend_views

app_name = 'frontend'

urlpatterns = [
    # Dashboard & Home
    path('login/', frontend_views.LoginView.as_view(), name='login'),
    path('dashboard/', frontend_views.DashboardView, name='dashboard'),
    path('', frontend_views.DashboardView, name='home'),
    path('logout/', frontend_views.LogoutView, name='logout'),


    # SMS Operations
    path('send/', frontend_views.SendSMSView.as_view(), name='send_sms'),
    path('history/', frontend_views.MessageHistoryView.as_view(), name='message_history'),
    path('message/<int:pk>/', frontend_views.MessageDetailsView.as_view(), name='message_details'),

    # Templates
    path('templates/', frontend_views.TemplatesView.as_view(), name='templates'),
    path('approvals/', frontend_views.template_approvals_view, name='template_approvals'),

    # Sender IDs / Settings
    path('sender-ids/', frontend_views.SenderIDsView.as_view(), name='sender_ids'),
    path('settings/', frontend_views.SettingsView.as_view(), name='settings'),

    # Users
    path('users/', frontend_views.manage_users, name='users_management'),
    path('profile/', frontend_views.UserProfileView.as_view(), name='user_profile'),
    path('activity/', frontend_views.activity_page, name='activity_log'),

    # Groups / Contacts
    path('groups/', frontend_views.GroupsManagementView.as_view(), name='groups_management'),
    path('contacts/', frontend_views.ContactsView.as_view(), name='contacts'),

    # Reports
    path('reports/', frontend_views.reports_view, name='reports'),

    # Auth
    path('login/', frontend_views.LoginView.as_view(), name='login'),
    path('register/', frontend_views.RegisterView.as_view(), name='register'),

    # Partials
    path('sidebar/', frontend_views.sidebar_view, name='sidebar'),
    path('404/', frontend_views.custom_404_view, name='custom_404'),
]
