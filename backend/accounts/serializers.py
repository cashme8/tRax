"""
Serializers turn JSON into validated Python data (and model instances back into JSON).
"""

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User, normalize_email


class UserSerializer(serializers.ModelSerializer):
    """What the API shows about a user. Never includes the password."""

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "created_at"]
        read_only_fields = ["id", "email", "created_at"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ["email", "full_name", "password"]

    def validate_email(self, value: str) -> str:
        email = normalize_email(value)
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return email

    def validate(self, attrs: dict) -> dict:
        # Django's password rules: min length, not too common, not all digits, not like the email.
        candidate = User(email=attrs["email"], full_name=attrs.get("full_name", ""))
        try:
            password_validation.validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    def create(self, validated_data: dict) -> User:
        return User.objects.create_user(**validated_data)

    def to_representation(self, user: User) -> dict:
        """After registering, return the user plus tokens so the app can log straight in."""
        refresh = RefreshToken.for_user(user)
        return {
            "user": UserSerializer(user).data,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Login: like simplejwt's default, but the email is matched case-insensitively."""

    def validate(self, attrs: dict) -> dict:
        attrs[self.username_field] = normalize_email(attrs.get(self.username_field, ""))
        return super().validate(attrs)
