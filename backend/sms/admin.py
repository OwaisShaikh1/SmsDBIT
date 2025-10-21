from django.contrib import admin
from .models import User, SenderID, APICredentials, Template, Group, StudentContact, SMSMessage, SMSUsageStats

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'username', 'role', 'is_staff', 'is_active')
    search_fields = ('email', 'username')
    list_filter = ('role', 'is_staff', 'is_active')

@admin.register(SenderID)
class SenderIDAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'is_approved', 'is_active', 'user')
    list_filter = ('type', 'is_approved', 'is_active')
    search_fields = ('name',)

@admin.register(APICredentials)
class APICredentialsAdmin(admin.ModelAdmin):
    list_display = ('user', 'api_key', 'is_active', 'created_at')
    list_filter = ('is_active',)

@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'category', 'status', 'is_active')
    list_filter = ('category', 'status', 'is_active')
    search_fields = ('title', 'content')

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'teacher')
    search_fields = ('name',)
    list_filter = ('teacher',)

@admin.register(StudentContact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'class_dept')
    search_fields = ('name', 'phone_number')

@admin.register(SMSMessage)
class SMSMessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'sent_at', 'created_at')
    list_filter = ('status',)
    search_fields = ('message_text',)

@admin.register(SMSUsageStats)
class SMSUsageStatsAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_sent', 'total_delivered', 'remaining_credits')
    list_filter = ('user',)
