from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from sms.models import APICredentials, SMSUsageStats
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = 'Create a new user (admin or teacher) with optional API credentials'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, required=True, help='User email address')
        parser.add_argument('--username', type=str, help='Username (defaults to email)')
        parser.add_argument('--password', type=str, required=True, help='User password')
        parser.add_argument('--role', type=str, choices=['admin', 'teacher'], default='teacher', help='User role')
        parser.add_argument('--phone', type=str, help='Phone number')
        parser.add_argument('--company', type=str, help='Company/Institution name')
        parser.add_argument('--assigned-class', type=str, help='Assigned class/section (for teachers)')
        parser.add_argument('--is-staff', action='store_true', help='Grant staff access (Django admin)')
        parser.add_argument('--is-superuser', action='store_true', help='Grant superuser privileges')
        
        # API Credentials (optional)
        parser.add_argument('--api-key', type=str, help='MySMSMantra API Key')
        parser.add_argument('--client-id', type=str, help='MySMSMantra Client ID')
        parser.add_argument('--sender-id', type=str, help='MySMSMantra Sender ID')
        
        # Credits
        parser.add_argument('--credits', type=int, default=100, help='Initial SMS credits (default: 100)')

    @transaction.atomic
    def handle(self, *args, **options):
        email = options['email']
        username = options.get('username') or email
        password = options['password']
        role = options['role']
        phone = options.get('phone', '')
        company = options.get('company', '')
        assigned_class = options.get('assigned_class', '')
        is_staff = options.get('is_staff', False)
        is_superuser = options.get('is_superuser', False)
        
        # Check if user exists
        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.ERROR(f'❌ User with email "{email}" already exists!'))
            return
        
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.ERROR(f'❌ User with username "{username}" already exists!'))
            return
        
        # Create user
        self.stdout.write(f'Creating {role} user...')
        user = User.objects.create_user(
            email=email,
            username=username,
            password=password,
            role=role,
            phone_number=phone,
            company=company,
            assigned_class=assigned_class,
            is_staff=is_staff or is_superuser,  # Superusers are automatically staff
            is_superuser=is_superuser,
            is_active=True,
            is_verified=True
        )
        
        self.stdout.write(self.style.SUCCESS(f'✅ User created: {email} ({role})'))
        
        # Create API Credentials if provided
        api_key = options.get('api_key')
        client_id = options.get('client_id')
        sender_id = options.get('sender_id')
        
        if api_key and client_id:
            APICredentials.objects.create(
                user=user,
                api_key=api_key,
                client_id=client_id,
                sender_id=sender_id or 'BOMBYS',
                is_active=True
            )
            self.stdout.write(self.style.SUCCESS(f'✅ API credentials added'))
        
        # Create SMS Usage Stats
        credits = options['credits']
        SMSUsageStats.objects.create(
            user=user,
            remaining_credits=credits,
            total_sent=0,
            total_delivered=0,
            total_failed=0
        )
        self.stdout.write(self.style.SUCCESS(f'✅ SMS credits initialized: {credits}'))
        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('🎉 USER CREATED SUCCESSFULLY'))
        self.stdout.write('='*60)
        self.stdout.write(f'📧 Email:        {email}')
        self.stdout.write(f'👤 Username:     {username}')
        self.stdout.write(f'🔑 Password:     {"*" * len(password)}')
        self.stdout.write(f'👔 Role:         {role}')
        self.stdout.write(f'📱 Phone:        {phone or "Not set"}')
        self.stdout.write(f'🏢 Company:      {company or "Not set"}')
        self.stdout.write(f'📚 Class:        {assigned_class or "Not set"}')
        self.stdout.write(f'🔧 Staff:        {"Yes" if is_staff else "No"}')
        self.stdout.write(f'⚡ Superuser:    {"Yes" if is_superuser else "No"}')
        self.stdout.write(f'💳 SMS Credits:  {credits}')
        self.stdout.write(f'🔌 API Setup:    {"Yes" if (api_key and client_id) else "No (using .env defaults)"}')
        self.stdout.write('='*60)
        
        if is_superuser:
            self.stdout.write(self.style.WARNING('\n⚠️  This user has superuser privileges!'))
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ Login at: http://localhost:8000/login/'))
