from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User, SMSMessage, SenderID, Template, APICredentials, SMSUsageStats


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('email', 'username', 'password', 'password_confirm', 'phone_number', 'company')

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(username=email, password=password)
            if not user:
                raise serializers.ValidationError('Invalid credentials')
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled')
            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError('Must include email and password')


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user profile"""
    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'phone_number', 'company', 'is_verified', 'created_at')
        read_only_fields = ('id', 'email', 'is_verified', 'created_at')


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


class TemplateSerializer(serializers.ModelSerializer):
    """Serializer for SMS templates"""
    class Meta:
        model = Template
        fields = ('id', 'title', 'content', 'is_active', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class SMSMessageSerializer(serializers.ModelSerializer):
    """Serializer for SMS messages"""
    recipients_list = serializers.ListField(
        child=serializers.CharField(max_length=15),
        write_only=True,
        help_text="List of phone numbers"
    )
    sender_id_name = serializers.CharField(source='sender_id.name', read_only=True)
    template_title = serializers.CharField(source='template.title', read_only=True)

    class Meta:
        model = SMSMessage
        fields = (
            'id', 'recipients', 'recipients_list', 'message_text', 'sender_id', 'sender_id_name',
            'template', 'template_title', 'status', 'message_id', 'delivery_status',
            'cost', 'total_recipients', 'successful_deliveries', 'failed_deliveries',
            'sent_at', 'delivered_at', 'created_at', 'updated_at', 'api_response'
        )
        read_only_fields = (
            'id', 'recipients', 'status', 'message_id', 'delivery_status', 'cost',
            'total_recipients', 'successful_deliveries', 'failed_deliveries',
            'sent_at', 'delivered_at', 'created_at', 'updated_at', 'api_response'
        )

    def create(self, validated_data):
        recipients_list = validated_data.pop('recipients_list', [])
        validated_data['user'] = self.context['request'].user
        
        sms_message = SMSMessage(**validated_data)
        sms_message.set_recipients_list(recipients_list)
        sms_message.save()
        
        return sms_message


class SendSMSSerializer(serializers.Serializer):
    """Serializer for sending SMS"""
    message_text = serializers.CharField(max_length=1600)
    recipients = serializers.ListField(
        child=serializers.CharField(max_length=15),
        min_length=1,
        help_text="List of phone numbers"
    )
    sender_id = serializers.IntegerField(required=False, help_text="Sender ID to use")
    template_id = serializers.IntegerField(required=False, help_text="Template ID to use")

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
        """Validate template belongs to user"""
        if value:
            user = self.context['request'].user
            if not Template.objects.filter(id=value, user=user, is_active=True).exists():
                raise serializers.ValidationError("Invalid template ID")
        return value


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