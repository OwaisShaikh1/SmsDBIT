from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import (
    User, SMSMessage, SenderID, Template, APICredentials, SMSUsageStats,
    Group, Contact
)


#
# User / Auth serializers
#
class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, required=False, default='teacher',
                                   help_text="Role for the new user (admin or teacher). Only use with care.")

    class Meta:
        model = User
        fields = ('email', 'username', 'password', 'password_confirm', 'phone_number', 'company', 'role')

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm', None)
        # pop role to set it explicitly (so we can restrict if needed)
        role = validated_data.pop('role', 'teacher')
        password = validated_data.pop('password')

        # create user - using create_user to ensure password hashing
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.role = role
        user.save()
        return user


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            # authenticate expects username field; your User model uses email as USERNAME_FIELD
            user = authenticate(username=email, password=password)
            if not user:
                raise serializers.ValidationError('Invalid credentials')
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled')
            attrs['user'] = user
            return attrs
        raise serializers.ValidationError('Must include email and password')


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user profile"""

    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'phone_number', 'company', 'is_verified', 'role', 'created_at')
        read_only_fields = ('id', 'email', 'is_verified', 'created_at')


#
# API Credentials / SenderID serializers
#
class APICredentialsSerializer(serializers.ModelSerializer):
    """Serializer for API credentials"""

    class Meta:
        model = APICredentials
        fields = ('id', 'api_key', 'client_id', 'sender_id', 'is_active', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class SenderIDSerializer(serializers.ModelSerializer):
    """Serializer for sender IDs"""

    class Meta:
        model = SenderID
        fields = ('id', 'name', 'description', 'is_approved', 'is_active', 'created_at', 'updated_at')
        read_only_fields = ('id', 'is_approved', 'created_at', 'updated_at')

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


#
# Group & Contact serializers
#
class ContactSerializer(serializers.ModelSerializer):
    """Serializer for a contact (member of a group)"""
    class Meta:
        model = Contact
        fields = ('id', 'name', 'phone_number', 'meta', 'group', 'added_by', 'created_at', 'updated_at')
        read_only_fields = ('id', 'added_by', 'created_at', 'updated_at')

    def create(self, validated_data):
        # set added_by automatically from the request user if available
        user = self.context['request'].user
        validated_data['added_by'] = user
        return super().create(validated_data)


class GroupSerializer(serializers.ModelSerializer):
    """Serializer for groups with members"""
    members = ContactSerializer(many=True, read_only=True)
    members_count = serializers.IntegerField(source='members.count', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = Group
        fields = ('id', 'name', 'type', 'description', 'created_by', 'created_by_name', 'members', 'members_count', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_by', 'created_by_name', 'members_count', 'created_at', 'updated_at')

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


#
# Template serializer
#
class TemplateSerializer(serializers.ModelSerializer):
    """Serializer for SMS templates"""
    # expose variable_schema if present
    variable_schema = serializers.JSONField(required=False, allow_null=True)

    class Meta:
        model = Template
        fields = ('id', 'title', 'content', 'category', 'status', 'variable_schema', 'is_active', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


#
# SMS message serializer
#
class SMSMessageSerializer(serializers.ModelSerializer):
    """Serializer for SMS messages"""
    # For creating: provide recipients_list (list of numbers); stored as comma-separated 'recipients'
    recipients_list = serializers.ListField(
        child=serializers.CharField(max_length=20),
        write_only=True,
        required=False,
        help_text="List of phone numbers"
    )
    # groups (M2M) can be provided as list of ids
    groups = serializers.PrimaryKeyRelatedField(many=True, queryset=Group.objects.all(), required=False)
    variables_used = serializers.JSONField(required=False, allow_null=True)

    sender_id_name = serializers.CharField(source='sender_id.name', read_only=True)
    template_title = serializers.CharField(source='template.title', read_only=True)
    groups_info = GroupSerializer(source='groups', many=True, read_only=True)

    class Meta:
        model = SMSMessage
        fields = (
            'id', 'recipients', 'recipients_list', 'message_text', 'sender_id', 'sender_id_name',
            'template', 'template_title', 'status', 'message_id', 'delivery_status',
            'cost', 'total_recipients', 'successful_deliveries', 'failed_deliveries',
            'sent_at', 'delivered_at', 'created_at', 'updated_at', 'api_response',
            'groups', 'groups_info', 'variables_used'
        )
        read_only_fields = (
            'id', 'recipients', 'status', 'message_id', 'delivery_status', 'cost',
            'total_recipients', 'successful_deliveries', 'failed_deliveries',
            'sent_at', 'delivered_at', 'created_at', 'updated_at', 'api_response'
        )

    def create(self, validated_data):
        # handle recipients_list -> recipients
        recipients_list = validated_data.pop('recipients_list', None) or []
        groups = validated_data.pop('groups', None) or []
        variables_used = validated_data.pop('variables_used', None)

        validated_data['user'] = self.context['request'].user

        sms_message = SMSMessage(**validated_data)

        # set recipients if provided
        if recipients_list:
            sms_message.set_recipients_list(recipients_list)
        else:
            # if no direct recipients, try to collect from groups (expand members)
            numbers = []
            for g in groups:
                for member in g.members.all():
                    numbers.append(member.phone_number)
            # deduplicate while preserving order
            seen = set()
            deduped = []
            for n in numbers:
                if n not in seen:
                    seen.add(n)
                    deduped.append(n)
            sms_message.set_recipients_list(deduped)

        # set variables used if provided (persisting mapping)
        if variables_used:
            sms_message.variables_used = variables_used

        sms_message.save()

        # set many-to-many groups if provided
        if groups:
            sms_message.groups.set(groups)

        return sms_message


#
# Send SMS serializer (for quick sends)
#
class SendSMSSerializer(serializers.Serializer):
    """
    Serializer for sending SMS via /send-sms/ endpoint.
    Expects simple message_text + recipients (list) or a pre-built payload.
    """
    # either 'recipients' list with a single message_text to send to all
    message_text = serializers.CharField(max_length=1600, required=False, allow_blank=True)
    recipients = serializers.ListField(
        child=serializers.CharField(max_length=20),
        min_length=1,
        required=False,
        help_text="List of phone numbers"
    )
    sender_id = serializers.IntegerField(required=False, help_text="Sender ID to use")
    template_id = serializers.IntegerField(required=False, help_text="Template ID to use")

    # optional "payload" for per-recipient messages (array of {name, number, message})
    payload = serializers.ListField(child=serializers.DictField(), required=False)

    def validate(self, attrs):
        # ensure either message_text+recipients OR payload is present
        if not attrs.get('payload') and not (attrs.get('message_text') and attrs.get('recipients')):
            raise serializers.ValidationError("Provide either 'payload' (per-recipient) or both 'message_text' and 'recipients'.")
        return attrs

    def validate_recipients(self, value):
        """Validate phone numbers format"""
        import re
        phone_pattern = re.compile(r'^\+?1?\d{9,15}$')

        for phone in value:
            if not phone_pattern.match(phone.strip()):
                raise serializers.ValidationError(
                    f"Invalid phone number format: {phone}. Use format: +1234567890"
                )
        return value

    def validate_sender_id(self, value):
        """Validate sender ID belongs to user"""
        if value:
            user = self.context['request'].user
            if not SenderID.objects.filter(id=value, user=user, is_active=True).exists():
                raise serializers.ValidationError("Invalid sender ID")
        return value

    def validate_template_id(self, value):
        """Validate template belongs to user (or is global for admins)"""
        if value:
            user = self.context['request'].user
            # admins may use any template
            if user.role == 'admin' and Template.objects.filter(id=value).exists():
                return value
            if not Template.objects.filter(id=value, user=user, is_active=True).exists():
                raise serializers.ValidationError("Invalid template ID")
        return value


#
# Usage stats & dashboard serializer
#
class SMSUsageStatsSerializer(serializers.ModelSerializer):
    """Serializer for SMS usage statistics"""

    class Meta:
        model = SMSUsageStats
        fields = (
            'total_sent', 'total_delivered', 'total_failed', 'total_cost',
            'remaining_credits', 'last_updated'
        )
        read_only_fields = '__all__'


class DashboardStatsSerializer(serializers.Serializer):
    """Serializer for dashboard statistics"""
    total_sent = serializers.IntegerField(read_only=True)
    total_delivered = serializers.IntegerField(read_only=True)
    total_failed = serializers.IntegerField(read_only=True)
    success_rate = serializers.FloatField(read_only=True)
    recent_messages = SMSMessageSerializer(many=True, read_only=True)
    monthly_stats = serializers.DictField(read_only=True)
    remaining_credits = serializers.DecimalField(max_digits=15, decimal_places=4, read_only=True)
