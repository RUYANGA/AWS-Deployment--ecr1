"""Middleware for the core app."""

from django.http import JsonResponse

from .health import HEALTH_PATH, health_report


class HealthCheckMiddleware:
    """Answer load balancer health checks before host validation and HTTPS redirect.

    ALB / ECS health checks call the instance's private IP over plain HTTP, so
    they would be rejected by ALLOWED_HOSTS (400) or redirected to HTTPS (301).
    This middleware must be first in MIDDLEWARE: it never calls
    request.get_host(), so only the health endpoint skips those checks.
    """

    def __init__(self, get_response):
        """Store the next handler in the middleware chain."""
        self.get_response = get_response

    def __call__(self, request):
        """Answer health check requests directly; pass everything else on.

        Args:
            request: The incoming HTTP request.

        Returns:
            A JSON health response for ``GET``/``HEAD`` on the health path, otherwise
            the response from the rest of the middleware chain.
        """
        if request.path == HEALTH_PATH and request.method in ("GET", "HEAD"):
            payload, status = health_report()
            return JsonResponse(payload, status=status)
        return self.get_response(request)
