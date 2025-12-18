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


# =========================================================================
# SMS SENDING API
# =========================================================================

@csrf_exempt
@login_required
def send_sms_api(request):
    """API endpoint for sending SMS via MySMSMantra with campaign tracking."""
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        from .models import Campaign, SMSRecipient
        from .services import MySMSMantraService
        
        data = json.loads(request.body.decode("utf-8"))
        template_id = data.get("template_id")
        recipients = data.get("recipients", [])
        message = data.get("message", "")
        sender_id = data.get("sender_id", "BOMBYS")
        campaign_id = data.get("campaign_id")

        if not recipients:
            return JsonResponse({"error": "No recipients provided"}, status=400)

        # Find or create campaign
        campaign = None
        if campaign_id and str(campaign_id).isdigit():
            try:
                campaign = Campaign.objects.get(id=int(campaign_id), user=request.user)
            except Campaign.DoesNotExist:
                pass

        if not campaign:
            campaign = Campaign.objects.create(
                user=request.user,
                title=f"Campaign {timezone.now().strftime('%d-%b %H:%M')}",
                status="active"
            )

        # Create master SMSMessage record
        sms_message = SMSMessage.objects.create(
            user=request.user,
            campaign=campaign,
            message_text=message,
            recipients=recipients,
            total_recipients=len(recipients),
            status='pending'
        )

        logger.info(f"Sending SMS to {len(recipients)} recipients under campaign {campaign.title}")

        # Send SMS via MySMSMantra API
        service = MySMSMantraService(user=request.user)
        result = service.send_sms_sync(
            sms_message_id=sms_message.id,
            message_text=message,
            recipients_list=recipients,
            sender_id=sender_id
        )

        if not result.get("success"):
            sms_message.status = "failed"
            sms_message.save()
            return JsonResponse({"success": False, "error": result.get("error")}, status=500)

        # Parse API response and save recipient details
        api_data = result.get("api_response", {}).get("Data", [])
        sent_count = 0
        failed_count = 0

        for entry in api_data:
            phone = entry.get("MobileNumber")
            api_msg_id = entry.get("MessageId")
            error_code = entry.get("MessageErrorCode")
            status = "sent" if error_code == 0 else "failed"

            SMSRecipient.objects.create(
                message=sms_message,
                phone_number=phone,
                api_message_id=api_msg_id,
                status=status,
                submit_time=timezone.now() if status == "sent" else None,
                error_description=entry.get("MessageErrorDescription")
            )

            if status == "sent":
                sent_count += 1
            else:
                failed_count += 1

        # Update SMSMessage
        sms_message.status = "sent" if sent_count > 0 else "failed"
        sms_message.sent_at = timezone.now()
        sms_message.successful_deliveries = sent_count
        sms_message.failed_deliveries = failed_count
        sms_message.save()

        # Auto-calculate Campaign statistics
        campaign.update_stats()
        campaign.status = "completed" if campaign.total_failed == 0 else "partial"
        campaign.save()

        logger.info(f"✅ SMS campaign '{campaign.title}' results → Sent={sent_count}, Failed={failed_count}")

        return JsonResponse({
            "success": True,
            "campaign_id": campaign.id,
            "message_id": sms_message.id,
            "delivered": sent_count,
            "failed": failed_count,
            "recipients": len(api_data),
            "api_response": api_data,
        })

    except Exception as e:
        logger.exception("Error in send_sms_api")
        return JsonResponse({"error": str(e)}, status=500)


# =========================================================================
# CONTACTS MANAGEMENT API
# =========================================================================

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
# ✅ API ENDPOINTS
# -------------------------------------------------------------------------

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


# =========================================================================
# GROUPS MANAGEMENT API
# =========================================================================

