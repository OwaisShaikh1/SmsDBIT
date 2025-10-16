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
from .models import User, SMSMessage, SenderID, Template, APICredentials, SMSUsageStats
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer, UserSerializer,
    SMSMessageSerializer, SenderIDSerializer, TemplateSerializer,
    APICredentialsSerializer, SendSMSSerializer, SMSUsageStatsSerializer,
    DashboardStatsSerializer
)
from .services import send_sms_message
import logging

logger = logging.getLogger(__name__)


class UserRegistrationView(generics.CreateAPIView):
    """User registration endpoint"""
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
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


class UserLoginView(APIView):
    """User login endpoint"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
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
            
            if result['success']:
                return Response({
                    'message': 'SMS sent successfully',
                    'message_id': result['message_id'],
                    'recipients_count': len(recipients),
                    'api_response': result.get('api_response')
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': result['error'],
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
        return Template.objects.filter(user=self.request.user)


class TemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Template detail endpoint"""
    serializer_class = TemplateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
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
    """Dashboard statistics endpoint"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Get usage stats
        usage_stats, created = SMSUsageStats.objects.get_or_create(
            user=user,
            defaults={
                'total_sent': 0,
                'total_delivered': 0,
                'total_failed': 0,
                'total_cost': 0,
                'remaining_credits': 1000  # Default credits
            }
        )
        
        # Calculate success rate
        total_attempts = usage_stats.total_delivered + usage_stats.total_failed
        success_rate = (usage_stats.total_delivered / total_attempts * 100) if total_attempts > 0 else 0
        
        # Get recent messages (last 5)
        recent_messages = SMSMessage.objects.filter(user=user).order_by('-created_at')[:5]
        
        # Get monthly stats (last 6 months)
        monthly_stats = self.get_monthly_stats(user)
        
        data = {
            'total_sent': usage_stats.total_sent,
            'total_delivered': usage_stats.total_delivered,
            'total_failed': usage_stats.total_failed,
            'success_rate': round(success_rate, 2),
            'recent_messages': SMSMessageSerializer(recent_messages, many=True).data,
            'monthly_stats': monthly_stats,
            'remaining_credits': usage_stats.remaining_credits
        }
        
        serializer = DashboardStatsSerializer(data)
        return Response(serializer.data)
    
    def get_monthly_stats(self, user):
        """Get monthly SMS statistics for the last 6 months"""
        now = timezone.now()
        six_months_ago = now - timedelta(days=180)
        
        # Group messages by month
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
        
        # Format for chart
        months = []
        sent_counts = []
        failed_counts = []
        
        for data in monthly_data:
            months.append(data['month'])
            sent_counts.append(data['sent'])
            failed_counts.append(data['failed'])
        
        return {
            'months': months,
            'sent': sent_counts,
            'failed': failed_counts
        }


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
        
        if result['success']:
            return Response({
                'message': f'Bulk SMS sent to {len(recipients)} recipients',
                'message_id': result['message_id'],
                'recipients_count': len(recipients)
            })
        else:
            return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error in bulk_send_sms: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
