"""Helpers for issuing JWT tokens."""

from rest_framework_simplejwt.tokens import RefreshToken


def tokens_for_user(user):
    """Issue a new JWT access/refresh token pair for a user.

    Args:
        user: The user the tokens are issued for.

    Returns:
        A dict with ``access`` and ``refresh`` token strings.
    """
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}
