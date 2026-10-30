"""Administrator endpoints for managing user accounts."""

from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from ...models import User
from ..permissions import CanManageUsers
from ..serializers import (
    ManagedUserSerializer,
    SetPasswordSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
)

TAG = "Users"
BOOLEAN_VALUES = {"true": True, "1": True, "false": False, "0": False}
FORBIDDEN = OpenApiResponse(description="Not a staff user, or target is a superuser")


@extend_schema(tags=[TAG])
@extend_schema_view(
    list=extend_schema(
        summary="List users",
        parameters=[
            OpenApiParameter("is_active", OpenApiTypes.BOOL, description="Filter by status"),
            OpenApiParameter("is_staff", OpenApiTypes.BOOL, description="Filter by staff flag"),
        ],
    ),
    create=extend_schema(
        summary="Create a user",
        responses={201: ManagedUserSerializer, 400: OpenApiResponse(description="Invalid")},
    ),
    retrieve=extend_schema(summary="Get a user", responses={200: ManagedUserSerializer}),
    partial_update=extend_schema(
        summary="Update a user",
        responses={200: ManagedUserSerializer, 400: OpenApiResponse(description="Invalid")},
    ),
    destroy=extend_schema(
        summary="Delete a user",
        responses={204: None, 400: OpenApiResponse(description="Cannot delete yourself")},
    ),
)
class UserViewSet(viewsets.ModelViewSet):
    """Manage user accounts. Staff only.

    Superuser accounts can only be changed by superusers, and administrators cannot
    deactivate, demote or delete their own account.
    """

    queryset = User.objects.all()
    permission_classes = [CanManageUsers]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["email", "first_name", "last_name"]
    ordering_fields = ["email", "first_name", "last_name", "date_joined", "last_login"]
    ordering = ["-date_joined"]

    def get_serializer_class(self):
        """Use the write serializer matching the action; read with the full view."""
        return {
            "create": UserCreateSerializer,
            "partial_update": UserUpdateSerializer,
            "set_password": SetPasswordSerializer,
        }.get(self.action, ManagedUserSerializer)

    def get_queryset(self):
        """Apply the optional ``is_active`` and ``is_staff`` filters.

        Raises:
            ValidationError: If a filter value is not ``true``/``false``.
        """
        queryset = super().get_queryset()
        for field in ("is_active", "is_staff"):
            raw = self.request.query_params.get(field)
            if raw is None:
                continue
            value = BOOLEAN_VALUES.get(raw.lower())
            if value is None:
                raise ValidationError({field: "Use true or false."})
            queryset = queryset.filter(**{field: value})
        return queryset

    def list(self, request, *args, **kwargs):
        """List users, newest first, paginated.

        Search with ``?search=`` (email, first or last name), filter with ``?is_active=``
        and ``?is_staff=``, sort with ``?ordering=`` (e.g. ``email`` or ``-date_joined``).
        """
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Create a user with a password; ``is_superuser`` cannot be set."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(ManagedUserSerializer(user).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        """Return one user's account details."""
        return super().retrieve(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """Update profile fields, status or the staff flag.

        Changing your own ``is_active`` or ``is_staff`` to ``false`` is rejected so an
        administrator cannot lock themselves out.
        """
        user = self.get_object()
        serializer = self.get_serializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if user.pk == request.user.pk:
            for field in ("is_active", "is_staff"):
                if serializer.validated_data.get(field) is False:
                    raise ValidationError({field: "You cannot remove this from yourself."})
        serializer.save()
        return Response(ManagedUserSerializer(user).data)

    def destroy(self, request, *args, **kwargs):
        """Permanently delete a user. Prefer deactivating to keep history."""
        user = self.get_object()
        if user.pk == request.user.pk:
            raise ValidationError({"detail": "You cannot delete your own account."})
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(summary="Activate a user", request=None, responses={200: ManagedUserSerializer})
    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        """Re-enable a deactivated account so the user can log in again."""
        return self._set_active(request, active=True)

    @extend_schema(
        summary="Deactivate a user",
        request=None,
        responses={200: ManagedUserSerializer, 400: OpenApiResponse(description="Yourself")},
    )
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        """Disable an account. The user's existing tokens stop working immediately."""
        return self._set_active(request, active=False)

    @extend_schema(
        summary="Set a user's password",
        request=SetPasswordSerializer,
        responses={204: None, 400: OpenApiResponse(description="Weak password"), 403: FORBIDDEN},
    )
    @action(detail=True, methods=["post"], url_path="set-password")
    def set_password(self, request, pk=None):
        """Replace a user's password, e.g. after a reset request."""
        user = self.get_object()
        serializer = self.get_serializer(data=request.data, context={"target_user": user})
        serializer.is_valid(raise_exception=True)
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _set_active(self, request, active):
        """Set ``is_active`` on the target user, refusing to deactivate yourself."""
        user = self.get_object()
        if not active and user.pk == request.user.pk:
            raise ValidationError({"detail": "You cannot deactivate your own account."})
        user.is_active = active
        user.save(update_fields=["is_active", "updated_at"])
        return Response(ManagedUserSerializer(user).data)
