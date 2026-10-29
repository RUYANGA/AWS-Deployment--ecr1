from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .health import health_report


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
        # Requests normally get answered by HealthCheckMiddleware; this view keeps
        # the endpoint in the OpenAPI schema and serves it if the middleware is off.
        payload, status = health_report()
        return Response(payload, status=status)
