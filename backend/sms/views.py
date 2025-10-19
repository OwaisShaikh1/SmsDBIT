from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import datetime, timedelta
import asyncio
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.conf import settings
import logging

from .models import (
    User, SMSMessage, SenderID, Template, APICredentials, SMSUsageStats,
    Group, Contact
)
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer, UserSerializer,
    SMSMessageSerializer, SenderIDSerializer, TemplateSerializer,
    APICredentialsSerializer, SendSMSSerializer, SMSUsageStatsSerializer,
    DashboardStatsSerializer
)
from .services import send_sms_message

logger = logging.getLogger(__name__)


def build_dashboard_data(user):
    """
    Helper that builds the dashboard payload for either admin (global)
    or teacher (per-user) and returns a plain dict.
    """
    # Admin dashboard (aggregate across system)
    if getattr(user, "role", None) == 'admin':
        # Aggregate over SMSMessage and SMSUsageStats
        total_sent = SMSMessage.objects.aggregate(total=Sum('total_recipients'))['total'] or 0
        total_delivered = SMSMessage.objects.filter(status='delivered').aggregate(total=Sum('successful_deliveries'))['total'] or 0
        total_failed = SMSMessage.objects.filter(status='failed').aggregate(total=Sum('failed_deliveries'))['total'] or 0

        # remaining credits across system (may be per-user stored)
        remaining_credits = SMSUsageStats.objects.aggregate(sum_credits=Sum('remaining_credits'))['sum_credits'] or 0

        total_attempts = (total_delivered + total_failed)
        success_rate = (total_delivered / total_attempts * 100) if total_attempts > 0 else 0

        # recent messages (global)
        recent_qs = SMSMessage.objects.all().order_by('-created_at')[:10]
        recent_messages = SMSMessageSerializer(recent_qs, many=True).data

        monthly_stats = get_monthly_stats_admin()

        data = {
            'total_sent': int(total_sent or 0),
            'total_delivered': int(total_delivered or 0),
            'total_failed': int(total_failed or 0),
            'success_rate': round(success_rate, 2),
            'recent_messages': recent_messages,
            'monthly_stats': monthly_stats,
            'remaining_credits': float(remaining_credits or 0),
        }
        return data

    # Teacher (or default) dashboard — per-user
    usage_stats, created = SMSUsageStats.objects.get_or_create(
        user=user,
        defaults={
            'total_sent': 0,
            'total_delivered': 0,
            'total_failed': 0,
            'total_cost': 0,
            'remaining_credits': 0
        }
    )

    total_attempts = usage_stats.total_delivered + usage_stats.total_failed
    success_rate = (usage_stats.total_delivered / total_attempts * 100) if total_attempts > 0 else 0
    recent_qs = SMSMessage.objects.filter(user=user).order_by('-created_at')[:5]
    recent_messages = SMSMessageSerializer(recent_qs, many=True).data
    monthly_stats = get_monthly_stats_user(user)

    # optional counts
    templates_count = Template.objects.filter(user=user, is_active=True).count()
    groups_count = Group.objects.filter(created_by=user).count()

    data = {
        'total_sent': int(usage_stats.total_sent or 0),
        'total_delivered': int(usage_stats.total_delivered or 0),
        'total_failed': int(usage_stats.total_failed or 0),
        'success_rate': round(success_rate, 2),
        'recent_messages': recent_messages,
        'monthly_stats': monthly_stats,
        'remaining_credits': float(usage_stats.remaining_credits or 0),
        'templates_count': templates_count,
        'groups_count': groups_count
    }
    return data


def get_monthly_stats_admin():
    """Get monthly SMS statistics for the last 6 months (global)."""
    now = timezone.now()
    six_months_ago = now - timedelta(days=180)

    monthly_data = (
        SMSMessage.objects
        .filter(created_at__gte=six_months_ago)
        .extra(select={'month': "strftime('%%Y-%%m', created_at)"})
        .values('month')
        .annotate(
            total=Count('id'),
            sent=Count('id', filter=Q(status='sent')),
            failed=Count('id', filter=Q(status='failed'))
        )
        .order_by('month')
    )

    months = []
    sent_counts = []
    failed_counts = []

    for d in monthly_data:
        months.append(d.get('month'))
        sent_counts.append(d.get('sent', 0))
        failed_counts.append(d.get('failed', 0))

    return {'months': months, 'sent': sent_counts, 'failed': failed_counts}


