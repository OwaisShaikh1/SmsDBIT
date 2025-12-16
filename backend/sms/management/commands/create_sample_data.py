from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random
from sms.models import SMSMessage, User


class Command(BaseCommand):
    help = 'Create sample SMS data for testing reports'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to create data for (default: 7)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing SMS messages before creating new ones'
        )

    def handle(self, *args, **options):
        days = options['days']
        clear_existing = options['clear']

        # Get admin user
        try:
            user = User.objects.get(username='admin')
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR('Admin user not found. Please create admin user first.'))
            return

        if clear_existing:
            count = SMSMessage.objects.count()
            SMSMessage.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Deleted {count} existing SMS messages'))

        self.stdout.write('Creating sample SMS data...')

        # Create messages for the specified number of days
        today = timezone.now()
        messages_created = 0

        for i in range(days):
            day = today - timedelta(days=(days-1)-i)

            # Generate random number of messages for each day (increasing trend)
            base_count = 50 + (i * 30)  # Start with 50, increase by 30 each day

            for j in range(base_count):
                # 85% delivered, 10% failed, 5% pending
                rand = random.random()
                if rand < 0.85:
                    status = 'delivered'
                elif rand < 0.95:
                    status = 'failed'
                else:
                    status = 'pending'

                # Random hour during the day
                hour = random.randint(8, 18)
                minute = random.randint(0, 59)

                created_time = day.replace(hour=hour, minute=minute, second=0, microsecond=0)

                # Create message with recipients
                phone = f"+9199999{random.randint(10000, 99999)}"
                msg = SMSMessage.objects.create(
                    user=user,
                    message_text=f"Sample message {j+1} for testing reports",
                    status=status,
                    recipients=[phone],
                    total_recipients=1,
                    successful_deliveries=1 if status == 'delivered' else 0,
                    failed_deliveries=1 if status == 'failed' else 0,
                    sent_at=created_time if status in ['delivered', 'failed'] else None
                )
                # Update created_at manually
                SMSMessage.objects.filter(id=msg.id).update(created_at=created_time)
                messages_created += 1

        self.stdout.write(self.style.SUCCESS(f'✅ Created {messages_created} sample SMS messages'))

        # Print summary
        self.stdout.write('\nSummary by status:')
        for status in ['delivered', 'failed', 'pending']:
            count = SMSMessage.objects.filter(status=status).count()
            self.stdout.write(f'  {status.capitalize()}: {count}')

        self.stdout.write('\nSummary by day:')
        for i in range(days):
            day = today - timedelta(days=(days-1)-i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)

            count = SMSMessage.objects.filter(
                created_at__range=[day_start, day_end]
            ).count()
            self.stdout.write(f'  {day.strftime("%Y-%m-%d")}: {count} messages')

        self.stdout.write(self.style.SUCCESS('\n✅ Sample data created successfully!'))
