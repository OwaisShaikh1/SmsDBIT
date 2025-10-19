from django.urls import path
from . import frontend_views

app_name = 'frontend'

urlpatterns = [
    # Home/Dashboard
    path('', frontend_views.DashboardView.as_view(), name='home'),
    path('dashboard/', frontend_views.DashboardView.as_view(), name='dashboard'),
    path('dashboard/page/', frontend_views.DashboardView.as_view(), name='dashboard_page'),  # Alias for compatibility
    
    # SMS Operations
    path('send/', frontend_views.SendSMSView.as_view(), name='send_sms'),
    path('history/', frontend_views.MessageHistoryView.as_view(), name='message_history'),
    path('message-details/', frontend_views.MessageDetailsView.as_view(), name='message_details'),
    
    # Templates
    path('templates/', frontend_views.TemplatesView.as_view(), name='templates'),
    
    # Settings
    path('settings/', frontend_views.SettingsView.as_view(), name='settings'),
    path('sender-ids/', frontend_views.SenderIDsView.as_view(), name='sender_ids'),
    
    # User Management
    path('users/', frontend_views.UsersManagementView.as_view(), name='users_management'),
    path('profile/', frontend_views.UserProfileView.as_view(), name='user_profile'),
    path('activity/', frontend_views.ActivityLogView.as_view(), name='activity_log'),
    
    # Groups Management
    path('groups/', frontend_views.GroupsManagementView.as_view(), name='groups_management'),
    
    # Template Approvals
    path('approvals/', frontend_views.TemplateApprovalsView.as_view(), name='template_approvals'),
    
    # Authentication
    path('login/', frontend_views.LoginView.as_view(), name='login'),
    path('register/', frontend_views.RegisterView.as_view(), name='register'),
    
    # Reports
    path('reports/', frontend_views.ReportsView.as_view(), name='reports'),

    # Groups
    path('groups/', frontend_views.GroupView.as_view(), name='groups'),

    # Dynamic components
    path('sidebar/', frontend_views.sidebar_view, name='sidebar'),
    
    # Test 404 page (for development)
    path('test-404/', frontend_views.custom_404_view, name='test_404'),
    path('404/', frontend_views.custom_404_view, name='custom_404'),
]