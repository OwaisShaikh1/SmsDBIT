from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt    
from django.contrib.auth.decorators import login_required
from django.utils import timezone
import json
import logging
from ..models import Campaign, SMSRecipient, SMSMessage, SMSUsageStats, Template
from ..services import MySMSMantraService
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
        data = json.loads(request.body.decode("utf-8"))
        template_id = data.get("template_id")
        sender_id = data.get("sender_id", "BOMBYS")
        campaign_id = data.get("campaign_id")
        
        # Check for per-contact messages (from Excel import)
        per_contact_messages = data.get("per_contact_messages", False)
        recipients_with_messages = data.get("recipients_with_messages", [])
        
        # Standard mode - same message to all
        recipients = data.get("recipients", [])
        message = data.get("message", "")

        # Determine recipient count and validate
        if per_contact_messages:
            if not recipients_with_messages:
                return JsonResponse({"error": "No recipients with messages provided"}, status=400)
            total_recipients_count = len(recipients_with_messages)
        else:
            if not recipients:
                return JsonResponse({"error": "No recipients provided"}, status=400)
            total_recipients_count = len(recipients)

        # Check credits BEFORE sending (Issue #4 fix)
        try:
            usage_stats = SMSUsageStats.objects.get(user=request.user)
            if usage_stats.remaining_credits < total_recipients_count:
                return JsonResponse({
                    "error": f"Insufficient credits. Required: {total_recipients_count}, Available: {int(usage_stats.remaining_credits)}"
                }, status=400)
        except SMSUsageStats.DoesNotExist:
            return JsonResponse({"error": "No SMS credits allocated to your account. Please contact admin."}, status=400)

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

        # Get template if provided
        template = None
        template_title = None
        if template_id:
            logger.info(f"Template ID received: {template_id}, type: {type(template_id)}")
            try:
                # Allow access to templates from any user (admin-created templates should be accessible)
                template = Template.objects.get(id=template_id)
                template_title = template.title
                logger.info(f"Template found: {template.title} (ID: {template.id})")
            except Template.DoesNotExist:
                logger.warning(f"Template with ID {template_id} not found")
        else:
            logger.info("No template_id provided in request")

        # Handle per-contact messages (different message per recipient)
        if per_contact_messages:
            return send_per_contact_messages(
                request, campaign, template, template_title,
                recipients_with_messages, sender_id
            )

        # Standard mode - same message to all recipients
        # Create master SMSMessage record
        sms_message = SMSMessage.objects.create(
            user=request.user,
            campaign=campaign,
            template=template,
            title=template_title,
            message_text=message,
            recipients=recipients,
            total_recipients=len(recipients),
            status='pending'
        )
        
        logger.info(f"Created SMSMessage ID {sms_message.id}: template={sms_message.template_id}, title={sms_message.title}")

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

        # Recipients are now created by update_sms_message() in the service
        # with proper api_message_id for each recipient
        sms_message.refresh_from_db()
        
        # Get counts from the created recipient logs
        submitted_count = sms_message.recipient_logs.filter(status="pending").count()
        submit_failed_count = sms_message.recipient_logs.filter(status="submit_failed").count()

        # Update Campaign to 'active' - not completed until we check status
        campaign.total_recipients = sms_message.total_recipients
        campaign.total_sent = submitted_count
        campaign.status = "active"
        campaign.save()

        logger.info(f"📤 SMS campaign '{campaign.title}' submitted → Accepted={submitted_count}, Rejected={submit_failed_count}")

        # Deduct credits after successful send (Issue #3 fix)
        try:
            usage_stats, _ = SMSUsageStats.objects.get_or_create(
                user=request.user,
                defaults={'remaining_credits': 0, 'total_sent': 0, 'total_delivered': 0, 'total_failed': 0}
            )
            usage_stats.remaining_credits -= submitted_count
            usage_stats.total_sent += submitted_count
            usage_stats.save()
            logger.info(f"💰 Credits deducted: {submitted_count}, Remaining: {usage_stats.remaining_credits}")
        except Exception as e:
            logger.warning(f"Failed to update usage stats: {e}")

        return JsonResponse({
            "success": True,
            "campaign_id": campaign.id,
            "message_id": sms_message.id,
            "submitted": submitted_count,
            "rejected": submit_failed_count,
            "recipients": sms_message.total_recipients,
            "redirect_to": "/history/",
        })

    except Exception as e:
        logger.exception("Error in send_sms_api")
        return JsonResponse({"error": str(e)}, status=500)


