from unittest import mock

from django.db.utils import OperationalError
from django.test import TestCase, override_settings

from apps.core.health import HEALTH_PATH

# Mimic production: a real domain in ALLOWED_HOSTS and HTTPS enforced.
PRODUCTION_LIKE = {"ALLOWED_HOSTS": ["api.example.com"], "SECURE_SSL_REDIRECT": True}
ALB_PRIVATE_IP = "10.0.1.23"


@override_settings(**PRODUCTION_LIKE)
class HealthCheckTests(TestCase):
    def test_load_balancer_check_on_private_ip_over_http(self):
        response = self.client.get(HEALTH_PATH, HTTP_HOST=ALB_PRIVATE_IP)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})

    def test_head_request_is_supported(self):
        response = self.client.head(HEALTH_PATH, HTTP_HOST=ALB_PRIVATE_IP)
        self.assertEqual(response.status_code, 200)

    def test_database_down_returns_503(self):
        with mock.patch("apps.core.health.connection.cursor", side_effect=OperationalError):
            response = self.client.get(HEALTH_PATH, HTTP_HOST=ALB_PRIVATE_IP)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "degraded", "database": "unavailable"})

    def test_other_paths_still_reject_unknown_hosts(self):
        response = self.client.get("/api/v1/auth/me/", HTTP_HOST=ALB_PRIVATE_IP)
        self.assertEqual(response.status_code, 400)

    def test_other_paths_still_redirect_to_https(self):
        response = self.client.get("/api/v1/auth/me/", HTTP_HOST="api.example.com")
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response["Location"].startswith("https://"))
