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
    Group, StudentContact
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
@login_required
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
        groups = Group.objects.none()

    return JsonResponse(list(groups.values()), safe=False)


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
            
        # Check if group with same name already exists
        if Group.objects.filter(name=name, user=request.user).exists():
            return JsonResponse({"error": "Group with this name already exists"}, status=400)
        
        # Create the group
        group = Group.objects.create(
            name=name,
            category=category,
            description=description,
            user=request.user,
            is_active=True
        )
        
        return JsonResponse({
            "success": True,
            "message": "Group created successfully",
            "group": {
                "id": group.id,
                "name": group.name,
                "category": group.category,
                "description": group.description,
                "contacts": 0,  # New group starts with 0 contacts
                "created_at": group.created_at.isoformat() if hasattr(group, 'created_at') else None,
                "is_active": group.is_active
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)
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
