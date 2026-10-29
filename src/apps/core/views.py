from django.db import connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    """Liveness/readiness probe for load balancers and container orchestrators."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["Health"],
        summary="Service health check",
        responses=inline_serializer(
            "HealthCheck",
            {"status": serializers.CharField(), "database": serializers.CharField()},
        ),
    )
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            db_status = "ok"
        except Exception:
            db_status = "unavailable"
        healthy = db_status == "ok"
        return Response(
            {"status": "ok" if healthy else "degraded", "database": db_status},
            status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        )