def send_per_contact_messages(request, campaign, template, template_title, recipients_with_messages, sender_id):
    """
    Send SMS with per-contact personalized messages.
    Each recipient gets a unique message based on their Excel data.
    This sends messages one-by-one to support different content per recipient.
    """
    service = MySMSMantraService(user=request.user)
    
    total_count = len(recipients_with_messages)
    submitted_count = 0
    rejected_count = 0
    
    # Create a master SMSMessage to track the batch
    # Store the first message as the template reference
    first_message = recipients_with_messages[0].get("message", "") if recipients_with_messages else ""
    all_phones = [r.get("phone") for r in recipients_with_messages]
    
    sms_message = SMSMessage.objects.create(
        user=request.user,
        campaign=campaign,
        template=template,
        title=template_title or "Personalized Messages",
        message_text=first_message + " (personalized)",
        recipients=all_phones,
        total_recipients=total_count,
        status='pending'
    )
    
    logger.info(f"Sending {total_count} personalized SMS under campaign {campaign.title}")
    
    # Send each message individually
    for recipient in recipients_with_messages:
        phone = recipient.get("phone", "").strip()
        message = recipient.get("message", "").strip()
        
        if not phone or not message:
            rejected_count += 1
            SMSRecipient.objects.create(
                message=sms_message,
                phone_number=phone or "UNKNOWN",
                status="submit_failed",
                error_message="Missing phone or message"
            )
            continue
        
        try:
            # Send single SMS
            creds = service.get_user_credentials()
            import httpx
            params = {
                "ApiKey": creds["api_key"],
                "ClientId": creds["client_id"],
                "SenderId": sender_id or creds["sender_id"],
                "Message": message,
                "MobileNumbers": phone,
            }
            
            url = f"{service.base_url}{service.SEND_SMS_PATH}"
            
            with httpx.Client(timeout=30) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                
                try:
                    data = resp.json()
                except Exception:
                    data = {"ErrorCode": -1, "ErrorDescription": resp.text}
            
            # Process response for single recipient
            error_code = data.get("ErrorCode")
            if error_code in [0, "0"]:
                api_data = data.get("Data", [])
                if api_data and isinstance(api_data, list):
                    entry = api_data[0]
                    api_msg_id = entry.get("MessageId")
                    msg_error_code = entry.get("MessageErrorCode")
                    
                    if msg_error_code == 0:
                        SMSRecipient.objects.create(
                            message=sms_message,
                            phone_number=phone,
                            api_message_id=api_msg_id,
                            status="pending",
                            personalized_message=message
                        )
                        submitted_count += 1
                    else:
                        SMSRecipient.objects.create(
                            message=sms_message,
                            phone_number=phone,
                            status="submit_failed",
                            error_message=entry.get("MessageErrorDescription", "Rejected by provider"),
                            error_code=str(msg_error_code)
                        )
                        rejected_count += 1
                else:
                    # Fallback - assume success if ErrorCode is 0
                    SMSRecipient.objects.create(
                        message=sms_message,
                        phone_number=phone,
                        status="pending",
                        personalized_message=message
                    )
                    submitted_count += 1
            else:
                SMSRecipient.objects.create(
                    message=sms_message,
                    phone_number=phone,
                    status="submit_failed",
                    error_message=data.get("ErrorDescription", "API Error"),
                    error_code=str(error_code)
                )
                rejected_count += 1
                
        except Exception as e:
            logger.exception(f"Failed to send SMS to {phone}")
            SMSRecipient.objects.create(
                message=sms_message,
                phone_number=phone,
                status="submit_failed",
                error_message=str(e)
            )
            rejected_count += 1
    
    # Update SMS message status
    sms_message.successful_deliveries = submitted_count
    sms_message.failed_deliveries = rejected_count
    sms_message.status = "sent" if submitted_count > 0 else "failed"
    sms_message.save()
    
    # Update campaign
    campaign.total_recipients = total_count
    campaign.total_sent = submitted_count
    campaign.status = "active"
    campaign.save()
    
    logger.info(f"📤 Personalized SMS campaign '{campaign.title}' → Accepted={submitted_count}, Rejected={rejected_count}")
    
    # Deduct credits
    try:
        usage_stats, _ = SMSUsageStats.objects.get_or_create(
            user=request.user,
            defaults={'remaining_credits': 0, 'total_sent': 0, 'total_delivered': 0, 'total_failed': 0}
        )
        usage_stats.remaining_credits -= submitted_count
        usage_stats.total_sent += submitted_count
        usage_stats.save()
        logger.info(f"💰 Credits deducted: {submitted_count}, Remaining: {usage_stats.remaining_credits}")
    except Exception as e:
        logger.warning(f"Failed to update usage stats: {e}")
    
    return JsonResponse({
        "success": True,
        "campaign_id": campaign.id,
        "message_id": sms_message.id,
        "submitted": submitted_count,
        "rejected": rejected_count,
        "recipients": total_count,
        "personalized": True,
        "redirect_to": "/history/",
    })


@csrf_exempt
@login_required
def refresh_sms_status(request, message_id):
    """
    Refresh SMS message status from provider API.
    Makes individual API calls for each recipient's MessageId.
    """
    if request.method != 'POST':
        return JsonResponse({"error": "POST only"}, status=405)
    
    try:
        # Verify message belongs to user (or user is admin)
        sms_message = SMSMessage.objects.get(id=message_id)
        if request.user.role != 'admin' and sms_message.user != request.user:
            return JsonResponse({"error": "Permission denied"}, status=403)
        
        # Call service to refresh status for each recipient individually
        
        service = MySMSMantraService(user=request.user)
        result = service.refresh_message_status(message_id)
        
        if result.get("success"):
            return JsonResponse({
                "success": True,
                "message": "Status refreshed successfully",
                "delivered": result.get("delivered", 0),
                "failed": result.get("failed", 0),
                "pending": result.get("pending", 0),
                "updated": result.get("updated", 0),
                "successful": result.get("delivered", 0),  # Backward compatibility
                "errors": result.get("errors"),
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

