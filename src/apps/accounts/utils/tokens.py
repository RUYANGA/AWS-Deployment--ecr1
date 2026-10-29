from rest_framework_simplejwt.tokens import RefreshToken


def tokens_for_user(user):
    """Issue a new JWT access/refresh pair for ``user``."""
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}
