"""One-time code that verifies a user's email address."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class EmailOTP(models.Model):
    """The pending email-verification code of a user.

    A user has at most one pending code: issuing a new one replaces it. Only a keyed
    hash of the code is stored, never the code itself.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_otp"
    )
    code_hash = models.CharField(max_length=128)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name = "email verification code"
        verbose_name_plural = "email verification codes"

    def __str__(self):
        return f"Verification code for {self.user}"

    @property
    def is_expired(self):
        """Whether the code is past its expiry time."""
        return timezone.now() >= self.expires_at