def get_monthly_stats_user(user):
    """Get monthly SMS statistics for a single user (last 6 months)."""
    now = timezone.now()
    six_months_ago = now - timedelta(days=180)

    monthly_data = (
        SMSMessage.objects
        .filter(user=user, created_at__gte=six_months_ago)
        .extra(select={'month': "strftime('%%Y-%%m', created_at)"})
        .values('month')
        .annotate(
            total=Count('id'),
            sent=Count('id', filter=Q(status='sent')),
            failed=Count('id', filter=Q(status='failed'))
        )
        .order_by('month')
    )

    months = []
    sent_counts = []
    failed_counts = []

    for d in monthly_data:
        months.append(d.get('month'))
        sent_counts.append(d.get('sent', 0))
        failed_counts.append(d.get('failed', 0))

    return {'months': months, 'sent': sent_counts, 'failed': failed_counts}


class UserRegistrationView(generics.CreateAPIView):
    """User registration endpoint"""
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()

            # Create usage stats for new user
            SMSUsageStats.objects.create(user=user)

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                'message': 'User registered successfully',
                'user': UserSerializer(user).data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Registration error: {e}")
            
            # Handle specific database errors
            if 'UNIQUE constraint failed' in str(e) or 'already exists' in str(e).lower():
                return Response({
                    'error': 'Registration failed',
                    'message': 'A user with this email already exists',
                    'code': 'DUPLICATE_EMAIL'
                }, status=status.HTTP_400_BAD_REQUEST)
            elif 'database' in str(e).lower():
                return Response({
                    'error': 'Registration failed',
                    'message': 'Database error occurred. Please try again.',
                    'code': 'DATABASE_ERROR'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                # Generic error response 
                return Response({
                    'error': 'Registration failed',
                    'message': 'An unexpected error occurred. Please try again.',
                    'code': 'UNKNOWN_ERROR',
                    'details': str(e) if settings.DEBUG else None
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserLoginView(APIView):
    """User login endpoint"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            serializer = UserLoginSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)

            return Response({
                'message': 'Login successful',
                'user': UserSerializer(user).data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            })
        except Exception as e:
            logger.error(f"Login error: {e}")
            
            # Return consistent JSON error response
            return Response({
                'error': 'Login failed',
                'message': 'Invalid credentials or server error',
                'code': 'LOGIN_ERROR',
                'details': str(e) if settings.DEBUG else None
            }, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """User profile endpoint"""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class SendSMSView(APIView):
    """Send SMS endpoint"""
    permission_classes = [permissions.IsAuthenticated]

    async def post(self, request):
        serializer = SendSMSSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        message_text = serializer.validated_data['message_text']
        recipients = serializer.validated_data['recipients']
        sender_id = serializer.validated_data.get('sender_id')
        template_id = serializer.validated_data.get('template_id')

        try:
            # Send SMS asynchronously
            result = await send_sms_message(
                user=request.user,
                message_text=message_text,
                recipients_list=recipients,
                sender_id=sender_id,
                template_id=template_id
            )

            if result.get('success'):
                return Response({
                    'message': 'SMS sent successfully',
                    'message_id': result.get('message_id'),
                    'recipients_count': len(recipients),
                    'api_response': result.get('api_response')
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': result.get('error', 'unknown error'),
                    'message_id': result.get('message_id')
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error in SendSMSView: {e}")
            return Response({
                'error': 'Failed to send SMS',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SMSHistoryView(generics.ListAPIView):
    """SMS history endpoint"""
    serializer_class = SMSMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = SMSMessage.objects.filter(user=self.request.user)

        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        if start_date:
            try:
                start_date = datetime.fromisoformat(start_date)
                queryset = queryset.filter(created_at__gte=start_date)
            except ValueError:
                pass

        if end_date:
            try:
                end_date = datetime.fromisoformat(end_date)
                queryset = queryset.filter(created_at__lte=end_date)
            except ValueError:
                pass

        return queryset.order_by('-created_at')


class SMSMessageDetailView(generics.RetrieveAPIView):
    """SMS message detail endpoint"""
    serializer_class = SMSMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SMSMessage.objects.filter(user=self.request.user)


class SenderIDListCreateView(generics.ListCreateAPIView):
    """Sender ID list and create endpoint"""
    serializer_class = SenderIDSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SenderID.objects.filter(user=self.request.user)


class SenderIDDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Sender ID detail endpoint"""
    serializer_class = SenderIDSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SenderID.objects.filter(user=self.request.user)


class TemplateListCreateView(generics.ListCreateAPIView):
    """Template list and create endpoint"""
    serializer_class = TemplateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Admins may want to see all templates; teachers only their own
        if getattr(self.request.user, 'role', None) == 'admin':
            return Template.objects.all()
        return Template.objects.filter(user=self.request.user)


class TemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Template detail endpoint"""
    serializer_class = TemplateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self.request.user, 'role', None) == 'admin':
            return Template.objects.all()
        return Template.objects.filter(user=self.request.user)


class APICredentialsView(generics.RetrieveUpdateAPIView):
    """API credentials endpoint"""
    serializer_class = APICredentialsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        credentials, created = APICredentials.objects.get_or_create(
            user=self.request.user,
            defaults={
                'api_key': '',
                'client_id': '',
                'sender_id': ''
            }
        )
        return credentials


class DashboardStatsView(APIView):
    """Dashboard statistics endpoint (returns JSON)"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        data = build_dashboard_data(request.user)
        return Response(data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def bulk_send_sms(request):
    """Bulk SMS sending endpoint"""
    try:
        message_text = request.data.get('message_text')
        recipients_file = request.FILES.get('recipients_file')
        sender_id = request.data.get('sender_id')

        if not message_text:
            return Response({'error': 'Message text is required'}, status=status.HTTP_400_BAD_REQUEST)

        recipients = []

        if recipients_file:
            # Process uploaded file
            try:
                content = recipients_file.read().decode('utf-8')
                recipients = [line.strip() for line in content.split('\n') if line.strip()]
            except Exception as e:
                return Response({'error': f'Error reading file: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Get recipients from request data
            recipients = request.data.get('recipients', [])

        if not recipients:
            return Response({'error': 'Recipients are required'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate recipients format
        import re
        phone_pattern = re.compile(r'^\+?1?\d{9,15}$')
        invalid_numbers = [num for num in recipients if not phone_pattern.match(num.strip())]

        if invalid_numbers:
            return Response({
                'error': 'Invalid phone number format',
                'invalid_numbers': invalid_numbers[:10]  # Show first 10 invalid numbers
            }, status=status.HTTP_400_BAD_REQUEST)

        # Send SMS
        async def send_bulk():
            return await send_sms_message(
                user=request.user,
                message_text=message_text,
                recipients_list=recipients,
                sender_id=sender_id
            )

        result = asyncio.run(send_bulk())

        if result.get('success'):
            return Response({
                'message': f'Bulk SMS sent to {len(recipients)} recipients',
                'message_id': result.get('message_id'),
                'recipients_count': len(recipients)
            })
        else:
            return Response({'error': result.get('error', 'unknown error')}, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"Error in bulk_send_sms: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# HTML view: sidebar partial (role-aware)
@login_required
def sidebar_view(request):
    """
    Returns a sidebar HTML partial rendered with role context.
    Frontend fetch('/sidebar/') expects this endpoint.
    """
    role = getattr(request.user, 'role', 'teacher')
    return render(request, 'partials/sidebar.html', {'role': role})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def api_sidebar_view(request):
    """
    API-compatible sidebar endpoint using JWT authentication.
    Returns HTML partial for AJAX loading.
    """
    role = getattr(request.user, 'role', 'teacher')
    
    try:
        from django.template.loader import render_to_string
        sidebar_html = render_to_string('includes/sidebar.html', {'role': role, 'user': request.user})
        
        # Return as plain text/html for direct injection
        from django.http import HttpResponse
        return HttpResponse(sidebar_html, content_type='text/html')
    except Exception as e:
        logger.error(f"Error rendering sidebar: {e}")
        return Response({
            'error': 'Failed to load sidebar',
            'detail': str(e) if settings.DEBUG else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# HTML view: dashboard page (renders the correct template per-role)
@login_required
def dashboard_page(request):
    """
    Renders an HTML dashboard page. Uses the same build_dashboard_data helper
    and injects context suitable for the admin or teacher template.
    """
    stats = build_dashboard_data(request.user)

    if getattr(request.user, 'role', None) == 'admin':
        # admin context
        pending_templates = Template.objects.filter(status='pending').count()
        context = {
            'stats': stats,
            'recent_messages': stats.get('recent_messages', []),
            'pending_templates': pending_templates,
        }
        return render(request, 'dashboard_admin.html', context)
    else:
        # teacher context
        context = {
            'stats': stats,
            'recent_messages': stats.get('recent_messages', []),
            'templates_count': stats.get('templates_count', 0),
            'groups_count': stats.get('groups_count', 0),
        }
        return render(request, 'dashboard_teacher.html', context)
