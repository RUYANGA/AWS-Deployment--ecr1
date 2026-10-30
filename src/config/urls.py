"""Root URL configuration.

All API routes are versioned under ``/api/v1/``. The OpenAPI schema, Swagger UI and
ReDoc are only routed when ``ENABLE_API_DOCS`` is true.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

api_v1 = [
    path("", include("apps.accounts.api.urls")),
    path("", include("apps.core.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
]

# API documentation (toggled with ENABLE_API_DOCS)
if settings.ENABLE_API_DOCS:
    urlpatterns += [
        path("", RedirectView.as_view(pattern_name="swagger-ui", permanent=False)),
        path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
        path(
            "api/v1/docs/",
            SpectacularSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
        path("api/v1/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    ]
