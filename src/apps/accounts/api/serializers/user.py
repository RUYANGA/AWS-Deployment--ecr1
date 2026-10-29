from rest_framework import serializers

from ...models import User


class UserSerializer(serializers.ModelSerializer):
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
            "date_joined",
        ]
        read_only_fields = ["id", "email", "date_joined"]
