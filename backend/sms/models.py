from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator


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
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='templates')
    title = models.CharField(max_length=255)
    content = models.TextField(max_length=1600)  # SMS character limit
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'title']

    def __str__(self):
        return f"{self.title} - {self.user.email}"


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
    
    # API Response data
    api_response = models.JSONField(null=True, blank=True)
    message_id = models.CharField(max_length=255, blank=True)  # From API response
    delivery_status = models.CharField(max_length=100, blank=True)
    
    # Cost and delivery info
    cost = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    total_recipients = models.PositiveIntegerField(default=0)
    successful_deliveries = models.PositiveIntegerField(default=0)
    failed_deliveries = models.PositiveIntegerField(default=0)
    
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
        if sms_message.status == 'sent':
            self.total_sent += sms_message.total_recipients
            self.total_delivered += sms_message.successful_deliveries
            self.total_failed += sms_message.failed_deliveries
            if sms_message.cost:
                self.total_cost += sms_message.cost
        self.save()
