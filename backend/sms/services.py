import httpx
from django.conf import settings
from django.utils import timezone
from .models import SMSMessage
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

        try:
            logger.info(f"Sending SMS via MySMSMantra → {len(recipients_list)} recipient(s)")

            with httpx.Client(timeout=30.0) as client:
                headers = {
                    'Accept': 'application/json'
                }
                response = client.get(self.api_url, params=params, headers=headers)
                response.raise_for_status()

                try:
                    data = response.json()
                    logger.info(f"MySMSMantra Response: {data}")
                except Exception:
                    data = {"raw_response": response.text, "status_code": response.status_code}
                    logger.warning(f"Non-JSON response: {response.text}")

            self.update_sms_message(sms_message, data, recipients_list)
            success = self.is_successful_response(data)

            return {
                "success": success,
                "message": "SMS sent successfully" if success else "Failed to send SMS",
                "api_response": data,
                "message_id": sms_message.id,
            }

        except httpx.HTTPError as e:
            logger.error(f"HTTP error while sending SMS: {e}")
            self.update_sms_message_error(sms_message_id, str(e))
            return {"success": False, "error": f"API request failed: {e}", "message_id": sms_message_id}

        except Exception as e:
            logger.error(f"Unexpected error while sending SMS: {e}")
            self.update_sms_message_error(sms_message_id, str(e))
            return {"success": False, "error": str(e), "message_id": sms_message_id}

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
        sms_message.refresh_from_db()
        sms_message.api_response = api_response
        sms_message.sent_at = timezone.now()

        if self.is_successful_response(api_response):
            sms_message.status = 'sent'
            sms_message.successful_deliveries = len(recipients_list)
            sms_message.failed_deliveries = 0
        else:
            sms_message.status = 'failed'
            sms_message.successful_deliveries = 0
            sms_message.failed_deliveries = len(recipients_list)

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

    def is_successful_response(self, api_response):
        if not isinstance(api_response, dict):
            return False
        if api_response.get("ErrorCode") in [0, "0"]:
            return True
        data_list = api_response.get("Data")
        if isinstance(data_list, list) and len(data_list) > 0:
            msg_status = data_list[0].get("MessageErrorDescription", "").lower()
            return "success" in msg_status
        return False


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

        sms_message.api_response = result.get("api_response", {})
        sms_message.sent_at = timezone.now()
        sms_message.status = "sent" if result.get("success") else "failed"
        sms_message.save()

        return result

    except Exception as e:
        logger.error(f"Error in send_sms_message: {e}")
        return {"success": False, "error": str(e)}
