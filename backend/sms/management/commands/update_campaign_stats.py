from django.core.management.base import BaseCommand
from sms.models import Campaign


class Command(BaseCommand):
    help = 'Recalculate statistics for all campaigns based on related SMS messages'

    def handle(self, *args, **options):
        campaigns = Campaign.objects.all()
        total = campaigns.count()
        
        self.stdout.write(self.style.WARNING(f'Updating statistics for {total} campaigns...'))
        
        updated = 0
        for campaign in campaigns:
            old_sent = campaign.total_sent
            old_delivered = campaign.total_delivered
            old_failed = campaign.total_failed
            
            campaign.update_stats()
            
            self.stdout.write(
                f'Campaign "{campaign.title}": '
                f'Sent {old_sent}→{campaign.total_sent}, '
                f'Delivered {old_delivered}→{campaign.total_delivered}, '
                f'Failed {old_failed}→{campaign.total_failed}'
            )
            updated += 1
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ Successfully updated {updated} campaigns!'))
