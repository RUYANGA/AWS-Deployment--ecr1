"""Service health checks used by load balancers and container orchestrators."""

from django.db import connection

#: URL path of the health endpoint, shared by the middleware and the URL config.
HEALTH_PATH = "/api/v1/health/"


def health_report():
    """Check whether the service can reach its database.

    Returns:
        A ``(payload, status_code)`` tuple. ``payload`` is
        ``{"status": "ok", "database": "ok"}`` with status 200 when the database
        answers, otherwise ``{"status": "degraded", "database": "unavailable"}`` with
        status 503.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "ok"
    except Exception:
        db_status = "unavailable"
    healthy = db_status == "ok"
    payload = {"status": "ok" if healthy else "degraded", "database": db_status}
    return payload, 200 if healthy else 503
