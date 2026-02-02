"""
Quick test script for template creation API
Run with: python test_template_create.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sms_portal.settings')
django.setup()

from django.test import Client
from sms.models import User
import json

# Create test client
client = Client()

# Get or create admin user
admin = User.objects.filter(role='admin').first()
if not admin:
    print("❌ No admin user found. Create one first with:")
    print("   python manage.py create_user")
    exit(1)

print(f"✓ Using admin: {admin.email}")

# Login
client.force_login(admin)
print("✓ Logged in")

# Test template data
template_data = {
    "title": "Test Template",
    "category": "student",
    "content": "Hello {#student_name#}, your test is on {#test_date#}.",
    "class_scope": "10th A",
    "variable_schema": {
        "student_name": {"type": "string", "required": True},
        "test_date": {"type": "date", "required": True}
    },
    "status": "pending",
    "is_active": True
}

print("\n📤 Sending POST request to /api/templates/create/")
print(f"Data: {json.dumps(template_data, indent=2)}")

# Make request
response = client.post(
    '/api/templates/create/',
    data=json.dumps(template_data),
    content_type='application/json'
)

print(f"\n📥 Response Status: {response.status_code}")
print(f"Response: {response.content.decode()}")

if response.status_code == 201:
    print("\n✅ Template created successfully!")
    result = json.loads(response.content)
    print(f"Template ID: {result.get('template', {}).get('id')}")
else:
    print("\n❌ Template creation failed!")
