"""Texts for the OpenAPI schema shown in Swagger UI and ReDoc.

Kept out of the settings module so the long Markdown stays readable. Values that depend on
configuration (token lifetimes, rate limits) are passed in, so the docs always match the
running settings.
"""

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
            "The authenticated user's own profile and password. Requires "
            "`Authorization: Bearer <access token>`. `GET /auth/me/` is also how other "
            "services verify a token."
        ),
    },
    {
        "name": "Users",
        "description": (
            "User management for administrators (`is_staff`): list, search, create, "
            "update, activate/deactivate, set passwords and delete accounts."
        ),
    },
    {
        "name": "Health",
        "description": "Liveness / readiness probe for load balancers and orchestrators.",
    },
]


def build_description(access_minutes, refresh_days, throttle_rates):
    """Build the Markdown description shown at the top of Swagger UI and ReDoc.

    Args:
        access_minutes: Access token lifetime in minutes.
        refresh_days: Refresh token lifetime in days.
        throttle_rates: DRF throttle rates, e.g. ``{"anon": "60/min", "auth": "10/min"}``.

    Returns:
        The description as a Markdown string.
    """
    return f"""
Identity service of the Logistic platform.

It **owns user identity** (accounts, credentials, profiles) and **issues the JSON Web
Tokens (JWTs)** that the rest of the platform trusts. The **shortener** and **analytics**
services keep no users or passwords of their own: they verify every token they receive
**over REST** against this service.

## How authentication works

1. **Get tokens.** Register with `POST /api/v1/auth/register/` or log in with
   `POST /api/v1/auth/login/`. Both return the user profile and a token pair:
   an **access** token and a **refresh** token.
2. **Call APIs.** Send `Authorization: Bearer <access token>` on every request, to this
   service and to the shortener and analytics services.
3. **Renew.** When the access token expires, exchange the refresh token at
   `POST /api/v1/auth/token/refresh/`. Refresh tokens rotate: each call returns a new
   refresh token and blacklists the old one.
4. **Log out.** `POST /api/v1/auth/logout/` blacklists the refresh token. Access tokens
   already issued stay valid until they expire, so keep them short-lived.

| Token | Lifetime | Used for |
|---|---|---|
| Access | {access_minutes} minutes | `Authorization: Bearer` header on API calls |
| Refresh | {refresh_days} days | obtaining a new access token |

## Verifying tokens (shortener and analytics services)

Forward the caller's `Authorization` header to **`GET /api/v1/auth/me/`**:

| Response | Meaning | What to do |
|---|---|---|
| `200 OK` | Token is valid | Trust the identity in the body (`id`, `email`, names) |
| `401 Unauthorized` | Token missing, malformed or expired | Reject the request with `401` |

Store the user's **`id`** (a UUID) as the reference to the user in your own data; it
never changes, unlike the email address.

## User management (administrators)

Staff users manage accounts under `/api/v1/users/`: list with search, filters and
sorting, create, update, **deactivate** (the user's tokens stop working immediately),
re-activate, set a password and delete. Superuser accounts can only be changed by
superusers, `is_superuser` cannot be set through the API, and administrators cannot
deactivate, demote or delete themselves.

## Try it in Swagger

1. Call **login** (or **register**) below and copy `tokens.access` from the response.
2. Click **Authorize**, paste the token and confirm. Swagger sends it as a Bearer token
   on every request and remembers it across page reloads.

## Conventions

- **Versioning:** every endpoint lives under `/api/v1/`.
- **Format:** JSON requests and responses; timestamps are ISO 8601 in UTC.
- **Pagination:** list endpoints return `count`, `next`, `previous` and `results`; use
  `?page=` and `?page_size=` (default 20, max 100).
- **Errors:** `{{"detail": "..."}}` for authentication and permission errors;
  `{{"<field>": ["..."]}}` for validation errors, or `non_field_errors` when no single
  field is at fault.
- **Rate limits:** register and login {throttle_rates.get("auth", "-")} per IP address;
  other anonymous requests {throttle_rates.get("anon", "-")}; authenticated requests
  {throttle_rates.get("user", "-")}. Exceeding a limit returns `429 Too Many Requests`.
- **Health:** `GET /api/v1/health/` reports service and database status for load
  balancers (`200` healthy, `503` degraded).
""".strip()
