from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json
from sms.models import User, SMSUsageStats
import logging
logger = logging.getLogger(__name__)

# =========================================================================
# USER MANAGEMENT API
# =========================================================================

@login_required
def create_user_view(request):
    """Create a new user (admin only)"""
    if request.method != 'POST':
        return JsonResponse({"error": "POST only"}, status=405)
    
    # Only admins can create users
    if request.user.role != 'admin':
        return JsonResponse({"error": "Permission denied. Admin access required."}, status=403)
    
    try:
        from django.db import transaction
        
        data = json.loads(request.body)
        email = data.get('email', '').strip()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        role = data.get('role', 'teacher')
        phone_number = data.get('phone_number', '').strip()
        company = data.get('company', '').strip()
        assigned_class = data.get('assigned_class', '').strip()
        is_staff = data.get('is_staff', False)
        credits = data.get('credits', 100)
        
        # Validate required fields
        if not email or not username or not password:
            return JsonResponse({"error": "Email, username, and password are required."}, status=400)
        
        # Check if user exists
        if User.objects.filter(email=email).exists():
            return JsonResponse({"error": f"User with email '{email}' already exists."}, status=400)
        
        if User.objects.filter(username=username).exists():
            return JsonResponse({"error": f"User with username '{username}' already exists."}, status=400)
        
        # Create user in transaction
        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                username=username,
                password=password,
                role=role,
                phone_number=phone_number,
                company=company,
                assigned_class=assigned_class,
                is_staff=is_staff,
                is_active=True,
                is_verified=True
            )
            
            # Create SMS Usage Stats
            SMSUsageStats.objects.create(
                user=user,
                remaining_credits=credits,
                total_sent=0,
                total_delivered=0,
                total_failed=0
            )
            
            logger.info(f"User created: {email} by admin {request.user.email}")
            
            return JsonResponse({
                "success": True,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "role": user.role,
                    "credits": credits
                }
            })
    
    except Exception as e:
        logger.exception("Error creating user")
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def delete_user_view(request):
    """Delete or deactivate a user (admin only). POST JSON: { user_id: int, hard: bool }
    By default performs a soft-deactivate (is_active=False). If 'hard'==true, performs permanent delete.
    """
    if request.method != 'POST':
        return JsonResponse({"error": "POST only"}, status=405)

    if request.user.role != 'admin':
        return JsonResponse({"error": "Permission denied. Admin access required."}, status=403)

    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        hard = bool(data.get('hard', False))
        action = data.get('action', '').lower()  # 'activate' | 'deactivate' | 'delete'

        if not user_id:
            return JsonResponse({"error": "user_id is required"}, status=400)

        # Prevent deleting or modifying self
        if int(user_id) == int(request.user.id):
            return JsonResponse({"error": "You cannot modify your own account"}, status=400)

        try:
            target = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({"error": "User not found"}, status=404)

        # Explicit action handling
        if action == 'activate':
            target.is_active = True
            target.save()
            logger.info(f"User {target.email} (id={user_id}) activated by {request.user.email}")
            return JsonResponse({"success": True, "message": "User activated"})

        if action == 'deactivate':
            target.is_active = False
            target.save()
            logger.info(f"User {target.email} (id={user_id}) deactivated by {request.user.email}")
            return JsonResponse({"success": True, "message": "User deactivated"})

        # fallback: if hard flag or action == 'delete' perform permanent delete
        if hard or action == 'delete':
            target.delete()
            logger.info(f"User {target.email} (id={user_id}) permanently deleted by {request.user.email}")
            return JsonResponse({"success": True, "message": "User permanently deleted"})

        # Default behavior: soft-deactivate
        target.is_active = False
        target.save()
        logger.info(f"User {target.email} (id={user_id}) deactivated by {request.user.email}")
        return JsonResponse({"success": True, "message": "User deactivated"})

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.exception("Error deleting user")
        return JsonResponse({"error": str(e)}, status=500)
