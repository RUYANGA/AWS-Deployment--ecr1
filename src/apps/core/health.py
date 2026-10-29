from django.db import connection

HEALTH_PATH = "/api/v1/health/"


def health_report():
    """Return (payload, http_status) describing service and database health."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "ok"
    except Exception:
        db_status = "unavailable"
    healthy = db_status == "ok"
    payload = {"status": "ok" if healthy else "degraded", "database": db_status}
    return payload, 200 if healthy else 503
