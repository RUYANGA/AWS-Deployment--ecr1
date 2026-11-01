"""Serializer for the user profile."""

from rest_framework import serializers

from ...models import User


class UserSerializer(serializers.ModelSerializer):
    """Public profile of a user.

    ``id``, ``email``, ``is_email_verified`` and ``date_joined`` are read-only; the
    remaining fields can be updated by the user through the ``me`` endpoint.
    """

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
            "is_email_verified",
            "date_joined",
        ]
        read_only_fields = ["id", "email", "is_email_verified", "date_joined"]
