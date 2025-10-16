from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

app_name = 'sms'

urlpatterns = [
    # Authentication
    path('auth/register/', views.UserRegistrationView.as_view(), name='register'),
    path('auth/login/', views.UserLoginView.as_view(), name='login'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/profile/', views.UserProfileView.as_view(), name='profile'),
    
    # SMS Operations
    path('send-sms/', views.SendSMSView.as_view(), name='send_sms'),
    path('bulk-send/', views.bulk_send_sms, name='bulk_send_sms'),
    path('history/', views.SMSHistoryView.as_view(), name='sms_history'),
    path('history/<int:pk>/', views.SMSMessageDetailView.as_view(), name='sms_detail'),
    
    # Templates
    path('templates/', views.TemplateListCreateView.as_view(), name='template_list'),
    path('templates/<int:pk>/', views.TemplateDetailView.as_view(), name='template_detail'),
    
    # Sender IDs
    path('senders/', views.SenderIDListCreateView.as_view(), name='sender_list'),
    path('senders/<int:pk>/', views.SenderIDDetailView.as_view(), name='sender_detail'),
    
    # API Credentials
    path('credentials/', views.APICredentialsView.as_view(), name='api_credentials'),
    
    # Dashboard
    path('dashboard/', views.DashboardStatsView.as_view(), name='dashboard_stats'),
]