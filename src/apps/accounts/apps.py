"""Application configuration for the accounts app."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Configuration for the accounts app (users and authentication)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Accounts"
