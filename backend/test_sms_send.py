#!/usr/bin/env python
"""
Test script to send a sample SMS using MySMSMantra API
Run this from the backend directory: python test_sms_send.py
"""

import os
import sys
import django
from pathlib import Path

# Add project to path
sys.path.append(str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sms_portal.settings')
django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from sms.services import send_sms_message

def test_sms_api():
    print("📱 Testing MySMSMantra API with Sample SMS")
    print("=" * 50)
    
    # Check credentials first
    print("1. Checking API Credentials...")
    config = settings.MYSMSMANTRA_CONFIG
    
    if not config['API_KEY'] or config['API_KEY'] == 'your-api-key-here':
        print("❌ ERROR: Please set your actual MYSMSMANTRA_API_KEY in .env file")
        return False
        
    if not config['CLIENT_ID'] or config['CLIENT_ID'] == 'your-client-id-here':
        print("❌ ERROR: Please set your actual MYSMSMANTRA_CLIENT_ID in .env file")
        return False
        
    if not config['SENDER_ID'] or config['SENDER_ID'] == 'your-sender-id-here':
        print("❌ ERROR: Please set your actual MYSMSMANTRA_SENDER_ID in .env file")
        return False
    
    print(f"   ✅ API URL: {config['API_URL']}")
    print(f"   ✅ API Key: ***{config['API_KEY'][-4:]}")
    print(f"   ✅ Client ID: ***{config['CLIENT_ID'][-4:]}")
    print(f"   ✅ Sender ID: {config['SENDER_ID']}")
    
    print("\n2. Getting Test User...")
    User = get_user_model()
    user = User.objects.first()
    
    if not user:
        print("❌ ERROR: No users found. Please create a user first.")
        return False
    
    print(f"   ✅ Using user: {user.email}")
    
    # Test SMS details
    test_number = "9769714298"
    test_message = "🧪 TEST SMS from SMS Portal - MySMSMantra API integration test. If you receive this, the API is working!"
    
    print(f"\n3. Sending Test SMS...")
    print(f"   📞 To: {test_number}")
    print(f"   💬 Message: {test_message}")
    
    try:
        # Send the SMS
        result = send_sms_message(
            user=user,
            message_text=test_message,
            recipients_list=[test_number],
            sender_id=config['SENDER_ID']
        )
        
        print(f"\n4. SMS Send Result:")
        print(f"   Success: {result.get('success', False)}")
        print(f"   Message: {result.get('message', 'No message')}")
        
        if result.get('api_response'):
            print(f"   API Response: {result['api_response']}")
        
        if result.get('error'):
            print(f"   Error: {result['error']}")
            
        # Check database record
        from sms.models import SMSMessage
        latest_sms = SMSMessage.objects.filter(user=user).order_by('-id').first()
        
        if latest_sms:
            print(f"\n5. Database Record:")
            print(f"   SMS ID: {latest_sms.id}")
            print(f"   Status: {latest_sms.status}")
            print(f"   Recipients: {latest_sms.recipients}")
            print(f"   Sent At: {latest_sms.sent_at}")
            
        return result.get('success', False)
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def check_credentials_setup():
    """Check if user needs to set up credentials"""
    config = settings.MYSMSMANTRA_CONFIG
    
    needs_setup = (
        not config['API_KEY'] or config['API_KEY'] == 'your-api-key-here' or
        not config['CLIENT_ID'] or config['CLIENT_ID'] == 'your-client-id-here' or
        not config['SENDER_ID'] or config['SENDER_ID'] == 'your-sender-id-here'
    )
    
    if needs_setup:
        print("\n🔧 SETUP REQUIRED:")
        print("Please update your .env file with actual MySMSMantra credentials:")
        print("")
        print("MYSMSMANTRA_API_KEY=your_actual_api_key")
        print("MYSMSMANTRA_CLIENT_ID=your_actual_client_id") 
        print("MYSMSMANTRA_SENDER_ID=your_actual_sender_id")
        print("")
        print("Get these from: https://www.mysmsmantra.com/")
        return False
    
    return True

if __name__ == "__main__":
    if check_credentials_setup():
        success = test_sms_api()
        if success:
            print("\n🎉 SMS API Test SUCCESSFUL!")
            print("✅ Check your phone (9769714298) for the test message")
        else:
            print("\n❌ SMS API Test FAILED!")
            print("Check the error messages above and verify your credentials")
    else:
        print("\n⚠️  Please set up your credentials first!")