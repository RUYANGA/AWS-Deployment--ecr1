"""Serializers for the registration, login and logout endpoints."""

from django.contrib.auth import authenticate, password_validation
from rest_framework import serializers

from ...models import User


class RegisterSerializer(serializers.ModelSerializer):
    """Create a new user account.

    Validates that the email is not already registered (case-insensitive), that both
    password fields match and that the password satisfies Django's password validators.
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
