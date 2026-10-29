from rest_framework.throttling import AnonRateThrottle


class AuthRateThrottle(AnonRateThrottle):
    """Stricter rate limit for credential endpoints (brute-force protection)."""

    scope = "auth"
