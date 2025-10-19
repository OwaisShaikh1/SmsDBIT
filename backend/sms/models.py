from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.conf import settings


class User(AbstractUser):
    """Extended User model with additional fields for SMS portal"""
    email = models.EmailField(unique=True)
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone_number = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    company = models.CharField(max_length=255, blank=True)
    is_verified = models.BooleanField(default=False)

    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('teacher', 'Teacher'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='teacher', help_text="User role (admin or teacher)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email


class APICredentials(models.Model):
    """Store MySMSMantra API credentials for each user"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='api_credentials')
    api_key = models.CharField(max_length=255)
    client_id = models.CharField(max_length=255)
    sender_id = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "API Credentials"

    def __str__(self):
        return f"{self.user.email} - API Credentials"


class SenderID(models.Model):
    """Manage different sender IDs for users"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sender_ids')
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'name']

    def __str__(self):
        return f"{self.name} - {self.user.email}"


class Template(models.Model):
    """SMS message templates for users"""
    CATEGORY_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('common', 'Common'),
    )
    STATUS_CHOICES = (
        ('approved', 'Approved'),
        ('pending', 'Pending'),
        ('rejected', 'Rejected'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='templates')
    title = models.CharField(max_length=255)
    content = models.TextField(max_length=1600)  # SMS character limit
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='student',
                                help_text="Who the template is intended for")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='approved')
    # Optional JSON schema to persist how {#var#} occurrences are mapped to names/types
    variable_schema = models.JSONField(null=True, blank=True,
                                       help_text="Optional mapping schema for anonymous variables (index -> name/type)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'title']

    def __str__(self):
        return f"{self.title} - {self.user.email}"


class Group(models.Model):
    """Group of contacts (e.g., Class 10A, Teachers)"""
    GROUP_TYPE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('mixed', 'Mixed'),
    )

    name = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=20, choices=GROUP_TYPE_CHOICES, default='student')
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='created_groups')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Group"
        verbose_name_plural = "Groups"

    def __str__(self):
        return f"{self.name} ({self.type})"


class Contact(models.Model):
    """Individual contact linked to a group"""
    name = models.CharField(max_length=255)
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone_number = models.CharField(validators=[phone_regex], max_length=17)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='members')
    # optional metadata (roll no, parent name, etc.)
    meta = models.JSONField(null=True, blank=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='added_contacts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('group', 'phone_number')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.phone_number})"


class SMSMessage(models.Model):
    """Store SMS message history and status"""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('delivered', 'Delivered'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sms_messages')
    recipients = models.TextField()  # Store comma-separated phone numbers
    message_text = models.TextField(max_length=1600)
    sender_id = models.ForeignKey(SenderID, on_delete=models.SET_NULL, null=True, blank=True)
    template = models.ForeignKey(Template, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Groups targeted (optional, useful for history and UI)
    groups = models.ManyToManyField(Group, blank=True, related_name='sent_messages')

    # API Response data
    api_response = models.JSONField(null=True, blank=True)
    message_id = models.CharField(max_length=255, blank=True)  # From API response
    delivery_status = models.CharField(max_length=100, blank=True)

    # Cost and delivery info
    cost = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    total_recipients = models.PositiveIntegerField(default=0)
    successful_deliveries = models.PositiveIntegerField(default=0)
    failed_deliveries = models.PositiveIntegerField(default=0)

    # Variables used for this send (mapping name->value) - persisted for audit
    variables_used = models.JSONField(null=True, blank=True, help_text="Final variable values used for this send")

    # Timing
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"SMS to {self.total_recipients} recipients - {self.status}"

    def get_recipients_list(self):
        """Return list of recipient phone numbers"""
        return [num.strip() for num in self.recipients.split(',') if num.strip()]

    def set_recipients_list(self, numbers_list):
        """Set recipients from a list of phone numbers"""
        self.recipients = ','.join(numbers_list)
        self.total_recipients = len(numbers_list)


class SMSUsageStats(models.Model):
    """Track SMS usage statistics for users"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='usage_stats')
    total_sent = models.PositiveIntegerField(default=0)
    total_delivered = models.PositiveIntegerField(default=0)
    total_failed = models.PositiveIntegerField(default=0)
    total_cost = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    remaining_credits = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "SMS Usage Statistics"

    def __str__(self):
        return f"{self.user.email} - Usage Stats"

    def update_stats(self, sms_message):
        """Update statistics when an SMS is sent"""
        # increment totals based on the message's recorded counts
        # we allow updates for any eventual status change; call this after final status set
        try:
            self.total_sent += int(sms_message.total_recipients or 0)
            self.total_delivered += int(sms_message.successful_deliveries or 0)
            self.total_failed += int(sms_message.failed_deliveries or 0)
            if sms_message.cost:
                self.total_cost += sms_message.cost
            self.save()
        except Exception:
            # avoid crashing on malformed data; log in production
            pass
