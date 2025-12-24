"""
API Views for SMS Portal
Handles all JSON API endpoints for the SMS management system.
"""

import json
import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    User, SMSMessage, SenderID, Template, APICredentials, SMSUsageStats,
    Group, StudentContact, Campaign, SMSRecipient
)
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer, UserSerializer,
    SMSMessageSerializer, SenderIDSerializer, TemplateSerializer,
    APICredentialsSerializer, SendSMSSerializer, SMSUsageStatsSerializer,
    DashboardStatsSerializer, ContactSerializer
)
from .services import MySMSMantraService

logger = logging.getLogger(__name__)



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
