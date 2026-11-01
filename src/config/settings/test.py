"""Test settings."""

from .base import *
from .base import REST_FRAMEWORK

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = ()
# Views that set throttle_classes explicitly (auth endpoints) are not throttled in tests.
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {"auth": None}
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
