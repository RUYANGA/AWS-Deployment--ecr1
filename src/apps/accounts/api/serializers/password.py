"""Serializer for changing the authenticated user's password."""

from django.contrib.auth import password_validation
from rest_framework import serializers


class ChangePasswordSerializer(serializers.Serializer):
    """Change the password of the authenticated user.

    Requires the current password and validates the new one with Django's password
    validators. The request must be passed in the serializer context.
    """

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        """Verify the current password.

        Args:
            value: The current password submitted by the client.

        Returns:
            The submitted password, unchanged.

        Raises:
            serializers.ValidationError: If it does not match the user's password.
        """
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate_new_password(self, value):
        """Run Django's password validators against the new password.

        Args:
            value: The new password submitted by the client.

        Returns:
            The submitted password, unchanged.

        Raises:
            django.core.exceptions.ValidationError: If the password is too weak.
        """
        password_validation.validate_password(value, user=self.context["request"].user)
        return value
