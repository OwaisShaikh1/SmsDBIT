from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import SMSMessage, SMSRecipient


@receiver(post_save, sender=SMSMessage)
def update_campaign_on_message_save(sender, instance, **kwargs):
    """Update campaign statistics when an SMS message is saved"""
    if instance.campaign:
        instance.campaign.update_stats()


@receiver(post_delete, sender=SMSMessage)
def update_campaign_on_message_delete(sender, instance, **kwargs):
    """Update campaign statistics when an SMS message is deleted"""
    if instance.campaign:
        instance.campaign.update_stats()


@receiver(post_save, sender=SMSRecipient)
def update_campaign_on_recipient_save(sender, instance, **kwargs):
    """Update campaign statistics when recipient status changes"""
    if instance.message and instance.message.campaign:
        # Update the parent message's delivery counts first
        message = instance.message
        recipients = message.recipient_logs.all()
        message.successful_deliveries = recipients.filter(status='delivered').count()
        message.failed_deliveries = recipients.filter(status='failed').count()
        message.save(update_fields=['successful_deliveries', 'failed_deliveries'])
        
        # Then update the campaign stats
        message.campaign.update_stats()
