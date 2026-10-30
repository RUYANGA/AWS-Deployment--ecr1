"""Permissions for the user-management endpoints."""

from rest_framework.permissions import BasePermission


class CanManageUsers(BasePermission):
    """Allow staff users to manage accounts, with superusers protected.

    Any staff user (``is_staff``) may list, create and edit users. Superuser accounts
    can only be changed by another superuser, so a staff member cannot lock out, delete
    or take over an account with more privileges than their own.
    """

    message = "You do not have permission to manage users."

    def has_permission(self, request, view):
        """Require an authenticated, active staff user."""
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.is_staff)

    def has_object_permission(self, request, view, obj):
        """Only superusers may act on superuser accounts."""
        return not obj.is_superuser or request.user.is_superuser
