from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.conf import settings
from django.utils import timezone


# --------------------------
# USER MODEL
# --------------------------
class User(AbstractUser):
    """User model for both Admins and Teachers"""
    email = models.EmailField(unique=True)
    phone_regex = RegexValidator(
        regex=r'^\+?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone_number = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    company = models.CharField(max_length=255, blank=True)
    is_verified = models.BooleanField(default=False)

    assigned_class = models.CharField(max_length=100, blank=True, null=True)

    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('teacher', 'Teacher'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='teacher')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.email} ({self.role})"


# --------------------------
# API CREDENTIALS
# --------------------------
class APICredentials(models.Model):
    """Stores SMS API credentials for a user"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='api_credentials')
    api_key = models.CharField(max_length=255)
    client_id = models.CharField(max_length=100)
    sender_id = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - API Credentials"


# --------------------------
# SENDER IDs
# --------------------------
class SenderID(models.Model):
    """Approved sender IDs (e.g., DBITADM, DBITEDU)"""
    TYPE_CHOICES = [
        ('transactional', 'Transactional'),
        ('promotional', 'Promotional'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sender_ids')
    name = models.CharField(max_length=20)
    description = models.TextField(blank=True, null=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='transactional')
    is_approved = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.type})"


# --------------------------
# TEMPLATES
# --------------------------
class Template(models.Model):
    """Reusable SMS templates"""
    CATEGORY_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('common', 'Common'),
    ]

    STATUS_CHOICES = [
        ('approved', 'Approved'),
        ('pending', 'Pending'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='templates')
    title = models.CharField(max_length=255)
    content = models.TextField(max_length=1600)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='student')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='approved')
    variable_schema = models.JSONField(null=True, blank=True)
    class_scope = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'title']

    def __str__(self):
        return f"{self.title} - {self.user.email}"


# --------------------------
# GROUPS (Class or Batch)
# --------------------------
class Group(models.Model):
    """Represents a class or contact group (e.g., Class 10A)"""
    name = models.CharField(max_length=255, unique=True)
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='teacher_groups',
        limit_choices_to={'role': 'teacher'}
    )
    class_dept = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.teacher and not self.class_dept:
            self.class_dept = self.teacher.assigned_class
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.teacher.email}"


# --------------------------
# CONTACTS
# --------------------------
class StudentContact(models.Model):
    """Individual contacts within a group (filtered by class)"""
    name = models.CharField(max_length=255)
    phone_regex = RegexValidator(
        regex=r'^\+?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'."
    )
    phone_number = models.CharField(validators=[phone_regex], max_length=17)
    class_dept = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='contacts')
    meta = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('class_dept', 'phone_number')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.phone_number})"

    @property
    def class_name(self):
        return self.class_dept.name if self.class_dept else None


# --------------------------
# CAMPAIGNS
# --------------------------
class Campaign(models.Model):
    """Represents a batch/campaign of SMS messages (e.g., announcements, reminders)."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("sending", "Sending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="campaigns")
    title = models.CharField(max_length=255, help_text="Name of the campaign, e.g. 'Parent Meeting 23 Oct'")
    description = models.TextField(blank=True, null=True)
    template = models.ForeignKey("Template", on_delete=models.SET_NULL, null=True, blank=True, related_name="campaigns")
    group = models.ForeignKey("Group", on_delete=models.SET_NULL, null=True, blank=True, related_name="campaigns")
    sender_id = models.ForeignKey("SenderID", on_delete=models.SET_NULL, null=True, blank=True, related_name="campaigns")

    total_recipients = models.PositiveIntegerField(default=0)
    total_sent = models.PositiveIntegerField(default=0)
    total_delivered = models.PositiveIntegerField(default=0)
    total_failed = models.PositiveIntegerField(default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    scheduled_for = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.status})"

    def update_stats(self):
        """Aggregates SMS message results into campaign totals."""
        related_messages = self.messages.all()
        self.total_recipients = sum(m.total_recipients for m in related_messages)
        self.total_sent = sum(1 for m in related_messages if m.status in ["sent", "delivered"])
        self.total_delivered = sum(m.successful_deliveries for m in related_messages)
        self.total_failed = sum(m.failed_deliveries for m in related_messages)
        self.save()


# --------------------------
# SMS MESSAGES
# --------------------------
class SMSMessage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sms_messages')
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, null=True, blank=True, related_name="messages")

    message_text = models.TextField()
    recipients = models.JSONField(default=list)
    status = models.CharField(max_length=20, default='pending')
    api_response = models.JSONField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    successful_deliveries = models.IntegerField(default=0)
    failed_deliveries = models.IntegerField(default=0)
    total_recipients = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SMS to {len(self.recipients)} recipients (Campaign: {self.campaign.title if self.campaign else 'N/A'})"

    def set_recipients_list(self, recipients_list):
        self.recipients = recipients_list or []
        self.total_recipients = len(recipients_list or [])
        self.save()


# --------------------------
# INDIVIDUAL RECIPIENT LOGS
# --------------------------
class SMSRecipient(models.Model):
    """Tracks delivery status of each recipient within a message."""
    message = models.ForeignKey(SMSMessage, on_delete=models.CASCADE, related_name="recipient_logs")
    phone_number = models.CharField(max_length=15)
    api_message_id = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, default="pending")  # pending/sent/delivered/failed
    submit_time = models.DateTimeField(null=True, blank=True)
    delivery_time = models.DateTimeField(null=True, blank=True)
    error_description = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.phone_number} ({self.status})"


# --------------------------
# USAGE STATS
# --------------------------
class SMSUsageStats(models.Model):
    """Tracks per-user SMS usage"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='usage_stats')
    total_sent = models.PositiveIntegerField(default=0)
    total_delivered = models.PositiveIntegerField(default=0)
    total_failed = models.PositiveIntegerField(default=0)
    total_cost = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    remaining_credits = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - Usage Stats"

    def update_stats(self, sms_message):
        """Update stats based on a new SMSMessage record"""
        try:
            self.total_sent += sms_message.total_recipients
            self.total_delivered += sms_message.successful_deliveries
            self.total_failed += sms_message.failed_deliveries
            sms_cost_per_message = 0.25
            self.total_cost += sms_message.total_recipients * sms_cost_per_message
            self.remaining_credits = max(self.remaining_credits - sms_message.total_recipients, 0)
            self.save()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error updating usage stats for {self.user.email}: {e}")
