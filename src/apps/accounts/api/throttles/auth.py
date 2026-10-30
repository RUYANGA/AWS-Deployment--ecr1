"""Rate limiting for authentication endpoints."""

from rest_framework.throttling import AnonRateThrottle


class AuthRateThrottle(AnonRateThrottle):
    """Stricter rate limit for credential endpoints (brute-force protection).

    Uses the ``auth`` rate from ``REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]``, keyed by
    client IP address.
    """

    scope = "auth"
