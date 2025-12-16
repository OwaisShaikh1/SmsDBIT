from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import datetime, timedelta
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.conf import settings
import logging
import asyncio
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from asgiref.sync import sync_to_async, async_to_sync
from .services import send_sms_message

from .models import (
    User, SMSMessage, SenderID, Template, APICredentials, SMSUsageStats,
    Group, StudentContact, Campaign
)
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer, UserSerializer,
    SMSMessageSerializer, SenderIDSerializer, TemplateSerializer,
    APICredentialsSerializer, SendSMSSerializer, SMSUsageStatsSerializer,
    DashboardStatsSerializer, ContactSerializer
)
from .services import send_sms_message

logger = logging.getLogger(__name__)






import asyncio
import logging
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .services import send_sms_message  # your async function from the file you shared

logger = logging.getLogger(__name__)

@csrf_exempt
def send_sms(request):
    """Sync endpoint for sending SMS via MySMSMantra."""
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        template_id = data.get("template_id")
        recipients = data.get("recipients", [])
        messages = data.get("messages", [])

        if not recipients or not messages:
            return JsonResponse({"error": "Missing messages or recipients"}, status=400)

        message_text = messages[0].get("message", "")

        # ✅ Direct sync call (no async_to_sync needed)
        result = send_sms_message(
            user=request.user if request.user.is_authenticated else None,
            message_text=message_text,
            recipients_list=recipients,
            template_id=template_id,
        )

        return JsonResponse(result, status=200 if result.get("success") else 500)

    except Exception as e:
        logger.exception("Error in send_sms view")
        return JsonResponse({"error": str(e)}, status=500)

# -------------------------------------------------------------------------
# ✅ CONTACTS API — Fetch from DB (used by /contacts/ page)
# -------------------------------------------------------------------------
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import StudentContact

@login_required
def get_contacts(request):
    """
    Return contacts filtered by user's assigned class.
    Admins see all contacts.
    Teachers see only contacts in their assigned_class.
    """
    user = request.user

    if user.role == "admin":
        # Admins see everything — no assigned_class needed
        contacts_qs = StudentContact.objects.all()
    else:
        # Teachers see only contacts matching their assigned_class
        if user.assigned_class:
            contacts_qs = StudentContact.objects.filter(class_dept=user.assigned_class)
        else:
            # If somehow no assigned_class set, return none
            contacts_qs = StudentContact.objects.none()

    contacts = contacts_qs.values(
        "id",
        "name",
        "phone_number",
        "class_dept",
        "meta",
    )

    contacts_list = []
    for c in contacts:
        meta = c["meta"] if isinstance(c["meta"], dict) else {}
        contacts_list.append({
            "id": c["id"],
            "first_name": c["name"],
            "phone": c["phone_number"],
            "email": meta.get("email", "-"),
            "category": meta.get("category", "students"),
            "class_dept": c["class_dept"] or "-",
        })

    return JsonResponse(contacts_list, safe=False)


# -------------------------------------------------------------------------
# ✅ DASHBOARD PAGE (HTML)
# -------------------------------------------------------------------------
@login_required
def dashboard_page(request):
    """Renders the dashboard HTML (admin/teacher role-aware)."""
    # from .views_helpers import build_dashboard_data  # move helper funcs there to keep clean
    stats = {}  # TODO: Implement build_dashboard_data function

    if getattr(request.user, 'role', None) == 'admin':
        pending_templates = Template.objects.filter(status='pending').count()
        context = {
            'stats': stats,
            'recent_messages': stats.get('recent_messages', []),
            'pending_templates': pending_templates,
        }
        return render(request, 'dashboard_admin.html', context)
    else:
        context = {
            'stats': stats,
            'recent_messages': stats.get('recent_messages', []),
            'templates_count': stats.get('templates_count', 0),
            'groups_count': stats.get('groups_count', 0),
        }
        return render(request, 'dashboard_teacher.html', context)


# -------------------------------------------------------------------------
# ✅ SIDEBAR HTML PARTIAL (used by fetch('/sidebar/'))
# -------------------------------------------------------------------------
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

@login_required
@vary_on_cookie           # Different cache per user session
@cache_page(60 * 60)      # Cache for 1 hour
def sidebar_view(request):
    """Sidebar partial HTML, loaded dynamically into each page."""
    role = getattr(request.user, 'role', 'teacher')
    return render(request, 'partials/sidebar.html', {'role': role})


# sms/views.py
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import StudentContact, Group, Template

