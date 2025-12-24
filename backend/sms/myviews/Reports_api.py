from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from sms.models import SMSMessage, Campaign, User

# =========================================================================
# REPORTS API
# =========================================================================

@login_required
def reports_dashboard(request):
    """Get dashboard data for reports page"""
    try:
        user = request.user
        
        # Get basic stats
        if user.role == "admin":
            total_messages = SMSMessage.objects.count()
            total_campaigns = Campaign.objects.count()
            total_users = User.objects.filter(role='teacher').count()
        else:
            total_messages = SMSMessage.objects.filter(user=user).count()
            total_campaigns = Campaign.objects.filter(user=user).count()
            total_users = 1  # Just the teacher themselves
        
        # Get recent activity (last 7 days for trends)
        from datetime import datetime, timedelta
        today = timezone.now().date()
        delivery_trends = []
        
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            day_start = timezone.make_aware(datetime.combine(day, datetime.min.time()))
            day_end = timezone.make_aware(datetime.combine(day, datetime.max.time()))
            
            if user.role == "admin":
                messages = SMSMessage.objects.filter(
                    created_at__range=[day_start, day_end]
                )
            else:
                messages = SMSMessage.objects.filter(
                    user=user,
                    created_at__range=[day_start, day_end]
                )
            
            sent = messages.count()
            delivered = messages.filter(status='delivered').count()
            failed = messages.filter(status='failed').count()
            
            delivery_trends.append({
                'date': day.strftime('%Y-%m-%d'),
                'sent': sent,
                'delivered': delivered,
                'failed': failed
            })
        
        # Calculate delivery rate
        total_sent = sum(d['sent'] for d in delivery_trends)
        total_delivered = sum(d['delivered'] for d in delivery_trends)
        delivery_rate = (total_delivered / total_sent * 100) if total_sent > 0 else 0
        
        # Get message categories (mock data for now - you can add category field to SMSMessage model)
        categories = [
            {'name': 'Academic', 'count': int(total_messages * 0.41), 'percentage': 41.0},
            {'name': 'Administrative', 'count': int(total_messages * 0.265), 'percentage': 26.5},
            {'name': 'Events', 'count': int(total_messages * 0.196), 'percentage': 19.6},
            {'name': 'Emergency', 'count': int(total_messages * 0.129), 'percentage': 12.9}
        ]
        
        return JsonResponse({
            "stats": {
                "total_sent": total_sent,
                "delivery_rate": round(delivery_rate, 1),
                "failed_count": sum(d['failed'] for d in delivery_trends),
                "active_users": total_users
            },
            "delivery_trends": delivery_trends,
            "categories": categories
        })
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required  
def reports_generate(request):
    """Generate reports based on parameters"""
    try:
        user = request.user
        report_type = request.GET.get('type', 'delivery')
        date_range = request.GET.get('range', 'last30')
        start_date = request.GET.get('start')
        end_date = request.GET.get('end')
        
        # Calculate date range
        if date_range == 'today':
            start_dt = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = timezone.now()
        elif date_range == 'yesterday':
            yesterday = timezone.now() - timedelta(days=1)
            start_dt = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif date_range == 'week':
            start_dt = timezone.now() - timedelta(days=7)
            end_dt = timezone.now()
        elif date_range == 'month':
            start_dt = timezone.now() - timedelta(days=30)
            end_dt = timezone.now()
        elif date_range == 'custom' and start_date and end_date:
            start_dt = timezone.make_aware(datetime.strptime(start_date, '%Y-%m-%d'))
            end_dt = timezone.make_aware(datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
        else:
            # Default to last 7 days
            start_dt = timezone.now() - timedelta(days=7)
            end_dt = timezone.now()
        
        # Filter messages based on user role
        if user.role == "admin":
            messages_qs = SMSMessage.objects.filter(
                created_at__range=[start_dt, end_dt]
            )
        else:
            messages_qs = SMSMessage.objects.filter(
                user=user,
                created_at__range=[start_dt, end_dt]
            )
        
        # Generate report data based on actual database records
        from datetime import datetime, timedelta
        today = timezone.now().date()
        delivery_trends = []
        
        # Get data for last 7 days
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            day_start = timezone.make_aware(datetime.combine(day, datetime.min.time()))
            day_end = timezone.make_aware(datetime.combine(day, datetime.max.time()))
            
            messages = messages_qs.filter(created_at__range=[day_start, day_end])
            sent = messages.count()
            delivered = messages.filter(status='delivered').count()
            failed = messages.filter(status='failed').count()
            
            delivery_trends.append({
                'date': day.strftime('%Y-%m-%d'),
                'sent': sent,
                'delivered': delivered,
                'failed': failed
            })
        
        # Calculate stats
        total_sent = sum(d['sent'] for d in delivery_trends)
        total_delivered = sum(d['delivered'] for d in delivery_trends)
        total_failed = sum(d['failed'] for d in delivery_trends)
        delivery_rate = (total_delivered / total_sent * 100) if total_sent > 0 else 0
        
        # Get categories (mock for now)
        categories = [
            {'name': 'Academic', 'count': int(total_sent * 0.41), 'percentage': 41.0},
            {'name': 'Administrative', 'count': int(total_sent * 0.265), 'percentage': 26.5},
            {'name': 'Events', 'count': int(total_sent * 0.196), 'percentage': 19.6},
            {'name': 'Emergency', 'count': int(total_sent * 0.129), 'percentage': 12.9}
        ]
        
        data = {
            "stats": {
                "total_sent": total_sent,
                "delivery_rate": round(delivery_rate, 1),
                "failed_count": total_failed,
                "active_users": User.objects.filter(role='teacher').count() if user.role == 'admin' else 1
            },
            "delivery_trends": delivery_trends,
            "categories": categories,
            "report_type": report_type
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