@login_required
def get_groups(request):
    user = request.user
    # Admins see all groups. Other users see universal groups + their own personal groups.
    if user.role == "admin":
        groups = Group.objects.all()
    else:
        groups = Group.objects.filter(Q(is_universal=True) | Q(teacher=user)).distinct()

    # Include contact count in response
    groups_data = []
    for g in groups:
        groups_data.append({
            'id': g.id,
            'name': g.name,
            'class_dept': g.class_dept,
            'description': g.description,
            'created_at': g.created_at.isoformat(),
            'teacher_id': g.teacher.id if g.teacher else None,
            'teacher_name': g.teacher.username if g.teacher else ('Universal' if g.is_universal else None),
            'contacts_count': g.contacts.count(),
            'is_universal': bool(g.is_universal),
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
        is_universal = bool(data.get('is_universal', False))
        
        if not name:
            return JsonResponse({"error": "Group name is required"}, status=400)
        
        if not category:
            return JsonResponse({"error": "Category is required"}, status=400)
            
        # Admins may create universal groups; non-admins cannot.
        if is_universal and request.user.role != 'admin':
            return JsonResponse({"error": "Only admins can create universal groups"}, status=403)

        # Check duplicate for this scope
        if is_universal:
            if Group.objects.filter(name=name, is_universal=True).exists():
                return JsonResponse({"error": "A universal group with this name already exists"}, status=400)
            group = Group.objects.create(
                name=name,
                class_dept=category,
                description=description,
                is_universal=True,
                teacher=None
            )
        else:
            if Group.objects.filter(name=name, teacher=request.user).exists():
                return JsonResponse({"error": "Group with this name already exists"}, status=400)
            group = Group.objects.create(
                name=name,
                class_dept=category,
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
        # Admins can access any group. Universal groups are readable by everyone.
        if request.user.role != 'admin':
            if group.is_universal:
                # allowed to read universal groups
                pass
            elif group.teacher != request.user:
                return JsonResponse({"error": "Permission denied"}, status=403)
        
        contacts = StudentContact.objects.filter(class_dept=group)
        contacts_data = [{
            'id': c.id,
            'name': c.name,
            'phone_number': c.phone_number,
            'meta': c.meta or {},
            'created_at': c.created_at.isoformat()
        } for c in contacts]
        
        print(contacts_data)

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
        
        # Check permission: only admins or the owning teacher can modify personal groups.
        if group.is_universal and request.user.role != 'admin':
            return JsonResponse({"error": "Permission denied: universal groups are admin-managed"}, status=403)

        if not group.is_universal and request.user.role != 'admin' and group.teacher != request.user:
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
                # If source is universal and user is not admin, copying is allowed (read),
                # but adding into a personal group still must obey permissions for target group above.
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
        
        # Read Excel file - first read without header to find the header row
        df_raw = pd.read_excel(BytesIO(excel_file.read()), header=None)
        
        # Find the header row (row that contains "name" and "phone" keywords)
        header_row = None
        name_col_idx = None
        phone_col_idx = None
        
        for row_idx in range(min(20, len(df_raw))):  # Check first 20 rows
            row_values = df_raw.iloc[row_idx].astype(str).str.lower().str.strip()
            
            # Look for name column
            name_patterns = ['name', 'student', 'contact', 'full']
            for col_idx, val in enumerate(row_values):
                if any(pattern in val for pattern in name_patterns):
                    name_col_idx = col_idx
                    break
            
            # Look for phone column
            phone_patterns = ['phone', 'mobile', 'number', 'contact']
            for col_idx, val in enumerate(row_values):
                if any(pattern in val for pattern in phone_patterns) and col_idx != name_col_idx:
                    phone_col_idx = col_idx
                    break
            
            if name_col_idx is not None and phone_col_idx is not None:
                header_row = row_idx
                break
        
        if header_row is None:
            return JsonResponse({
                "error": "Could not find header row with name and phone columns. Please ensure your Excel has column headers."
            }, status=400)
        
        # Re-read the Excel file with the correct header row
        excel_file.seek(0)  # Reset file pointer
        df = pd.read_excel(BytesIO(excel_file.read()), header=header_row)
        
        # Get the actual column names
        name_col = df.columns[name_col_idx]
        phone_col = df.columns[phone_col_idx]
        
        added_count = 0
        errors = []
        
        for index, row in df.iterrows():
            name = str(row.get(name_col, '')).strip()
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
@login_required
def delete_contact_from_group(request, contact_id):
    """Delete a contact from a group"""
    if request.method != 'DELETE':
        return JsonResponse({"error": "DELETE method required"}, status=405)
    
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
        return JsonResponse({"error": str(e)}, status=500)


# =========================================================================
# REPORTS API
# =========================================================================

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
        
        # Get recent activity (last 7 days for trends)
        from datetime import datetime, timedelta
        today = timezone.now().date()
        delivery_trends = []
        
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            day_start = timezone.make_aware(datetime.combine(day, datetime.min.time()))
            day_end = timezone.make_aware(datetime.combine(day, datetime.max.time()))
            
            if user.role == "admin":
                messages = SMSMessage.objects.filter(
                    created_at__range=[day_start, day_end]
                )
            else:
                messages = SMSMessage.objects.filter(
                    user=user,
                    created_at__range=[day_start, day_end]
                )
            
            sent = messages.count()
            delivered = messages.filter(status='delivered').count()
            failed = messages.filter(status='failed').count()
            
            delivery_trends.append({
                'date': day.strftime('%Y-%m-%d'),
                'sent': sent,
                'delivered': delivered,
                'failed': failed
            })
        
        # Calculate delivery rate
        total_sent = sum(d['sent'] for d in delivery_trends)
        total_delivered = sum(d['delivered'] for d in delivery_trends)
        delivery_rate = (total_delivered / total_sent * 100) if total_sent > 0 else 0
        
        # Get message categories (mock data for now - you can add category field to SMSMessage model)
        categories = [
            {'name': 'Academic', 'count': int(total_messages * 0.41), 'percentage': 41.0},
            {'name': 'Administrative', 'count': int(total_messages * 0.265), 'percentage': 26.5},
            {'name': 'Events', 'count': int(total_messages * 0.196), 'percentage': 19.6},
            {'name': 'Emergency', 'count': int(total_messages * 0.129), 'percentage': 12.9}
        ]
        
        return JsonResponse({
            "stats": {
                "total_sent": total_sent,
                "delivery_rate": round(delivery_rate, 1),
                "failed_count": sum(d['failed'] for d in delivery_trends),
                "active_users": total_users
            },
            "delivery_trends": delivery_trends,
            "categories": categories
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
        if date_range == 'today':
            start_dt = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = timezone.now()
        elif date_range == 'yesterday':
            yesterday = timezone.now() - timedelta(days=1)
            start_dt = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif date_range == 'week':
            start_dt = timezone.now() - timedelta(days=7)
            end_dt = timezone.now()
        elif date_range == 'month':
            start_dt = timezone.now() - timedelta(days=30)
            end_dt = timezone.now()
        elif date_range == 'custom' and start_date and end_date:
            start_dt = timezone.make_aware(datetime.strptime(start_date, '%Y-%m-%d'))
            end_dt = timezone.make_aware(datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
        else:
            # Default to last 7 days
            start_dt = timezone.now() - timedelta(days=7)
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
        
        # Generate report data based on actual database records
        from datetime import datetime, timedelta
        today = timezone.now().date()
        delivery_trends = []
        
        # Get data for last 7 days
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            day_start = timezone.make_aware(datetime.combine(day, datetime.min.time()))
            day_end = timezone.make_aware(datetime.combine(day, datetime.max.time()))
            
            messages = messages_qs.filter(created_at__range=[day_start, day_end])
            sent = messages.count()
            delivered = messages.filter(status='delivered').count()
            failed = messages.filter(status='failed').count()
            
            delivery_trends.append({
                'date': day.strftime('%Y-%m-%d'),
                'sent': sent,
                'delivered': delivered,
                'failed': failed
            })
        
        # Calculate stats
        total_sent = sum(d['sent'] for d in delivery_trends)
        total_delivered = sum(d['delivered'] for d in delivery_trends)
        total_failed = sum(d['failed'] for d in delivery_trends)
        delivery_rate = (total_delivered / total_sent * 100) if total_sent > 0 else 0
        
        # Get categories (mock for now)
        categories = [
            {'name': 'Academic', 'count': int(total_sent * 0.41), 'percentage': 41.0},
            {'name': 'Administrative', 'count': int(total_sent * 0.265), 'percentage': 26.5},
            {'name': 'Events', 'count': int(total_sent * 0.196), 'percentage': 19.6},
            {'name': 'Emergency', 'count': int(total_sent * 0.129), 'percentage': 12.9}
        ]
        
        data = {
            "stats": {
                "total_sent": total_sent,
                "delivery_rate": round(delivery_rate, 1),
                "failed_count": total_failed,
                "active_users": User.objects.filter(role='teacher').count() if user.role == 'admin' else 1
            },
            "delivery_trends": delivery_trends,
            "categories": categories,
            "report_type": report_type
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# =========================================================================
# TEMPLATES API
# =========================================================================

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

# =========================================================================
# CAMPAIGNS API
# =========================================================================

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


@csrf_exempt
@login_required
def refresh_sms_status(request, message_id):
    """Refresh SMS message status from provider API."""
    if request.method != 'POST':
        return JsonResponse({"error": "POST only"}, status=405)
    
    try:
        # Verify message belongs to user (or user is admin)
        sms_message = SMSMessage.objects.get(id=message_id)
        if request.user.role != 'admin' and sms_message.user != request.user:
            return JsonResponse({"error": "Permission denied"}, status=403)
        
        # Call service to refresh status
        from .services import MySMSMantraService
        service = MySMSMantraService(user=request.user)
        result = service.refresh_message_status(message_id)
        
        if result.get("success"):
            return JsonResponse({
                "success": True,
                "message": result.get("message"),
                "successful": result.get("successful", 0),
                "failed": result.get("failed", 0)
            })
        else:
            return JsonResponse({
                "success": False,
                "error": result.get("error", "Failed to refresh status")
            }, status=400)
            
    except SMSMessage.DoesNotExist:
        return JsonResponse({"error": "Message not found"}, status=404)
    except Exception as e:
        logger.error(f"Error refreshing SMS status: {e}")
        return JsonResponse({"error": str(e)}, status=500)


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


# =========================================================================
# DASHBOARD STATISTICS API
# =========================================================================

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
