"""Texts for the OpenAPI schema shown in Swagger UI and ReDoc."""

TAGS = [
    {
        "name": "Authentication",
        "description": (
            "Register, log in, refresh and revoke JSON Web Tokens. "
            "Register and login are rate-limited per IP address."
        ),
    },
    {
        "name": "Profile",
        "description": (
            "The authenticated user's own profile and password. Requires an authenticated JWT."
        ),
    },
    {
        "name": "Users",
        "description": (
            "User management for administrators: list, search, create, update, "
            "activate or deactivate, set passwords and delete accounts."
        ),
    },
    {
        "name": "Health",
        "description": "Liveness and readiness probe for load balancers and orchestrators.",
    },
]


def build_description(access_minutes, refresh_days, throttle_rates):
    """Build the concise description shown at the top of Swagger UI and ReDoc.

    The arguments are retained for compatibility with the settings configuration.
    """
    return (
        "The Logistic Identity API provides secure user registration, authentication, "
        "profile management and administrative user-management endpoints. "
        "It issues and validates JWT access tokens for the Logistic platform's services."
    )
