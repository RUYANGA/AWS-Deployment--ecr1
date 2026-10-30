"""Serializers for the user-management endpoints used by administrators."""

from django.contrib.auth import password_validation
from rest_framework import serializers

from ...models import User


class ManagedUserSerializer(serializers.ModelSerializer):
    """Full account details as seen by administrators."""

    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone_number",
            "is_active",
            "is_staff",
            "is_superuser",
            "date_joined",
            "last_login",
            "updated_at",
        ]
        read_only_fields = fields


class UniqueEmailMixin:
    """Validate that an email is unused (case-insensitive) and store it lowercased."""

    def validate_email(self, value):
        """Lowercase the email and reject addresses used by another account.

        Args:
            value: Email address submitted by the client.

        Returns:
            The lowercased email address.

        Raises:
            serializers.ValidationError: If another user already has this email.
        """
        value = value.lower()
        others = User.objects.filter(email__iexact=value)
        if self.instance is not None:
            others = others.exclude(pk=self.instance.pk)
        if others.exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value


class UserCreateSerializer(UniqueEmailMixin, serializers.ModelSerializer):
    """Create an account on behalf of a user.

    The password must pass the password validators. ``is_superuser`` cannot be set
    through the API.
    """

    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "password",
            "is_active",
            "is_staff",
        ]

    def validate(self, attrs):
        """Run the password validators against the account being created.

        Args:
            attrs: Field values that passed field-level validation.

        Returns:
            The validated data, unchanged.

        Raises:
            django.core.exceptions.ValidationError: If the password is too weak.
        """
        candidate = User(**{k: v for k, v in attrs.items() if k != "password"})
        password_validation.validate_password(attrs["password"], user=candidate)
        return attrs

    def create(self, validated_data):
        """Create the user with a hashed password.

        Args:
            validated_data: Data returned by :meth:`validate`.

        Returns:
            The newly created user.
        """
        return User.objects.create_user(**validated_data)


class UserUpdateSerializer(UniqueEmailMixin, serializers.ModelSerializer):
    """Update an account's profile, status and staff flag.

    Passwords are changed with the dedicated set-password action; ``is_superuser`` is
    not editable through the API.
    """

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "is_active",
            "is_staff",
        ]


class SetPasswordSerializer(serializers.Serializer):
    """Set a new password for a user, validated with the password validators."""

    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_new_password(self, value):
        """Run the password validators against the target user.

        Args:
            value: The new password.

        Returns:
            The password, unchanged.

        Raises:
            django.core.exceptions.ValidationError: If the password is too weak.
        """
        password_validation.validate_password(value, user=self.context.get("target_user"))
        return value
