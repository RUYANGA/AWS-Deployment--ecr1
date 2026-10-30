"""Endpoints for the authenticated user's own profile and password."""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..serializers import ChangePasswordSerializer, ProfileUpdateSerializer, UserSerializer

TAG = "Profile"


@extend_schema(tags=[TAG])
class MeView(generics.RetrieveUpdateAPIView):
    """Read or update the authenticated user's own profile."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch"]

    def get_object(self):
        """Return the authenticated user, so the endpoint needs no ID in the URL."""
        return self.request.user

    def get_serializer_class(self):
        """Accept profile changes on ``PATCH``; always respond with the profile."""
        if self.request.method == "PATCH":
            return ProfileUpdateSerializer
        return UserSerializer

    @extend_schema(summary="Get your profile")
    def get(self, request, *args, **kwargs):
        """Return the authenticated user's profile."""
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Update your profile",
        request=ProfileUpdateSerializer,
        responses={200: UserSerializer, 400: OpenApiResponse(description="Validation error")},
    )
    def patch(self, request, *args, **kwargs):
        """Update any of: email, first name, last name, phone number and password.

        All fields are optional. To change ``email`` or ``password``, also send
        ``current_password``. A new ``password`` must be repeated in ``password_confirm``.
        Tokens already issued stay valid after a password change.
        """
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data)


class ChangePasswordView(generics.GenericAPIView):
    """Change the authenticated user's password."""

    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[TAG],
        summary="Change the current user's password",
        responses={204: None, 400: OpenApiResponse(description="Validation error")},
    )
    def post(self, request):
        """Set a new password after verifying the current one.

        Existing JWT tokens stay valid until they expire.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
