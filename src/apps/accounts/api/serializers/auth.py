"""Serializers for the registration, email verification, login and logout endpoints."""

from django.conf import settings
from django.contrib.auth import authenticate, password_validation
from rest_framework import serializers

from ...models import User
from ...utils import EmailOTPError, verify_email_otp
from .user import UserSerializer


class RegisterSerializer(serializers.ModelSerializer):
    """Create a new user account.

    Validates that the email is not already registered (case-insensitive), that both
    password fields match and that the password satisfies Django's password validators.
    The account starts unverified; a verification code is emailed to the address.
    """

    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "password",
            "password_confirm",
        ]

    def validate_email(self, value):
        """Normalise the email to lowercase and reject addresses already in use.

        Args:
            value: Email address submitted by the client.

        Returns:
            The lowercased email address.

        Raises:
            serializers.ValidationError: If a user with this email already exists.
        """
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs):
        """Check that the passwords match and that the password is strong enough.

        The password is validated against an unsaved user built from the submitted
        data, so similarity checks (e.g. password resembling the email) apply.

        Args:
            attrs: Field values that passed field-level validation.

        Returns:
            The validated data without ``password_confirm``.

        Raises:
            serializers.ValidationError: If the passwords differ or the password is weak.
        """
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}  # nosec B105 - not a secret
            )
        candidate = User(**{k: v for k, v in attrs.items() if k != "password"})
        password_validation.validate_password(attrs["password"], user=candidate)
        return attrs

    def create(self, validated_data):
        """Create the user with a hashed password.

        Args:
            validated_data: Data returned by :meth:`validate`.

        Returns:
            The newly created :class:`~apps.accounts.models.User`.
        """
        return User.objects.create_user(**validated_data)


class MessageSerializer(serializers.Serializer):
    """A human-readable message about the outcome of a request."""

    detail = serializers.CharField()


class RegisterResponseSerializer(MessageSerializer):
    """Body returned by register: the new, still unverified user profile."""

    user = UserSerializer()


class VerifyEmailSerializer(serializers.Serializer):
    """Confirm an email address with the one-time code that was sent to it."""

    email = serializers.EmailField()
    code = serializers.RegexField(
        rf"^\d{{{settings.EMAIL_OTP_LENGTH}}}$",
        error_messages={"invalid": f"Enter the {settings.EMAIL_OTP_LENGTH}-digit code."},
    )

    def validate(self, attrs):
        """Check the code and mark the account's email address as verified.

        Args:
            attrs: The submitted ``email`` and ``code``.

        Returns:
            The validated data with the verified user under ``"user"``.

        Raises:
            serializers.ValidationError: If the account does not exist or is already
                verified, or the code is missing, expired, locked or wrong. Code errors
                carry the reason (``expired``, ``locked``, ...) as the error code.
        """
        user = User.objects.filter(email__iexact=attrs["email"], is_active=True).first()
        if user is None:
            raise serializers.ValidationError(
                {"code": ["Invalid email or verification code."]}, code="invalid"
            )
        if user.is_email_verified:
            raise serializers.ValidationError(
                {"email": ["This email address is already verified."]}, code="already_verified"
            )
        try:
            verify_email_otp(user, attrs["code"])
        except EmailOTPError as exc:
            raise serializers.ValidationError({"code": [exc.message]}, code=exc.code) from exc
        attrs["user"] = user
        return attrs


class ResendVerificationSerializer(serializers.Serializer):
    """Email address of an account that needs a new verification code."""

    email = serializers.EmailField()


class LoginSerializer(serializers.Serializer):
    """Authenticate a user with email and password."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        """Authenticate the credentials and attach the user to the validated data.

        Args:
            attrs: The submitted ``email`` and ``password``.

        Returns:
            The validated data with the authenticated user under ``"user"``.

        Raises:
            serializers.ValidationError: If the credentials are invalid or the account
                is inactive. The message is deliberately generic so it does not reveal
                which accounts exist.
        """
        user = authenticate(
            request=self.context.get("request"),
            email=attrs["email"].lower(),
            password=attrs["password"],
        )
        if user is None:
            raise serializers.ValidationError("Invalid email or password.", code="authorization")
        attrs["user"] = user
        return attrs


class LogoutSerializer(serializers.Serializer):
    """Refresh token to revoke when logging out."""

    refresh = serializers.CharField()
