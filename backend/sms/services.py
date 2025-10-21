import httpx
from django.conf import settings
from django.utils import timezone
from .models import SMSMessage, APICredentials, SenderID, Template
import logging

logger = logging.getLogger(__name__)


class MySMSMantraService:
    """Synchronous service class for interacting with MySMSMantra API"""

    def __init__(self, user=None):
        self.user = user
        self.api_url = settings.MYSMSMANTRA_CONFIG['API_URL']

    def get_user_credentials(self):
        """Get API credentials for the user"""
        if not self.user:
            raise ValueError("User is required for API credentials")

        try:
            credentials = APICredentials.objects.get(user=self.user, is_active=True)
            return {
                'api_key': credentials.api_key,
                'client_id': credentials.client_id,
                'sender_id': credentials.sender_id,
            }
        except APICredentials.DoesNotExist:
            # Fallback to global settings if user doesn't have custom credentials
            return {
                'api_key': settings.MYSMSMANTRA_CONFIG['API_KEY'],
                'client_id': settings.MYSMSMANTRA_CONFIG['CLIENT_ID'],
                'sender_id': settings.MYSMSMANTRA_CONFIG['SENDER_ID'],
            }

    def send_sms_sync(self, sms_message_id, message_text, recipients_list, sender_id=None):
        """Send SMS synchronously using MySMSMantra API"""
        try:
            sms_message = SMSMessage.objects.get(id=sms_message_id)
            credentials = self.get_user_credentials()

            if sender_id:
                credentials['sender_id'] = sender_id

            recipients_str = ','.join(recipients_list)

            params = {
                'ApiKey': credentials['api_key'],
                'ClientId': credentials['client_id'],
                'SenderId': credentials['sender_id'],
                'Message': message_text,
                'MobileNumbers': recipients_str,
                'Is_Unicode': '0',
                'Is_Flash': '0',
            }

            logger.info(f"Sending SMS to {len(recipients_list)} recipients via MySMSMantra API")

            # ✅ Sync API call using httpx
            with httpx.Client(timeout=30.0) as client:
                response = client.get(self.api_url, params=params)
                response.raise_for_status()

                # Parse response
                if response.headers.get('content-type') == 'application/json':
                    response_data = response.json()
                else:
                    response_data = {
                        'status': 'success' if response.status_code == 200 else 'error',
                        'response_text': response.text,
                        'status_code': response.status_code,
                    }

            # Update SMS message after API call
            self.update_sms_message(sms_message, response_data, recipients_list)

            return {
                'success': True,
                'message': 'SMS sent successfully',
                'api_response': response_data,
                'message_id': sms_message.id,
            }

        except httpx.HTTPError as e:
            logger.error(f"HTTP error sending SMS: {e}")
            self.update_sms_message_error(sms_message_id, str(e))
            return {'success': False, 'error': f'API request failed: {e}', 'message_id': sms_message_id}

        except Exception as e:
            logger.error(f"Error sending SMS: {e}")
            self.update_sms_message_error(sms_message_id, str(e))
            return {'success': False, 'error': str(e), 'message_id': sms_message_id}

    def update_sms_message(self, sms_message, api_response, recipients_list):
        """Update SMS message with API response"""
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

        if hasattr(sms_message.user, 'usage_stats'):
            sms_message.user.usage_stats.update_stats(sms_message)

    def update_sms_message_error(self, sms_message_id, error_message):
        """Update SMS message with error status"""
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
        """Check if API response indicates success"""
        if isinstance(api_response, dict):
            status = api_response.get('Status', '').lower()
            error_code = api_response.get('ErrorCode', '')
            success_indicators = ['success', 'sent', 'ok', 'submitted']
            return (
                any(indicator in status for indicator in success_indicators)
                or error_code == '0'
                or (error_code == '' and status != 'error')
            )

        # Fallback: non-JSON, consider success if HTTP 200
        return api_response.get('status_code') == 200


# -------------------------------------------------------------------
# Utility function for use in views
# -------------------------------------------------------------------

def send_sms_message(user, message_text, recipients_list, sender_id=None, template_id=None):
    """Public utility to send SMS synchronously via MySMSMantra"""
    try:
        sms_message = SMSMessage.objects.create(
            user=user,
            message_text=message_text,
            status="pending",
        )
        sms_message.set_recipients_list(recipients_list)

        if sender_id:
            try:
                sender = SenderID.objects.get(id=sender_id, user=user, is_active=True)
                sms_message.sender_id = sender
            except SenderID.DoesNotExist:
                pass

        if template_id:
            try:
                template = Template.objects.get(id=template_id, user=user, is_active=True)
                sms_message.template = template
            except Template.DoesNotExist:
                pass

        sms_message.save()

        # ✅ Use the now synchronous service
        service = MySMSMantraService(user=user)
        result = service.send_sms_sync(sms_message.id, message_text, recipients_list, sender_id)

        sms_message.api_response = result.get("api_response", {})
        sms_message.sent_at = timezone.now()
        sms_message.status = "sent" if result.get("success") else "failed"
        sms_message.save()

        return {
            "success": result.get("success", False),
            "message": result.get("message", "Failed to send"),
            "api_response": result.get("api_response", {}),
        }

    except Exception as e:
        logger.error(f"Error in send_sms_message: {e}")
        return {"success": False, "error": str(e)}
