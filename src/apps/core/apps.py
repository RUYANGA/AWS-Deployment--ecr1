"""Application configuration for the core app."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Configuration for the core app (cross-cutting features such as health checks)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
