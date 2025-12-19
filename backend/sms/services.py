import httpx
from django.conf import settings
from django.utils import timezone
from .models import SMSMessage, Template, Group, SMSRecipient
import logging

logger = logging.getLogger(__name__)


class MySMSMantraService:
    """
    Official MySMSMantra v2 API Service
    Safe, defensive, and production-ready
    """

    SEND_SMS_PATH = "/api/v2/SendSMS"
    HISTORY_PATH = "/api/v2/messageStatus"

    def __init__(self, user=None):
        self.user = user
        self.base_url = settings.MYSMSMANTRA_CONFIG["API_URL"].rstrip("/")

    # ------------------------------------------------------------------
    # 🔑 Credentials
    # ------------------------------------------------------------------
    def get_user_credentials(self):
        creds = {
            "api_key": settings.MYSMSMANTRA_CONFIG.get("API_KEY"),
            "client_id": settings.MYSMSMANTRA_CONFIG.get("CLIENT_ID"),
            "sender_id": settings.MYSMSMANTRA_CONFIG.get("SENDER_ID"),
        }

        if not creds["api_key"] or not creds["client_id"]:
            raise ValueError("MySMSMantra credentials missing")

        return creds

    # ------------------------------------------------------------------
    # 🚀 Send SMS
    # ------------------------------------------------------------------
    def send_sms_sync(self, sms_message_id, message_text, recipients_list, sender_id=None):
        sms_message = SMSMessage.objects.get(id=sms_message_id)
        creds = self.get_user_credentials()

        params = {
            "ApiKey": creds["api_key"],
            "ClientId": creds["client_id"],
            "SenderId": sender_id or creds["sender_id"],
            "Message": message_text,
            "MobileNumbers": ",".join(recipients_list),
        }

        url = f"{self.base_url}{self.SEND_SMS_PATH}"

        try:
            logger.info(f"Sending SMS → {len(recipients_list)} recipients")

            with httpx.Client(timeout=30) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()

                try:
                    data = resp.json()
                except Exception:
                    data = {
                        "ErrorCode": -1,
                        "ErrorDescription": resp.text,
                    }

        except Exception as e:
            logger.exception("SMS send failed")
            self.update_sms_message_error(sms_message_id, str(e))
            return {"success": False, "error": str(e)}

        self.update_sms_message(sms_message, data, recipients_list)

        return {
            "success": self.is_successful_response(data),
            "api_response": data,
            "message_id": sms_message.id,
        }

    # ------------------------------------------------------------------
    # 🧾 Message History
    # ------------------------------------------------------------------
    def get_sms_history(self, start=0, length=50, fromdate=None, enddate=None):
        creds = self.get_user_credentials()

        params = {
            "ApiKey": creds["api_key"],
            "ClientId": creds["client_id"],
            "start": start,
            "length": length,
        }

        if fromdate:
            params["fromdate"] = fromdate
        if enddate:
            params["enddate"] = enddate

        url = f"{self.base_url}{self.HISTORY_PATH}"

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                return {"success": True, "history": resp.json()}

        except Exception as e:
            logger.exception("History fetch failed")
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # 🛠 Update message after SendSMS
    # ------------------------------------------------------------------
    def update_sms_message(self, sms_message, api_response, recipients_list):
        """Update SMS message and create recipient logs from API response.
        
        This now properly saves api_message_id for each recipient from the API's Data array.
        Recipients are saved with 'pending' status - actual delivery status is checked later.
        """
        sms_message.refresh_from_db()
        sms_message.api_response = api_response
        sms_message.sent_at = timezone.now()

        submitted_count = 0
        rejected_count = 0

        error_code = api_response.get("ErrorCode")

        # Check if API accepted the request
        if error_code in [0, "0"]:
            # API returned per-recipient data with MessageId
            api_data = api_response.get("Data", [])
            
            if isinstance(api_data, list) and api_data:
                # Process each recipient from API response
                for entry in api_data:
                    phone = entry.get("MobileNumber")
                    api_msg_id = entry.get("MessageId")
                    msg_error_code = entry.get("MessageErrorCode")
                    msg_error_desc = entry.get("MessageErrorDescription")
                    
                    if msg_error_code == 0:
                        # Message accepted by API
                        SMSRecipient.objects.update_or_create(
                            message=sms_message,
                            phone_number=phone,
                            defaults={
                                "status": "pending",
                                "api_message_id": api_msg_id,
                                "submit_time": timezone.now(),
                                "error_description": None,
                            },
                        )
                        submitted_count += 1
                    else:
                        # Message rejected by API for this recipient
                        SMSRecipient.objects.update_or_create(
                            message=sms_message,
                            phone_number=phone,
                            defaults={
                                "status": "submit_failed",
                                "api_message_id": api_msg_id,
                                "submit_time": None,
                                "error_description": msg_error_desc,
                            },
                        )
                        rejected_count += 1
            else:
                # Fallback: API didn't return per-recipient data
                for phone in recipients_list:
                    SMSRecipient.objects.update_or_create(
                        message=sms_message,
                        phone_number=phone,
                        defaults={"status": "pending", "submit_time": timezone.now()},
                    )
                submitted_count = len(recipients_list)
        else:
            # Entire API request failed
            for phone in recipients_list:
                SMSRecipient.objects.update_or_create(
                    message=sms_message,
                    phone_number=phone,
                    defaults={
                        "status": "submit_failed",
                        "error_description": api_response.get("ErrorDescription"),
                    },
                )
            rejected_count = len(recipients_list)

        # Update message totals - don't mark as delivered yet, just submitted
        sms_message.successful_deliveries = 0  # Will be updated on status refresh
        sms_message.failed_deliveries = rejected_count
        sms_message.status = "submitted" if submitted_count > 0 else "failed"
        sms_message.save()
        
        logger.info(f"📤 SMS {sms_message.id}: Submitted={submitted_count}, Rejected={rejected_count}")

    # ------------------------------------------------------------------
    # 🔄 Get individual message status by MessageId
    # ------------------------------------------------------------------
    def get_individual_message_status(self, message_id):
        """
        Check delivery status for a single message using its MessageId.
        Uses the api/v2/MessageStatus endpoint.
        """
        creds = self.get_user_credentials()
        
        params = {
            "ApiKey": creds["api_key"],
            "ClientId": creds["client_id"],
            "MessageId": message_id,
        }
        
        url = f"{self.base_url}{self.HISTORY_PATH}"
        
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                
                error_code = data.get("ErrorCode")
                if str(error_code) == "0":
                    msg_data = data.get("Data", {})
                    return {
                        "success": True,
                        "MobileNumber": msg_data.get("MobileNumber"),
                        "Status": msg_data.get("Status"),
                        "SubmitDate": msg_data.get("SubmitDate"),
                        "DoneDate": msg_data.get("DoneDate"),
                    }
                else:
                    return {
                        "success": False,
                        "error": data.get("ErrorDescription", "Unknown error"),
                        "error_code": error_code,
                    }
                    
        except Exception as e:
            logger.exception(f"Failed to get status for MessageId {message_id}")
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # 🔄 Refresh delivery status - Queue style (individual API calls)
    # ------------------------------------------------------------------
    def refresh_message_status(self, sms_message_id):
        """
        Refresh delivery status for all recipients of a message.
        Makes individual API calls to api/v2/MessageStatus for each recipient.
        Updates status to delivered/failed based on API response.
        """
        try:
            sms_message = SMSMessage.objects.get(id=sms_message_id)
            recipients = list(sms_message.recipient_logs.filter(
                api_message_id__isnull=False
            ).exclude(api_message_id=''))

            if not recipients:
                return {"success": False, "error": "No recipients with message IDs found"}

            # Status codes mapping
            delivered_codes = {"DELIVRD", "DELIVERED", "SUCCESS"}
            submitted_codes = {"SUBMITTED", "SENT", "PENDING", "ACCEPTED"}
            failed_codes = {"UNDELIV", "FAILED", "REJECTD", "REJECTED", "EXPIRED", "ERROR"}

            updated = 0
            delivered_count = 0
            failed_count = 0
            pending_count = 0
            errors = []

            logger.info(f"🔄 Refreshing status for {len(recipients)} recipients (Message ID: {sms_message_id})")

            for recipient in recipients:
                if not recipient.api_message_id:
                    continue
                    
                # Call API for this specific recipient
                result = self.get_individual_message_status(recipient.api_message_id)
                
                if result.get("success"):
                    status_text = (result.get("Status") or "").upper()
                    
                    if status_text in delivered_codes:
                        recipient.status = "delivered"
                        recipient.delivery_time = timezone.now()
                        recipient.error_description = None
                        delivered_count += 1
                    elif status_text in failed_codes:
                        recipient.status = "failed"
                        recipient.error_description = status_text
                        failed_count += 1
                    elif status_text in submitted_codes:
                        recipient.status = "pending"
                        pending_count += 1
                    else:
                        # Unknown status, keep as pending
                        recipient.status = "pending"
                        recipient.error_description = f"Status: {status_text}"
                        pending_count += 1
                    
                    recipient.save()
                    updated += 1
                    logger.debug(f"  📱 {recipient.phone_number}: {status_text} → {recipient.status}")
                else:
                    # API call failed for this recipient
                    error_msg = result.get("error", "Unknown error")
                    errors.append(f"{recipient.phone_number}: {error_msg}")
                    logger.warning(f"  ⚠️ {recipient.phone_number}: API error - {error_msg}")

            # Update SMSMessage totals
            total_delivered = sms_message.recipient_logs.filter(status="delivered").count()
            total_failed = sms_message.recipient_logs.filter(status__in=["failed", "submit_failed"]).count()
            total_pending = sms_message.recipient_logs.filter(status="pending").count()

            sms_message.successful_deliveries = total_delivered
            sms_message.failed_deliveries = total_failed

            # Update status based on results
            if total_pending == 0:
                # All statuses resolved
                if total_failed == 0:
                    sms_message.status = "sent"
                elif total_delivered == 0:
                    sms_message.status = "failed"
                else:
                    sms_message.status = "partial"
            else:
                sms_message.status = "submitted"  # Still waiting for some

            sms_message.save()

            # Update Campaign stats
            if sms_message.campaign:
                campaign = sms_message.campaign
                campaign.total_delivered = total_delivered
                campaign.total_failed = total_failed
                
                if total_pending == 0:
                    campaign.status = "completed" if total_failed == 0 else "partial"
                
                campaign.save()

            logger.info(f"✅ Status refresh complete: Delivered={total_delivered}, Failed={total_failed}, Pending={total_pending}")

            return {
                "success": True,
                "updated": updated,
                "delivered": total_delivered,
                "failed": total_failed,
                "pending": total_pending,
                "successful": total_delivered,  # For backward compatibility
                "errors": errors if errors else None,
            }

        except SMSMessage.DoesNotExist:
            return {"success": False, "error": "Message not found"}
        except Exception as e:
            logger.exception("Status refresh failed")
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # ✅ Success evaluation
    # ------------------------------------------------------------------
    def is_successful_response(self, api_response):
        return (
            isinstance(api_response, dict)
            and api_response.get("ErrorCode") in [0, "0"]
        )

    # ------------------------------------------------------------------
    # ❌ Hard failure
    # ------------------------------------------------------------------
    def update_sms_message_error(self, sms_message_id, error_message):
        try:
            sms_message = SMSMessage.objects.get(id=sms_message_id)
            sms_message.status = "failed"
            sms_message.api_response = {"error": error_message}
            sms_message.failed_deliveries = sms_message.total_recipients
            sms_message.successful_deliveries = 0
            sms_message.save()
        except SMSMessage.DoesNotExist:
            logger.error(f"SMS {sms_message_id} not found")


