import httpx
import asyncio
from django.conf import settings
from django.utils import timezone
from .models import SMSMessage, APICredentials
import logging

logger = logging.getLogger(__name__)


class MySMSMantraService:
    """Service class for interacting with MySMSMantra API"""
    
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
                'sender_id': credentials.sender_id
            }
        except APICredentials.DoesNotExist:
            # Fall back to global settings if user doesn't have custom credentials
            return {
                'api_key': settings.MYSMSMANTRA_CONFIG['API_KEY'],
                'client_id': settings.MYSMSMANTRA_CONFIG['CLIENT_ID'],
                'sender_id': settings.MYSMSMANTRA_CONFIG['SENDER_ID']
            }
    
    async def send_sms_async(self, sms_message_id, message_text, recipients_list, sender_id=None):
        """Send SMS asynchronously using MySMSMantra API"""
        try:
            # Get SMS message object
            sms_message = await asyncio.to_thread(
                SMSMessage.objects.get, id=sms_message_id
            )
            
            # Get API credentials
            credentials = self.get_user_credentials()
            
            # Override sender_id if provided
            if sender_id:
                credentials['sender_id'] = sender_id
            
            # Prepare recipients string
            recipients_str = ','.join(recipients_list)
            
            # Prepare API parameters
            params = {
                'ApiKey': credentials['api_key'],
                'ClientId': credentials['client_id'],
                'SenderId': credentials['sender_id'],
                'Message': message_text,
                'MobileNumbers': recipients_str,
                'Is_Unicode': '0',
                'Is_Flash': '0'
            }
            
            logger.info(f"Sending SMS to {len(recipients_list)} recipients via MySMSMantra API")
            
            # Make API request
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.api_url, params=params)
                response.raise_for_status()
                
                # Parse response
                response_data = response.json() if response.headers.get('content-type') == 'application/json' else {
                    'status': 'success' if response.status_code == 200 else 'error',
                    'response_text': response.text,
                    'status_code': response.status_code
                }
                
                # Update SMS message with response
                await self.update_sms_message_async(sms_message, response_data, recipients_list)
                
                return {
                    'success': True,
                    'message': 'SMS sent successfully',
                    'api_response': response_data,
                    'message_id': sms_message.id
                }
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error sending SMS: {e}")
            await self.update_sms_message_error_async(sms_message_id, str(e))
            return {
                'success': False,
                'error': f'API request failed: {str(e)}',
                'message_id': sms_message_id
            }
            
        except Exception as e:
            logger.error(f"Error sending SMS: {e}")
            await self.update_sms_message_error_async(sms_message_id, str(e))
            return {
                'success': False,
                'error': str(e),
                'message_id': sms_message_id
            }
    
    async def update_sms_message_async(self, sms_message, api_response, recipients_list):
        """Update SMS message with API response"""
        def update_in_thread():
            # Refresh from database
            sms_message.refresh_from_db()
            
            # Update with API response
            sms_message.api_response = api_response
            sms_message.sent_at = timezone.now()
            
            # Parse API response to determine status
            if self.is_successful_response(api_response):
                sms_message.status = 'sent'
                sms_message.successful_deliveries = len(recipients_list)
                sms_message.failed_deliveries = 0
                
                # Extract message ID if available
                if isinstance(api_response, dict):
                    sms_message.message_id = api_response.get('MessageId', '')
                    sms_message.delivery_status = api_response.get('Status', 'Sent')
                    
            else:
                sms_message.status = 'failed'
                sms_message.successful_deliveries = 0
                sms_message.failed_deliveries = len(recipients_list)
            
            sms_message.save()
            
            # Update user usage stats
            if hasattr(sms_message.user, 'usage_stats'):
                sms_message.user.usage_stats.update_stats(sms_message)
            
        await asyncio.to_thread(update_in_thread)
    
    async def update_sms_message_error_async(self, sms_message_id, error_message):
        """Update SMS message with error status"""
        def update_in_thread():
            try:
                sms_message = SMSMessage.objects.get(id=sms_message_id)
                sms_message.status = 'failed'
                sms_message.api_response = {'error': error_message}
                sms_message.failed_deliveries = sms_message.total_recipients
                sms_message.successful_deliveries = 0
                sms_message.save()
            except SMSMessage.DoesNotExist:
                logger.error(f"SMS message {sms_message_id} not found for error update")
                
        await asyncio.to_thread(update_in_thread)
    
    def is_successful_response(self, api_response):
        """Check if API response indicates success"""
        if isinstance(api_response, dict):
            # Check common success indicators
            status = api_response.get('Status', '').lower()
            error_code = api_response.get('ErrorCode', '')
            
            # MySMSMantra specific success indicators
            success_indicators = ['success', 'sent', 'ok', 'submitted']
            
            return (
                any(indicator in status for indicator in success_indicators) or
                error_code == '0' or
                error_code == '' and status != 'error'
            )
        
        # If response is not JSON, assume success if we got here
        return api_response.get('status_code') == 200
    
    def send_sms_sync(self, sms_message_id, message_text, recipients_list, sender_id=None):
        """Synchronous wrapper for sending SMS"""
        return asyncio.run(
            self.send_sms_async(sms_message_id, message_text, recipients_list, sender_id)
        )


# Utility function to send SMS from views
async def send_sms_message(user, message_text, recipients_list, sender_id=None, template_id=None):
    """
    High-level function to send SMS message
    
    Args:
        user: User object
        message_text: SMS content
        recipients_list: List of phone numbers
        sender_id: Optional sender ID
        template_id: Optional template ID
    
    Returns:
        dict: Result with success status and message details
    """
    from .models import SenderID, Template
    
    try:
        # Create SMS message record
        sms_message = SMSMessage.objects.create(
            user=user,
            message_text=message_text,
            status='pending'
        )
        sms_message.set_recipients_list(recipients_list)
        
        # Set sender ID if provided
        if sender_id:
            try:
                sender = SenderID.objects.get(id=sender_id, user=user, is_active=True)
                sms_message.sender_id = sender
            except SenderID.DoesNotExist:
                pass
        
        # Set template if provided
        if template_id:
            try:
                template = Template.objects.get(id=template_id, user=user, is_active=True)
                sms_message.template = template
            except Template.DoesNotExist:
                pass
        
        sms_message.save()
        
        # Send SMS using service
        service = MySMSMantraService(user=user)
        result = await service.send_sms_async(
            sms_message.id, 
            message_text, 
            recipients_list, 
            sender_id
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error in send_sms_message: {e}")
        return {
            'success': False,
            'error': str(e)
        }