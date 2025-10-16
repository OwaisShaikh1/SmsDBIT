from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, SMSMessage, SenderID, Template, APICredentials, SMSUsageStats


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin interface for User model"""
    list_display = ('email', 'username', 'company', 'is_verified', 'is_active', 'created_at')
    list_filter = ('is_verified', 'is_active', 'is_staff', 'created_at')
    search_fields = ('email', 'username', 'company')
    ordering = ('-created_at',)
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('phone_number', 'company', 'is_verified')
        }),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Additional Info', {
            'fields': ('email', 'phone_number', 'company')
        }),
    )


@admin.register(SMSMessage)
class SMSMessageAdmin(admin.ModelAdmin):
    """Admin interface for SMS messages"""
    list_display = ('id', 'user', 'status', 'total_recipients', 'successful_deliveries', 'failed_deliveries', 'created_at')
    list_filter = ('status', 'created_at', 'sent_at')
    search_fields = ('user__email', 'message_text', 'recipients')
    readonly_fields = ('created_at', 'updated_at', 'api_response')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Message Info', {
            'fields': ('user', 'message_text', 'recipients', 'sender_id', 'template')
        }),
        ('Status', {
            'fields': ('status', 'message_id', 'delivery_status')
        }),
        ('Statistics', {
            'fields': ('total_recipients', 'successful_deliveries', 'failed_deliveries', 'cost')
        }),
        ('Timing', {
            'fields': ('sent_at', 'delivered_at', 'created_at', 'updated_at')
        }),
        ('API Response', {
            'fields': ('api_response',),
            'classes': ('collapse',)
        })
    )


@admin.register(SenderID)
class SenderIDAdmin(admin.ModelAdmin):
    """Admin interface for Sender IDs"""
    list_display = ('name', 'user', 'is_approved', 'is_active', 'created_at')
    list_filter = ('is_approved', 'is_active', 'created_at')
    search_fields = ('name', 'user__email', 'description')
    ordering = ('-created_at',)
    
    actions = ['approve_sender_ids', 'reject_sender_ids']
    
    def approve_sender_ids(self, request, queryset):
        count = queryset.update(is_approved=True)
        self.message_user(request, f'{count} Sender IDs approved successfully.')
    approve_sender_ids.short_description = "Approve selected Sender IDs"
    
    def reject_sender_ids(self, request, queryset):
        count = queryset.update(is_approved=False)
        self.message_user(request, f'{count} Sender IDs rejected.')
    reject_sender_ids.short_description = "Reject selected Sender IDs"


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    """Admin interface for Templates"""
    list_display = ('title', 'user', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'content', 'user__email')
    ordering = ('-created_at',)


@admin.register(APICredentials)
class APICredentialsAdmin(admin.ModelAdmin):
    """Admin interface for API Credentials"""
    list_display = ('user', 'sender_id', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('user__email', 'sender_id')
    ordering = ('-created_at',)
    
    # Hide sensitive fields in list view, show in detail view
    fields = ('user', 'api_key', 'client_id', 'sender_id', 'is_active')


@admin.register(SMSUsageStats)
class SMSUsageStatsAdmin(admin.ModelAdmin):
    """Admin interface for SMS Usage Statistics"""
    list_display = ('user', 'total_sent', 'total_delivered', 'total_failed', 'remaining_credits', 'last_updated')
    list_filter = ('last_updated',)
    search_fields = ('user__email',)
    readonly_fields = ('last_updated',)
    ordering = ('-last_updated',)
    
    def get_readonly_fields(self, request, obj=None):
        # Make all fields readonly except remaining_credits for admins
        if request.user.is_superuser:
            return ('last_updated',)
        return [field.name for field in self.model._meta.fields if field.name != 'remaining_credits']


# Customize admin site headers
admin.site.site_header = "SMS Portal Administration"
admin.site.site_title = "SMS Portal Admin"
admin.site.index_title = "Welcome to SMS Portal Administration"
