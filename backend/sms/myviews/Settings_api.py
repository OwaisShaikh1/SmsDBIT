from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from ..models import APICredentials, User
from ..services import MySMSMantraService
import json
import logging
logger = logging.getLogger(__name__)

# =========================================================================
# SETTINGS API
# =========================================================================

@login_required
def get_settings(request):
    """Get user settings"""
    if request.method != 'GET':
        return JsonResponse({"error": "GET only"}, status=405)
    
    user = request.user
    
    # Get API credentials if they exist
    api_creds = None
    try:
        api_creds = APICredentials.objects.get(user=user)
    except APICredentials.DoesNotExist:
        pass
    
    settings_data = {
        "general": {
            "username": user.username,
            "email": user.email,
            "phone": user.phone_number or "",
            "company": user.company or "",
            "assigned_class": user.assigned_class or ""
        },
        "sms": {
            "api_key": api_creds.api_key if api_creds else "",
            "client_id": api_creds.client_id if api_creds else "",
            "sender_id": api_creds.sender_id if api_creds else "",
            "has_credentials": api_creds is not None
        }
    }
    
    return JsonResponse(settings_data)


@login_required
def update_general_settings(request):
    """Update general user settings"""
    if request.method != 'POST':
        return JsonResponse({"error": "POST only"}, status=405)
    
    try:
        data = json.loads(request.body)
        user = request.user
        
        # Update allowed fields
        if 'username' in data:
            username = data['username'].strip()
            if username and username != user.username:
                if User.objects.filter(username=username).exists():
                    return JsonResponse({"error": "Username already exists"}, status=400)
                user.username = username
        
        if 'phone' in data:
            user.phone_number = data['phone'].strip()
        
        if 'company' in data:
            user.company = data['company'].strip()
        
        if 'assigned_class' in data:
            user.assigned_class = data['assigned_class'].strip()
        
        user.save()
        
        return JsonResponse({
            "success": True,
            "message": "Settings updated successfully"
        })
    
    except Exception as e:
        logger.exception("Error updating general settings")
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def update_sms_settings(request):
    """Update SMS API credentials"""
    if request.method != 'POST':
        return JsonResponse({"error": "POST only"}, status=405)
    
    try:
        from django.db import transaction
        
        data = json.loads(request.body)
        user = request.user
        
        api_key = data.get('api_key', '').strip()
        client_id = data.get('client_id', '').strip()
        sender_id = data.get('sender_id', '').strip()
        
        if not api_key or not client_id:
            return JsonResponse({"error": "API Key and Client ID are required"}, status=400)
        
        with transaction.atomic():
            api_creds, created = APICredentials.objects.get_or_create(
                user=user,
                defaults={
                    'api_key': api_key,
                    'client_id': client_id,
                    'sender_id': sender_id or 'BOMBYS',
                    'is_active': True
                }
            )
            
            if not created:
                # Update existing credentials
                api_creds.api_key = api_key
                api_creds.client_id = client_id
                api_creds.sender_id = sender_id or 'BOMBYS'
                api_creds.is_active = True
                api_creds.save()
        
        return JsonResponse({
            "success": True,
            "message": "SMS credentials updated successfully"
        })
    
    except Exception as e:
        logger.exception("Error updating SMS settings")
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def test_sms_settings(request):
    """Test SMS API credentials"""
    if request.method != 'POST':
        return JsonResponse({"error": "POST only"}, status=405)
    
    try:
        data = json.loads(request.body)
        phone = data.get('phone', '').strip()
        
        if not phone:
            return JsonResponse({"error": "Phone number is required"}, status=400)
        
        # Send a test SMS
        
        
        service = MySMSMantraService(user=request.user)
        message = f"Test SMS from SMS Portal. Your API credentials are working! - {timezone.now().strftime('%d %b %Y %H:%M')}"
        
        # This would call the actual SMS API - for now just validate credentials exist
        try:
            credentials = service.get_user_credentials()
            
            # TODO: Actually send test SMS
            # For now, just validate credentials are configured
            
            return JsonResponse({
                "success": True,
                "message": f"Test message would be sent to {phone}. Credentials validated."
            })
        
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)
    
    except Exception as e:
        logger.exception("Error testing SMS settings")
        return JsonResponse({"error": str(e)}, status=500)

