#!/usr/bin/env python
"""
Test script to verify .env credentials are properly imported
Run this from the backend directory: python test_env_import.py
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
from sms.services import MySMSMantraService

def test_env_import():
    print("🧪 Testing .env credential import...")
    print("-" * 50)
    
    # Test Django settings import
    print("1. Django Settings Import:")
    try:
        config = settings.MYSMSMANTRA_CONFIG
        print(f"   ✅ API_URL: {config['API_URL']}")
        print(f"   ✅ API_KEY: {'***' + config['API_KEY'][-4:] if config['API_KEY'] else 'NOT SET'}")
        print(f"   ✅ CLIENT_ID: {'***' + config['CLIENT_ID'][-4:] if config['CLIENT_ID'] else 'NOT SET'}")
        print(f"   ✅ SENDER_ID: {config['SENDER_ID'] or 'NOT SET'}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print()
    
    # Test service credential loading
    print("2. Service Credential Loading:")
    try:
        # Create a dummy user for testing
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Try to get first user, or create a test scenario
        try:
            user = User.objects.first()
            if user:
                service = MySMSMantraService(user=user)
                credentials = service.get_user_credentials()
                print(f"   ✅ Service loaded credentials successfully")
                print(f"   ✅ API Key: {'***' + credentials['api_key'][-4:] if credentials['api_key'] else 'NOT SET'}")
                print(f"   ✅ Client ID: {'***' + credentials['client_id'][-4:] if credentials['client_id'] else 'NOT SET'}")
            else:
                print("   ⚠️  No users found in database - create a user first")
        except Exception as e:
            print(f"   ❌ Service Error: {e}")
            
    except Exception as e:
        print(f"   ❌ Import Error: {e}")
    
    print()
    print("🎉 .env import test completed!")

if __name__ == "__main__":
    test_env_import()