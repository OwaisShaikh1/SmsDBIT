from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator


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
    
    # NEW FIELD — class or department the teacher is assigned to
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
    class_scope = models.CharField(max_length=100, blank=True, null=True)  # 🔹 NEW: restrict template to class
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
    class_dept = models.CharField(max_length=100, blank=True, null=True)  # 🔹 NEW: linked to teacher.assigned_class
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Auto-assign class_dept if teacher has assigned_class
        if self.teacher and not self.class_dept:
            self.class_dept = self.teacher.assigned_class
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.teacher.email}"


# --------------------------
# CONTACTS (Students/Parents)
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
# SMS MESSAGES
# --------------------------
# sms/models.py
from django.db import models

from django.conf import settings
from django.db import models
import json

class SMSMessage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # ✅ Use this instead of 'auth.User'
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sms_messages'
    )
    message_text = models.TextField()
    recipients = models.JSONField(default=list)  # stores list of phone numbers
    status = models.CharField(max_length=20, default='pending')
    api_response = models.JSONField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    successful_deliveries = models.IntegerField(default=0)
    failed_deliveries = models.IntegerField(default=0)
    total_recipients = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SMS to {len(self.recipients)} recipients"

    def set_recipients_list(self, recipients_list):
        """Stores recipients as JSON and updates total count"""
        self.recipients = recipients_list or []
        self.total_recipients = len(recipients_list or [])
        self.save()

# --------------------------
# USAGE STATS
# --------------------------
class SMSUsageStats(models.Model):
    """Tracks per-user SMS usage"""
    user = models.OneToOneField('User', on_delete=models.CASCADE, related_name='usage_stats')
    total_sent = models.PositiveIntegerField(default=0)
    total_delivered = models.PositiveIntegerField(default=0)
    total_failed = models.PositiveIntegerField(default=0)
    total_cost = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    remaining_credits = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - Usage Stats"

    # ✅ ADD THIS
    def update_stats(self, sms_message):
        """Update stats based on a new SMSMessage record"""
        try:
            self.total_sent += sms_message.total_recipients
            self.total_delivered += sms_message.successful_deliveries
            self.total_failed += sms_message.failed_deliveries

            # Example cost calculation — adjust if needed
            sms_cost_per_message = 0.25  # e.g., ₹0.25 per message
            self.total_cost += sms_message.total_recipients * sms_cost_per_message
            self.remaining_credits = max(self.remaining_credits - sms_message.total_recipients, 0)

            self.save()
            return True
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error updating usage stats for {self.user.email}: {e}")
            return False