@login_required
def get_contacts(request):
    user = request.user
    if user.role == "admin":
        contacts = StudentContact.objects.all()
    elif user.assigned_class:
        contacts = StudentContact.objects.filter(class_dept=user.assigned_class)
    else:
        contacts = StudentContact.objects.none()

    return JsonResponse(list(contacts.values()), safe=False)


@login_required
def get_groups(request):
    user = request.user
    if user.role == "admin":
        groups = Group.objects.all()
    elif user.assigned_class:
        groups = Group.objects.filter(class_dept=user.assigned_class)
    else:
        # Teachers see their own groups
        groups = Group.objects.filter(teacher=user)

    # Include contact count in response
    groups_data = []
    for g in groups:
        groups_data.append({
            'id': g.id,
            'name': g.name,
            'class_dept': g.class_dept,
            'description': g.description,
            'created_at': g.created_at.isoformat(),
            'teacher_id': g.teacher.id,
            'teacher_name': g.teacher.username,
            'contacts_count': g.contacts.count(),
            'is_active': True  # Add if you have this field
        })

    return JsonResponse(groups_data, safe=False)


@login_required
def create_group(request):
    """Create a new group"""
    if request.method != 'POST':
        return JsonResponse({"error": "Only POST method allowed"}, status=405)
    
    try:
        import json
        data = json.loads(request.body)
        
        name = data.get('name', '').strip()
        category = data.get('category', '').strip()
        description = data.get('description', '').strip()
        
        if not name:
            return JsonResponse({"error": "Group name is required"}, status=400)
        
        if not category:
            return JsonResponse({"error": "Category is required"}, status=400)
            
        # Check if group with same name already exists for this teacher
        if Group.objects.filter(name=name, teacher=request.user).exists():
            return JsonResponse({"error": "Group with this name already exists"}, status=400)
        
        # Create the group
        group = Group.objects.create(
            name=name,
            class_dept=category,  # Store category in class_dept
            description=description,
            teacher=request.user
        )
        
        return JsonResponse({
            "success": True,
            "message": "Group created successfully",
            "group": {
                "id": group.id,
                "name": group.name,
                "class_dept": group.class_dept,
                "description": group.description,
                "contacts": 0,  # New group starts with 0 contacts
                "created_at": group.created_at.isoformat() if hasattr(group, 'created_at') else None,
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def get_group_contacts(request, group_id):
    """Get all contacts in a specific group"""
    try:
        group = Group.objects.get(id=group_id)
        
        # Check permission
        if request.user.role != 'admin' and group.teacher != request.user:
            return JsonResponse({"error": "Permission denied"}, status=403)
        
        contacts = StudentContact.objects.filter(class_dept=group)
        contacts_data = [{
            'id': c.id,
            'name': c.name,
            'phone_number': c.phone_number,
            'meta': c.meta or {},
            'created_at': c.created_at.isoformat()
        } for c in contacts]
        
        return JsonResponse({
            'group_id': group.id,
            'group_name': group.name,
            'contacts': contacts_data
        })
    except Group.DoesNotExist:
        return JsonResponse({"error": "Group not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def add_contacts_to_group(request, group_id):
    """Add contacts to a group (manual or from another group)"""
    if request.method != 'POST':
        return JsonResponse({"error": "POST only"}, status=405)
    
    try:
        group = Group.objects.get(id=group_id)
        
        # Check permission
        if request.user.role != 'admin' and group.teacher != request.user:
            return JsonResponse({"error": "Permission denied"}, status=403)
        
        data = json.loads(request.body)
        contacts_data = data.get('contacts', [])
        source_group_id = data.get('source_group_id')
        
        added_count = 0
        errors = []
        
        # If copying from another group
        if source_group_id:
            try:
                source_group = Group.objects.get(id=source_group_id)
                source_contacts = StudentContact.objects.filter(class_dept=source_group)
                
                for contact in source_contacts:
                    try:
                        StudentContact.objects.create(
                            name=contact.name,
                            phone_number=contact.phone_number,
                            class_dept=group,
                            meta=contact.meta
                        )
                        added_count += 1
                    except Exception as e:
                        errors.append(f"{contact.name}: {str(e)}")
            except Group.DoesNotExist:
                return JsonResponse({"error": "Source group not found"}, status=404)
        
        # Add individual contacts
        for contact_data in contacts_data:
            name = contact_data.get('name', '').strip()
            phone = contact_data.get('phone_number', '').strip()
            
            if not name or not phone:
                errors.append(f"Missing name or phone for: {name or phone}")
                continue
            
            try:
                StudentContact.objects.create(
                    name=name,
                    phone_number=phone,
                    class_dept=group,
                    meta=contact_data.get('meta', {})
                )
                added_count += 1
            except Exception as e:
                errors.append(f"{name}: {str(e)}")
        
        return JsonResponse({
            "success": True,
            "message": f"Added {added_count} contacts",
            "added_count": added_count,
            "errors": errors
        })
        
    except Group.DoesNotExist:
        return JsonResponse({"error": "Group not found"}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def import_contacts_excel(request, group_id):
    """Import contacts from Excel file"""
    if request.method != 'POST':
        return JsonResponse({"error": "POST only"}, status=405)
    
    try:
        import pandas as pd
        from io import BytesIO
        
        group = Group.objects.get(id=group_id)
        
        # Check permission
        if request.user.role != 'admin' and group.teacher != request.user:
            return JsonResponse({"error": "Permission denied"}, status=403)
        
        if 'file' not in request.FILES:
            return JsonResponse({"error": "No file uploaded"}, status=400)
        
        excel_file = request.FILES['file']
        
        # Read Excel file
        df = pd.read_excel(BytesIO(excel_file.read()))
        
        # Expected columns: name, phone_number (or phone)
        if 'name' not in df.columns or ('phone_number' not in df.columns and 'phone' not in df.columns):
            return JsonResponse({
                "error": "Excel must have 'name' and 'phone_number' (or 'phone') columns"
            }, status=400)
        
        phone_col = 'phone_number' if 'phone_number' in df.columns else 'phone'
        
        added_count = 0
        errors = []
        
        for index, row in df.iterrows():
            name = str(row.get('name', '')).strip()
            phone = str(row.get(phone_col, '')).strip()
            
            if not name or not phone or phone == 'nan':
                errors.append(f"Row {index + 2}: Missing name or phone")
                continue
            
            try:
                StudentContact.objects.create(
                    name=name,
                    phone_number=phone,
                    class_dept=group,
                    meta={}
                )
                added_count += 1
            except Exception as e:
                errors.append(f"Row {index + 2} ({name}): {str(e)}")
        
        return JsonResponse({
            "success": True,
            "message": f"Imported {added_count} contacts from Excel",
            "added_count": added_count,
            "errors": errors[:10]  # Limit error messages
        })
        
    except Group.DoesNotExist:
        return JsonResponse({"error": "Group not found"}, status=404)
    except ImportError:
        return JsonResponse({"error": "pandas library not installed. Run: pip install pandas openpyxl"}, status=500)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def delete_contact_from_group(request, contact_id):
    """Delete a contact from a group"""
    if request.method != 'POST':
        return JsonResponse({"error": "POST only"}, status=405)
    
    try:
        contact = StudentContact.objects.get(id=contact_id)
        group = contact.class_dept
        
        # Check permission
        if request.user.role != 'admin' and group.teacher != request.user:
            return JsonResponse({"error": "Permission denied"}, status=403)
        
        contact.delete()
        
        return JsonResponse({
            "success": True,
            "message": "Contact deleted successfully"
        })
        
    except StudentContact.DoesNotExist:
        return JsonResponse({"error": "Contact not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


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
        
        # Get recent activity (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        if user.role == "admin":
            recent_messages = SMSMessage.objects.filter(
                created_at__gte=thirty_days_ago
            ).count()
        else:
            recent_messages = SMSMessage.objects.filter(
                user=user,
                created_at__gte=thirty_days_ago
            ).count()
        
        return JsonResponse({
            "totalMessages": total_messages,
            "totalCampaigns": total_campaigns,
            "totalUsers": total_users,
            "recentMessages": recent_messages,
            "deliveryRate": 95.2,  # Mock data - you can calculate this from actual data
            "engagementRate": 78.5  # Mock data
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
        if date_range == 'last30':
            start_dt = timezone.now() - timedelta(days=30)
            end_dt = timezone.now()
        elif date_range == 'last7':
            start_dt = timezone.now() - timedelta(days=7)
            end_dt = timezone.now()
        elif date_range == 'custom' and start_date and end_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        else:
            start_dt = timezone.now() - timedelta(days=30)
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
        
        # Generate mock report data (you can replace with actual calculations)
        if report_type == 'delivery':
            data = {
                "labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                "delivered": [120, 190, 300, 500, 200, 300, 450],
                "failed": [10, 15, 20, 25, 15, 20, 30]
            }
        elif report_type == 'usage':
            data = {
                "labels": ["Week 1", "Week 2", "Week 3", "Week 4"],
                "sent": [1200, 1900, 3000, 2200],
                "delivered": [1150, 1820, 2850, 2100]
            }
        else:
            data = {
                "message": "Report type not supported yet",
                "available_types": ["delivery", "usage"]
            }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def get_templates(request):
    """Admins see all templates; teachers see their own templates and approved ones."""
    user = request.user
    if user.role == "admin":
        templates = Template.objects.all()
    else:
        # Teachers can see their own templates and approved templates
        templates = Template.objects.filter(
            Q(user=user) | Q(status='approved')
        ).distinct()

    return JsonResponse(list(templates.values()), safe=False)

from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from sms.models import Campaign

from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json
from sms.models import Campaign

@login_required
def get_campaigns(request):
    """Return user's campaigns (latest first)."""
    campaigns = Campaign.objects.filter(user=request.user).order_by('-created_at')
    data = [
        {
            "id": c.id,
            "title": c.title or f"Untitled Campaign {c.id}",
            "status": c.status or "draft",
            "created_at": c.created_at.strftime("%Y-%m-%d %H:%M")
        }
        for c in campaigns
    ]
    return JsonResponse(data, safe=False)

@csrf_exempt
@login_required
def create_campaign(request):
    """Create a new campaign."""
    print("Create_campaign called")
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            title = data.get('title', '').strip() or None

            if not title:
                # Auto title fallback if blank
                from django.utils import timezone
                title = f"Campaign {timezone.now().strftime('%d %b %Y %H:%M')}"

            campaign = Campaign.objects.create(
                user=request.user,
                title=title,
                status='draft'
            )
            return JsonResponse({
                "id": campaign.id,
                "title": campaign.title,
                "status": campaign.status,
                "created_at": campaign.created_at.strftime("%Y-%m-%d %H:%M")
            })
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "POST only"}, status=405)


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
        from .services import MySMSMantraService
        
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


@login_required
def get_send_page_stats(request):
    """Get statistics for send SMS page (user-specific for teachers)"""
    if request.method != 'GET':
        return JsonResponse({"error": "GET only"}, status=405)
    
    try:
        from django.db.models import Sum, Count, Q
        from datetime import date
        
        user = request.user
        today = timezone.now().date()
        
        # Filter campaigns by user role (same approach as message history)
        if user.role == 'admin':
            # Admin sees all campaigns
            campaigns_query = Campaign.objects.all()
        else:
            # Teachers only see their own campaigns
            campaigns_query = Campaign.objects.filter(user=user)
        
        # Get messages sent today by this user (use timezone-aware date range)
        from datetime import datetime, timedelta
        
        # Create timezone-aware start and end of today
        today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        today_end = timezone.make_aware(datetime.combine(today, datetime.max.time()))
        
        if user.role == 'admin':
            # Admin sees all messages sent today
            today_messages = SMSMessage.objects.filter(
                sent_at__gte=today_start,
                sent_at__lte=today_end
            )
        else:
            # Teachers see only their own messages sent today
            today_messages = SMSMessage.objects.filter(
                user=user,
                sent_at__gte=today_start,
                sent_at__lte=today_end
            )
        
        # Count total recipients from today's messages (actual SMS sent)
        successful = today_messages.aggregate(total=Sum('successful_deliveries'))['total'] or 0
        failed = today_messages.aggregate(total=Sum('failed_deliveries'))['total'] or 0
        today_count = successful + failed
        
        # Get user's SMS usage stats
        try:
            usage_stats = SMSUsageStats.objects.get(user=user)
            remaining_credits = usage_stats.remaining_credits
        except SMSUsageStats.DoesNotExist:
            remaining_credits = 0
        
        # Calculate delivery rate from all campaigns (same as message history)
        all_campaigns = campaigns_query.all()
        
        total_sent = sum(camp.total_sent or 0 for camp in all_campaigns)
        total_delivered = sum(camp.total_delivered or 0 for camp in all_campaigns)
        
        delivery_rate = round((total_delivered / total_sent * 100), 1) if total_sent > 0 else 0
        
        return JsonResponse({
            "today_count": today_count,
            "remaining_credits": remaining_credits,
            "delivery_rate": delivery_rate,
            "cost_per_sms": 0.15  # Fixed cost
        })
    
    except Exception as e:
        logger.exception("Error getting send page stats")
        return JsonResponse({"error": str(e)}, status=500)
