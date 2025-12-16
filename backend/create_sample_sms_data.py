"""
Script to create sample SMS data for testing reports
"""
import os
import django
import sys
from datetime import datetime, timedelta
import random

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sms_portal.settings')
django.setup()

from sms.models import SMSMessage, User
from django.utils import timezone

def create_sample_data():
    # Get admin user
    try:
        user = User.objects.get(username='admin')
    except User.DoesNotExist:
        print("Admin user not found. Please create admin user first.")
        return
    
    print("Creating sample SMS data...")
    
    # Create messages for the last 7 days
    today = timezone.now()
    statuses = ['delivered', 'failed', 'pending']
    
    messages_created = 0
    
    for i in range(7):
        day = today - timedelta(days=6-i)
        
        # Generate random number of messages for each day (increasing trend)
        base_count = 50 + (i * 30)  # Start with 50, increase by 30 each day
        
        for j in range(base_count):
            # 85% delivered, 10% failed, 5% pending
            rand = random.random()
            if rand < 0.85:
                status = 'delivered'
            elif rand < 0.95:
                status = 'failed'
            else:
                status = 'pending'
            
            # Random hour during the day
            hour = random.randint(8, 18)
            minute = random.randint(0, 59)
            
            created_time = day.replace(hour=hour, minute=minute, second=0)
            
            SMSMessage.objects.create(
                user=user,
                recipient_number=f"+9199999{random.randint(10000, 99999)}",
                message_text=f"Sample message {j+1} for testing",
                status=status,
                created_at=created_time,
                updated_at=created_time
            )
            messages_created += 1
    
    print(f"✅ Created {messages_created} sample SMS messages")
    
    # Print summary
    print("\nSummary by status:")
    for status in ['delivered', 'failed', 'pending']:
        count = SMSMessage.objects.filter(status=status).count()
        print(f"  {status.capitalize()}: {count}")
    
    print("\nSummary by day:")
    for i in range(7):
        day = today - timedelta(days=6-i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        count = SMSMessage.objects.filter(
            created_at__range=[day_start, day_end]
        ).count()
        print(f"  {day.strftime('%Y-%m-%d')}: {count} messages")

if __name__ == '__main__':
    create_sample_data()
