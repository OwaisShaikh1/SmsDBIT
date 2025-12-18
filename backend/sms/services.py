import httpx
from django.conf import settings
from django.utils import timezone
from .models import SMSMessage, Template, Group, SMSRecipient
import logging

logger = logging.getLogger(__name__)


class MySMSMantraService:
    """Service class for interacting with MySMSMantra API (GET-based confirmed method)."""

    def __init__(self, user=None):
        self.user = user
        self.api_url = settings.MYSMSMANTRA_CONFIG['API_URL']
        # ✅ Official MySMSMantra History Endpoint
        self.history_url = settings.MYSMSMANTRA_CONFIG.get(
            'HISTORY_URL', 'https://api.mylogin.co.in/api/v2/SMS'
        )

    # ------------------------------------------------------------------
    #  🔑 Get credentials
    # ------------------------------------------------------------------
    def get_user_credentials(self):
        """Fetch credentials from .env (primary)."""
        env_credentials = {
            'api_key': settings.MYSMSMANTRA_CONFIG['API_KEY'],
            'client_id': settings.MYSMSMANTRA_CONFIG['CLIENT_ID'],
            'sender_id': settings.MYSMSMANTRA_CONFIG['SENDER_ID'],
        }

        if not env_credentials['api_key'] or not env_credentials['client_id']:
            raise ValueError(
                "MySMSMantra credentials missing in .env. "
                "Please set MYSMSMANTRA_API_KEY and MYSMSMANTRA_CLIENT_ID."
            )

        return env_credentials

    # ------------------------------------------------------------------
    #  🚀 Send SMS
    # ------------------------------------------------------------------
    def send_sms_sync(self, sms_message_id, message_text, recipients_list, sender_id=None):
        """Send SMS using verified GET format."""
        sms_message = SMSMessage.objects.get(id=sms_message_id)
        credentials = self.get_user_credentials()
        sender = sender_id or credentials['sender_id']

        params = {
            "ApiKey": credentials['api_key'],
            "ClientId": credentials['client_id'],
            "SenderId": sender,
            "Message": message_text,
            "MobileNumbers": ",".join(recipients_list),
        }

        # Separate try-catch: API call
        try:
            logger.info(f"Sending SMS via MySMSMantra → {len(recipients_list)} recipient(s)")

            with httpx.Client(timeout=30.0) as client:
                headers = {
                    'Accept': 'application/json'
                }
                response = client.get(f"{self.api_url}/SendSMS", params=params, headers=headers)
                response.raise_for_status()

                try:
                    data = response.json()
                    logger.info(f"MySMSMantra Response: {data}")
                except Exception:
                    data = {"raw_response": response.text, "status_code": response.status_code}
                    logger.warning(f"Non-JSON response: {response.text}")

        except httpx.HTTPError as e:
            logger.error(f"HTTP error while sending SMS: {e}")
            self.update_sms_message_error(sms_message_id, str(e))
            return {"success": False, "error": f"API request failed: {e}", "message_id": sms_message_id}

        except Exception as e:
            logger.error(f"Unexpected error during API call: {e}")
            self.update_sms_message_error(sms_message_id, str(e))
            return {"success": False, "error": str(e), "message_id": sms_message_id}

        # Separate try-catch: Database operations
        try:
            self.update_sms_message(sms_message, data, recipients_list)
            success = self.is_successful_response(data)

            return {
                "success": success,
                "message": success and "SMS sent successfully" or "Failed to send SMS",
                "api_response": data,
                "message_id": sms_message.id,
            }

        except Exception as e:
            logger.error(f"Error saving SMS status to database: {e}")
            return {
                "success": False, 
                "error": f"SMS sent but failed to save status: {e}", 
                "message_id": sms_message_id,
                "api_response": data
            }

    # ------------------------------------------------------------------
    #  🧾 Get Message History
    # ------------------------------------------------------------------
    def get_sms_history(self, start=0, length=50, fromdate=None, enddate=None):
        """Fetch sent SMS history using official MySMSMantra endpoint."""
        credentials = self.get_user_credentials()

        params = {
            "ApiKey": credentials["api_key"],
            "ClientId": credentials["client_id"],
            "start": start,
            "length": length,
        }

        if fromdate:
            params["fromdate"] = fromdate
        if enddate:
            params["enddate"] = enddate

        try:
            logger.info(f"Fetching SMS history from {fromdate} → {enddate}")

            with httpx.Client(timeout=30.0) as client:
                headers = {"Accept": "application/json"}
                response = client.get(self.history_url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()

            logger.info(f"History fetch response: ErrorCode={data.get('ErrorCode')}")
            return {"success": True, "history": data}

        except httpx.HTTPError as e:
            logger.error(f"HTTP error retrieving SMS history: {e}")
            return {"success": False, "error": f"API request failed: {e}"}

        except Exception as e:
            logger.error(f"Unexpected error retrieving SMS history: {e}")
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    #  🛠 Helpers
    # ------------------------------------------------------------------
    def update_sms_message(self, sms_message, api_response, recipients_list):
        """Update SMS message status by checking individual recipient delivery status."""
        sms_message.refresh_from_db()
        sms_message.api_response = api_response
        sms_message.sent_at = timezone.now()

        successful_count = 0
        failed_count = 0

        # Handle response with Data object (single or multiple recipients)
        if isinstance(api_response, dict) and api_response.get("ErrorCode") in [0, "0"]:
            data = api_response.get("Data")
            
            # If Data is a list (multiple recipients)
            if isinstance(data, list):
                for item in data:
                    phone = item.get("MobileNumber", "")
                    message_id = item.get("MessageId", "")
                    error_code = item.get("MessageErrorCode", item.get("ErrorCode", ""))
                    error_desc_text = item.get("MessageErrorDescription", item.get("ErrorDescription", None))
                    
                    # Success if MessageErrorCode is 0
                    is_success = str(error_code) == "0" or error_code == 0
                    
                    # Create/update SMSRecipient record
                    if phone:
                        recipient_status = "sent" if is_success else "failed"
                        error_desc = error_desc_text if error_desc_text and not is_success else None
                        
                        recipient, created = SMSRecipient.objects.update_or_create(
                            message=sms_message,
                            phone_number=phone,
                            defaults={
                                'status': recipient_status,
                                'api_message_id': message_id,
                                'error_description': error_desc,
                                'delivery_time': timezone.now() if is_success else None
                            }
                        )
                        logger.info(f"{'Created' if created else 'Updated'} SMSRecipient: {phone} - {recipient_status} (ID: {recipient.id})")
                        
                        if is_success:
                            successful_count += 1
                        else:
                            failed_count += 1
            
            # If Data is a single object
            elif isinstance(data, dict):
                phone = data.get("MobileNumber", "")
                message_id = data.get("MessageId", "")
                error_code = data.get("MessageErrorCode", data.get("ErrorCode", ""))
                error_desc_text = data.get("MessageErrorDescription", data.get("ErrorDescription", None))
                
                # Success if MessageErrorCode is 0
                is_success = str(error_code) == "0" or error_code == 0
                
                if phone:
                    recipient_status = "sent" if is_success else "failed"
                    error_desc = error_desc_text if error_desc_text and not is_success else None
                    
                    recipient, created = SMSRecipient.objects.update_or_create(
                        message=sms_message,
                        phone_number=phone,
                        defaults={
                            'status': recipient_status,
                            'api_message_id': message_id,
                            'error_description': error_desc,
                            'delivery_time': timezone.now() if is_success else None
                        }
                    )
                    logger.info(f"{'Created' if created else 'Updated'} SMSRecipient: {phone} - {recipient_status} (ID: {recipient.id})")
                    
                    if is_success:
                        successful_count += 1
                    else:
                        failed_count += 1
            
            # If no individual status available, fall back to checking ErrorCode
            if successful_count == 0 and failed_count == 0:
                successful_count = len(recipients_list)
        else:
            # API call failed at the request level
            failed_count = len(recipients_list)
            
            # Mark all recipients as failed
            for phone in recipients_list:
                SMSRecipient.objects.update_or_create(
                    message=sms_message,
                    phone_number=phone,
                    defaults={
                        'status': 'failed',
                        'error_description': api_response.get("ErrorDescription", "Unknown error")
                    }
                )

        # Update overall message status
        sms_message.successful_deliveries = successful_count
        sms_message.failed_deliveries = failed_count
        
        if successful_count > 0 and failed_count == 0:
            sms_message.status = 'sent'
        elif failed_count > 0 and successful_count == 0:
            sms_message.status = 'failed'
        else:
            sms_message.status = 'partial'  # Some succeeded, some failed

        sms_message.save()

    def update_sms_message_error(self, sms_message_id, error_message):
        try:
            sms_message = SMSMessage.objects.get(id=sms_message_id)
            sms_message.status = 'failed'
            sms_message.api_response = {'error': error_message}
            sms_message.failed_deliveries = sms_message.total_recipients
            sms_message.successful_deliveries = 0
            sms_message.save()
        except SMSMessage.DoesNotExist:
            logger.error(f"SMS message {sms_message_id} not found for error update")

    def refresh_message_status(self, sms_message_id):
        """Fetch latest status from SMS provider and update message."""
        try:
            sms_message = SMSMessage.objects.get(id=sms_message_id)
            recipients = [r.phone_number for r in sms_message.recipient_logs.all()]
            
            if not recipients:
                logger.warning(f"No recipients found for message {sms_message_id}")
                return {"success": False, "error": "No recipients found"}
            
            # Fetch current status from history API
            # Use sent_at or created_at for date range
            msg_date = sms_message.sent_at or sms_message.created_at
            if msg_date:
                from_date = msg_date.strftime("%Y-%m-%d")
                to_date = timezone.now().strftime("%Y-%m-%d")
                
                history_result = self.get_sms_history(
                    start=0, 
                    length=100, 
                    fromdate=from_date, 
                    enddate=to_date
                )
                
                if history_result.get("success"):
                    history_data = history_result.get("history", {})
                    messages = history_data.get("Data", [])
                    
                    # Match messages by phone numbers and update
                    updated_count = 0
                    for recipient in sms_message.recipient_logs.all():
                        for msg in messages:
                            if msg.get("MobileNumber") == recipient.phone_number:
                                error_code = msg.get("MessageErrorCode", msg.get("ErrorCode", ""))
                                is_success = str(error_code) == "0" or error_code == 0
                                recipient_status = "sent" if is_success else "failed"
                                recipient.status = recipient_status
                                recipient.api_message_id = msg.get("MessageId", "")
                                error_desc = msg.get("MessageErrorDescription", msg.get("ErrorDescription", None))
                                recipient.error_description = error_desc if not is_success else None
                                recipient.delivery_time = timezone.now() if is_success else None
                                recipient.save()
                                updated_count += 1
                                break
                    
                    # Recalculate message stats
                    successful = sms_message.recipient_logs.filter(status='sent').count()
                    failed = sms_message.recipient_logs.filter(status='failed').count()
                    
                    sms_message.successful_deliveries = successful
                    sms_message.failed_deliveries = failed
                    
                    if successful > 0 and failed == 0:
                        sms_message.status = 'sent'
                    elif failed > 0 and successful == 0:
                        sms_message.status = 'failed'
                    else:
                        sms_message.status = 'partial'
                    
                    sms_message.save()
                    
                    return {
                        "success": True, 
                        "message": f"Updated {updated_count} recipient(s)",
                        "successful": successful,
                        "failed": failed
                    }
                else:
                    return {"success": False, "error": history_result.get("error", "Failed to fetch history")}
            else:
                return {"success": False, "error": "Message date not available"}
                
        except SMSMessage.DoesNotExist:
            return {"success": False, "error": "Message not found"}
        except Exception as e:
            logger.error(f"Error refreshing message status: {e}")
            return {"success": False, "error": str(e)}

    def is_successful_response(self, api_response):
        """Check if API response indicates successful sending (checks individual message status)."""
        if not isinstance(api_response, dict):
            return False
        
        # Check top-level ErrorCode first
        if api_response.get("ErrorCode") not in [0, "0"]:
            return False
        
        # Check individual message status in Data
        data = api_response.get("Data")
        
        # If Data is a list, check if at least one succeeded (MessageErrorCode == 0)
        if isinstance(data, list):
            for item in data:
                error_code = item.get("MessageErrorCode", item.get("ErrorCode", ""))
                if str(error_code) == "0" or error_code == 0:
                    return True
            return False
        
        # If Data is a single object, check its MessageErrorCode
        elif isinstance(data, dict):
            error_code = data.get("MessageErrorCode", data.get("ErrorCode", ""))
            return str(error_code) == "0" or error_code == 0
        
        # If no Data or no status info, consider it successful if ErrorCode is 0
        return True


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