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
    from .views_helpers import build_dashboard_data  # move helper funcs there to keep clean
    stats = build_dashboard_data(request.user)

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
def get_templates(request):
    """Admins see all templates; teachers only see ones relevant to their class."""
    user = request.user
    if user.role == "admin":
        templates = Template.objects.all()
    else:
        templates = Template.objects.filter(created_by=user)

    return JsonResponse(list(templates.values()), safe=False)
