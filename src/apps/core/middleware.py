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
        self.get_response = get_response

    def __call__(self, request):
        if request.path == HEALTH_PATH and request.method in ("GET", "HEAD"):
            payload, status = health_report()
            return JsonResponse(payload, status=status)
        return self.get_response(request)
