"""Serializer for updating the authenticated user's own profile."""

from django.contrib.auth import password_validation
from rest_framework import serializers

from ...models import User
from .management import UniqueEmailMixin

SENSITIVE_FIELDS = ("email", "password")


class ProfileUpdateSerializer(UniqueEmailMixin, serializers.ModelSerializer):
    """Update your own profile, email and password.

    All fields are optional. Changing ``email`` or ``password`` also requires
    ``current_password``, so a stolen access token alone cannot take over the account.
    A new ``password`` must be repeated in ``password_confirm`` and pass the password
    validators.
    """

    password = serializers.CharField(
        write_only=True, required=False, style={"input_type": "password"}
    )
    password_confirm = serializers.CharField(
        write_only=True, required=False, style={"input_type": "password"}
    )
    current_password = serializers.CharField(
        write_only=True,
        required=False,
        style={"input_type": "password"},
        help_text="Required when changing email or password.",
    )

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "password",
            "password_confirm",
            "current_password",
        ]

    def validate(self, attrs):
        """Check the current password, password confirmation and password strength.

        Args:
            attrs: Field values that passed field-level validation.

        Returns:
            The validated data without ``password_confirm`` and ``current_password``.

        Raises:
            serializers.ValidationError: If the current password is missing or wrong,
                the new passwords differ, or the new password is too weak.
        """
        user = self.instance
        current_password = attrs.pop("current_password", None)
        password_confirm = attrs.pop("password_confirm", None)
        password = attrs.get("password")

        changing_email = "email" in attrs and attrs["email"] != user.email
        if changing_email or password is not None:
            if not current_password:
                raise serializers.ValidationError(
                    {
                        "current_password": (  # nosec B105 - validation message, not a secret
                            "Required to change your email or password."
                        )
                    }
                )
            if not user.check_password(current_password):
                raise serializers.ValidationError(
                    {
                        "current_password": (  # nosec B105 - validation message, not a secret
                            "Current password is incorrect."
                        )
                    }
                )

        if password is not None or password_confirm is not None:
            if password != password_confirm:
                raise serializers.ValidationError(
                    {"password_confirm": "Passwords do not match."}  # nosec B105 - not a secret
                )
            password_validation.validate_password(password, user=user)
        return attrs

    def update(self, instance, validated_data):
        """Apply the changes, hashing the new password if one was given.

        Args:
            instance: The authenticated user.
            validated_data: Data returned by :meth:`validate`.

        Returns:
            The updated user.
        """
        password = validated_data.pop("password", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password is not None:
            instance.set_password(password)
        instance.save()
        return instance
