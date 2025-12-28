"""
Test script to verify reports functionality
Run this after starting the server: python manage.py test_reports.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sms_portal.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from sms.models import SMSMessage, Campaign, Group, Template
import json

User = get_user_model()

def test_reports_data():
    print("=" * 60)
    print("TESTING REPORTS PAGE DATA SOURCES")
    print("=" * 60)
    
    # Get test user
    admin_user = User.objects.filter(role='admin').first()
    teacher_user = User.objects.filter(role='teacher').first()
    
    if not admin_user and not teacher_user:
        print("⚠️  No users found. Creating test data...")
        admin_user = User.objects.create_user(
            username='testadmin',
            email='admin@test.com',
            password='test123',
            role='admin'
        )
        print(f"✓ Created admin user: {admin_user.email}")
    
    user = admin_user if admin_user else teacher_user
    print(f"\n📊 Testing with user: {user.email} (Role: {user.role})")
    
    # Test 1: Check SMSMessage data
    print("\n" + "=" * 60)
    print("1. TESTING SMS MESSAGES DATA")
    print("=" * 60)
    
    seven_days_ago = timezone.now() - timedelta(days=7)
    
    if user.role == "admin":
        messages = SMSMessage.objects.filter(created_at__gte=seven_days_ago)
    else:
        messages = SMSMessage.objects.filter(user=user, created_at__gte=seven_days_ago)
    
    total_messages = messages.count()
    delivered = messages.filter(status='delivered').count()
    failed = messages.filter(status='failed').count()
    
    print(f"Total Messages (last 7 days): {total_messages}")
    print(f"  └─ Delivered: {delivered}")
    print(f"  └─ Failed: {failed}")
    print(f"  └─ Delivery Rate: {(delivered/total_messages*100):.1f}%" if total_messages > 0 else "  └─ Delivery Rate: 0%")
    
    if total_messages == 0:
        print("⚠️  No messages found in last 7 days")
    else:
        print("✓ Messages data available")
    
    # Test 2: Check Campaign data
    print("\n" + "=" * 60)
    print("2. TESTING CAMPAIGNS DATA")
    print("=" * 60)
    
    if user.role == "admin":
        campaigns = Campaign.objects.all()
    else:
        campaigns = Campaign.objects.filter(user=user)
    
    total_campaigns = campaigns.count()
    completed_campaigns = campaigns.filter(status='completed').count()
    
    print(f"Total Campaigns: {total_campaigns}")
    print(f"  └─ Completed: {completed_campaigns}")
    print(f"  └─ Draft: {campaigns.filter(status='draft').count()}")
    print(f"  └─ Sending: {campaigns.filter(status='sending').count()}")
    
    if total_campaigns == 0:
        print("⚠️  No campaigns found")
    else:
        print("✓ Campaigns data available")
        print("\nSample campaigns:")
        for campaign in campaigns[:3]:
            print(f"  • {campaign.title} - {campaign.status} (Sent: {campaign.total_sent}, Delivered: {campaign.total_delivered})")
    
    # Test 3: Test delivery trends calculation
    print("\n" + "=" * 60)
    print("3. TESTING DELIVERY TRENDS (7 DAYS)")
    print("=" * 60)
    
    today = timezone.now().date()
    delivery_trends = []
    
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_start = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.min.time()))
        day_end = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.max.time()))
        
        if user.role == "admin":
            day_messages = SMSMessage.objects.filter(created_at__range=[day_start, day_end])
        else:
            day_messages = SMSMessage.objects.filter(user=user, created_at__range=[day_start, day_end])
        
        sent = day_messages.count()
        delivered = day_messages.filter(status='delivered').count()
        failed = day_messages.filter(status='failed').count()
        
        delivery_trends.append({
            'date': day.strftime('%Y-%m-%d'),
            'sent': sent,
            'delivered': delivered,
            'failed': failed
        })
        
        print(f"{day.strftime('%Y-%m-%d')}: Sent: {sent:4d}, Delivered: {delivered:4d}, Failed: {failed:4d}")
    
    # Test 4: Test category analysis
    print("\n" + "=" * 60)
    print("4. TESTING CATEGORY ANALYSIS")
    print("=" * 60)
    
    if user.role == "admin":
        campaigns_for_cat = Campaign.objects.filter(status='completed')
    else:
        campaigns_for_cat = Campaign.objects.filter(user=user, status='completed')
    
    academic_keywords = ['exam', 'test', 'result', 'homework', 'assignment', 'class', 'lecture']
    admin_keywords = ['meeting', 'notice', 'announcement', 'circular', 'reminder']
    event_keywords = ['event', 'fest', 'competition', 'celebration', 'program', 'function']
    emergency_keywords = ['urgent', 'emergency', 'alert', 'important', 'immediate']
    
    categories = {
        'Academic': 0,
        'Administrative': 0,
        'Events': 0,
        'Emergency': 0,
        'Other': 0
    }
    
    for campaign in campaigns_for_cat:
        title_lower = (campaign.title or '').lower()
        desc_lower = (campaign.description or '').lower()
        text = title_lower + ' ' + desc_lower
        
        categorized = False
        if any(kw in text for kw in emergency_keywords):
            categories['Emergency'] += campaign.total_sent
            categorized = True
        elif any(kw in text for kw in academic_keywords):
            categories['Academic'] += campaign.total_sent
            categorized = True
        elif any(kw in text for kw in admin_keywords):
            categories['Administrative'] += campaign.total_sent
            categorized = True
        elif any(kw in text for kw in event_keywords):
            categories['Events'] += campaign.total_sent
            categorized = True
        
        if not categorized:
            categories['Other'] += campaign.total_sent
    
    total_cat = sum(categories.values())
    for name, count in categories.items():
        percentage = (count / total_cat * 100) if total_cat > 0 else 0
        print(f"{name:15s}: {count:6d} messages ({percentage:5.1f}%)")
    
    # Test 5: Test Users count
    print("\n" + "=" * 60)
    print("5. TESTING USERS DATA")
    print("=" * 60)
    
    total_users = User.objects.count()
    admin_users = User.objects.filter(role='admin').count()
    teacher_users = User.objects.filter(role='teacher').count()
    
    print(f"Total Users: {total_users}")
    print(f"  └─ Admins: {admin_users}")
    print(f"  └─ Teachers: {teacher_users}")
    
    # Final Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    issues = []
    if total_messages == 0:
        issues.append("No SMS messages in database")
    if total_campaigns == 0:
        issues.append("No campaigns in database")
    if total_users <= 1:
        issues.append("Only one user in database")
    
    if issues:
        print("⚠️  Potential Issues:")
        for issue in issues:
            print(f"  • {issue}")
        print("\n💡 Consider creating sample data using create_sample_sms_data.py")
    else:
        print("✅ All data sources are properly configured and contain data!")
    
    print("\n" + "=" * 60)
    print("JSON DATA PREVIEW (as sent to template)")
    print("=" * 60)
    
    stats_json = {
        'total_sent': total_messages,
        'delivery_rate': round((delivered/total_messages*100) if total_messages > 0 else 0, 1),
        'failed_count': failed,
        'active_users': teacher_users if user.role == 'admin' else 1
    }
    
    print("\ninitial_stats:")
    print(json.dumps(stats_json, indent=2))
    
    print("\ndelivery_trends (sample):")
    print(json.dumps(delivery_trends[:3], indent=2))
    
    print("\n" + "=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)

if __name__ == '__main__':
    test_reports_data()