# -------------------------------------------------------------------
# Public Utility Function
# -------------------------------------------------------------------
def send_sms_message(user, message_text, recipients_list, sender_id=None, template_id=None):
    """Public wrapper to send SMS synchronously via MySMSMantra."""
    try:
        sms_message = SMSMessage.objects.create(
            user=user,
            message_text=message_text,
            status="pending",
        )
        sms_message.set_recipients_list(recipients_list)

        service = MySMSMantraService(user=user)
        result = service.send_sms_sync(sms_message.id, message_text, recipients_list, sender_id)

        # send_sms_sync already updates the message via update_sms_message()
        # No need to save again here
        return result

    except Exception as e:
        logger.error(f"Error in send_sms_message: {e}")
        return {"success": False, "error": str(e)}


class AdminAnalyticsService:
    """Service to provide admin-wide analytics and activity logs.

    This keeps aggregation and data-fetching logic in the service layer so
    views/controllers can remain thin and focused on presentation.
    """

    def __init__(self, user=None):
        self.user = user

    def get_admin_totals(self):
        """Return aggregate counts across the system.

        Returns a dict with keys: total_users, total_sms, total_templates, total_groups
        """
        try:
            from django.contrib.auth import get_user_model
            UserModel = get_user_model()
            total_users = UserModel.objects.count()
        except Exception:
            total_users = 0

        try:
            total_sms = SMSMessage.objects.count()
        except Exception:
            total_sms = 0

        try:
            total_templates = Template.objects.count()
        except Exception:
            total_templates = 0

        try:
            total_groups = Group.objects.count()
        except Exception:
            total_groups = 0

        return {
            'total_users': total_users,
            'total_sms': total_sms,
            'total_templates': total_templates,
            'total_groups': total_groups,
        }

    def get_activity_logs(self, start=0, length=50):
        """Return a paginated list of recent activity log entries.

        Currently this builds a lightweight activity list from `SMSMessage` entries.
        You can later extend to include auth events, API requests, etc.

        Returns: list of dicts: {id, timestamp, level, category, action, user, details}
        """
        logs = []
        try:
            msgs = SMSMessage.objects.select_related('user').order_by('-created_at')[start:start+length]
            for m in msgs:
                sent = getattr(m, 'successful_deliveries', 0) or 0
                failed = getattr(m, 'failed_deliveries', 0) or 0
                total = getattr(m, 'total_recipients', None)
                status = 'success' if m.status == 'sent' else 'failed' if m.status == 'failed' else 'info'

                # Build recipients list for expanded view
                recipients = []
                try:
                    recs = SMSRecipient.objects.filter(message_id=m.id).values('phone_number', 'status', 'error_description')
                    for r in recs:
                        recipients.append({
                            'phone_number': r.get('phone_number'),
                            'status': r.get('status'),
                            'error_description': r.get('error_description')
                        })
                except Exception:
                    recipients = []

                logs.append({
                    'id': m.id,
                    'timestamp': (m.sent_at or m.created_at) if (m.sent_at or m.created_at) else None,
                    'status': status,
                    'category': 'sms',
                    'action': 'SMS sent' if m.status == 'sent' else 'SMS failed',
                    'user': getattr(m.user, 'email', getattr(m.user, 'username', 'system')) if m.user else 'system',
                    'details': f"Recipients: {total or '-'}, Sent: {sent}, Failed: {failed}",
                    'message_text': getattr(m, 'message_text', ''),
                    'recipients': recipients,
                })
        except Exception as e:
            logger.exception("Error building activity logs: %s", e)

        return logs

    # Future helpers: get_monthly_aggregates(), get_user_activity(user_id), export_csv(), etc.

def fetch_total_sent_messages(user):
    """Fetch total number of sent messages for a user."""
    try:
        total_sent = SMSMessage.objects.filter(user=user, status='sent').count()
        return {"success": True, "total_sent_messages": total_sent}
    except Exception as e:
        logger.error(f"Error fetching total sent messages: {e}")
        return {"success": False, "error": str(e)}