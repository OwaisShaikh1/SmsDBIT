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
        from datetime import datetime, timedelta
        user = request.user
        report_type = request.GET.get('type', 'delivery')
        date_range = request.GET.get('range', 'week')
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
        
        # Generate report data based on type
        if report_type == 'delivery':
            # Delivery report - daily breakdown
            today = timezone.now().date()
            delivery_trends = []
            
            # Calculate days in range
            days_diff = (end_dt.date() - start_dt.date()).days
            
            for i in range(days_diff, -1, -1):
                day = end_dt.date() - timedelta(days=i)
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
            
            data = {
                "stats": {
                    "total_sent": total_sent,
                    "delivery_rate": round(delivery_rate, 1),
                    "failed_count": total_failed,
                    "active_users": User.objects.filter(role='teacher').count() if user.role == 'admin' else 1
                },
                "delivery_trends": delivery_trends,
                "report_type": report_type
            }
            
        elif report_type == 'usage':
            # Usage report - by user
            if user.role == 'admin':
                users = User.objects.filter(role__in=['admin', 'teacher'])
                report_data = []
                
                for u in users:
                    u_messages = SMSMessage.objects.filter(
                        user=u,
                        created_at__range=[start_dt, end_dt]
                    )
                    sent = u_messages.count()
                    last_msg = u_messages.order_by('-created_at').first()
                    last_activity = last_msg.created_at.strftime('%Y-%m-%d %H:%M') if last_msg else 'N/A'
                    
                    report_data.append({
                        'user': u.email,
                        'role': u.get_role_display(),
                        'messages_sent': sent,
                        'last_activity': last_activity,
                        'status': 'Active' if sent > 0 else 'Inactive'
                    })
                
                data = {
                    "report_type": report_type,
                    "report_data": report_data,
                    "stats": {
                        "total_users": len(report_data),
                        "active_users": len([r for r in report_data if r['status'] == 'Active']),
                        "total_sent": sum(r['messages_sent'] for r in report_data)
                    }
                }
            else:
                # Teacher can only see their own usage
                sent = messages_qs.count()
                last_msg = messages_qs.order_by('-created_at').first()
                last_activity = last_msg.created_at.strftime('%Y-%m-%d %H:%M') if last_msg else 'N/A'
                
                data = {
                    "report_type": report_type,
                    "report_data": [{
                        'user': user.email,
                        'role': user.get_role_display(),
                        'messages_sent': sent,
                        'last_activity': last_activity,
                        'status': 'Active' if sent > 0 else 'Inactive'
                    }],
                    "stats": {
                        "total_users": 1,
                        "active_users": 1 if sent > 0 else 0,
                        "total_sent": sent
                    }
                }
                
        elif report_type == 'user_activity':
            # User activity report - campaigns and templates
            if user.role == 'admin':
                campaigns = Campaign.objects.filter(
                    created_at__range=[start_dt, end_dt]
                )
            else:
                campaigns = Campaign.objects.filter(
                    user=user,
                    created_at__range=[start_dt, end_dt]
                )
            
            activity_data = []
            for campaign in campaigns:
                activity_data.append({
                    'campaign': campaign.title,
                    'user': campaign.user.email,
                    'status': campaign.get_status_display(),
                    'recipients': campaign.total_recipients,
                    'sent': campaign.total_sent,
                    'delivered': campaign.total_delivered,
                    'failed': campaign.total_failed,
                    'created': campaign.created_at.strftime('%Y-%m-%d %H:%M')
                })
            
            data = {
                "report_type": report_type,
                "report_data": activity_data,
                "stats": {
                    "total_campaigns": len(activity_data),
                    "total_sent": sum(c['sent'] for c in activity_data),
                    "total_delivered": sum(c['delivered'] for c in activity_data)
                }
            }
            
        elif report_type == 'financial':
            # Financial report - cost estimation
            sms_cost_per_message = 0.25  # Cost per SMS
            
            messages = messages_qs.all()
            total_sent = messages.count()
            total_cost = total_sent * sms_cost_per_message
            
            # Monthly breakdown
            from collections import defaultdict
            monthly_data = defaultdict(lambda: {'sent': 0, 'cost': 0})
            
            for msg in messages:
                month_key = msg.created_at.strftime('%Y-%m')
                monthly_data[month_key]['sent'] += 1
                monthly_data[month_key]['cost'] += sms_cost_per_message
            
            financial_data = [
                {
                    'month': month,
                    'messages_sent': data['sent'],
                    'cost': round(data['cost'], 2)
                }
                for month, data in sorted(monthly_data.items())
            ]
            
            data = {
                "report_type": report_type,
                "report_data": financial_data,
                "stats": {
                    "total_sent": total_sent,
                    "total_cost": round(total_cost, 2),
                    "avg_monthly_cost": round(total_cost / max(len(financial_data), 1), 2)
                }
            }
        else:
            # Default - delivery report
            data = {
                "error": "Invalid report type",
                "report_type": report_type
            }
        
        return JsonResponse(data)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)

