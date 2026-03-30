"""
User serializers
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from ..models import TestResult


class UserSerializer(serializers.ModelSerializer):
    """
    Basic user serializer for safe user data representation
    """
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'date_joined')
        read_only_fields = ('id', 'date_joined')


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration with password validation
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'password_confirm', 'first_name', 'last_name')
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
        }
    
    def validate(self, attrs):
        """
        Validate that passwords match
        """
        if attrs.get('password') != attrs.get('password_confirm'):
            raise serializers.ValidationError({
                "password": "Password fields didn't match."
            })
        return attrs
    
    def create(self, validated_data):
        """
        Create user with encrypted password
        """
        validated_data.pop('password_confirm')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user profile information
    """
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')
    
    def validate_email(self, value):
        """
        Validate that email is unique (excluding current user)
        """
        user = self.context['request'].user
        if User.objects.exclude(pk=user.pk).filter(email=value).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for password change endpoint
    """
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password]
    )
    new_password_confirm = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        """
        Validate that new passwords match
        """
        if attrs.get('new_password') != attrs.get('new_password_confirm'):
            raise serializers.ValidationError({
                "new_password": "New password fields didn't match."
            })
        return attrs
    
    def validate_old_password(self, value):
        """
        Validate that old password is correct
        """
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value


class TestResultSerializer(serializers.ModelSerializer):
    """Serializer for saved test results"""
    user = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = TestResult
        fields = (
            'id', 'user', 'payload', 'summary', 'saved_at',
            'dtw_score', 'final_score', 'stgcn_score',
            'ai_verdict', 'deep_verdict', 'windows', 'window_count',
            'ref_job_id', 'user_job_id', 'compare_job_id',
        )
        read_only_fields = ('id', 'user', 'saved_at')


class TestResultListSerializer(serializers.ModelSerializer):
    """Lightweight serializer returned in list views to avoid large payloads."""
    user = serializers.ReadOnlyField(source='user.username')
    refJobId = serializers.SerializerMethodField()
    userJobId = serializers.SerializerMethodField()
    has_payload = serializers.SerializerMethodField()

    class Meta:
        model = TestResult
        fields = ('id', 'user', 'summary', 'saved_at', 'refJobId', 'userJobId', 'has_payload',
                  'dtw_score', 'final_score', 'stgcn_score', 'ai_verdict', 'window_count')

    def get_refJobId(self, obj):
        try:
            return obj.payload.get('refJobId') if obj.payload else None
        except Exception:
            return None

    def get_userJobId(self, obj):
        try:
            return obj.payload.get('userJobId') if obj.payload else None
        except Exception:
            return None

    def get_has_payload(self, obj):
        return bool(obj.payload)
