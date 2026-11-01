"""Issue, email and check the one-time codes that verify a user's email address."""

import logging
import math
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from ..models import EmailOTP

logger = logging.getLogger(__name__)

_HMAC_SALT = "apps.accounts.email-otp"


class EmailOTPError(Exception):
    """A verification code was rejected.

    Attributes:
        code: Machine-readable reason: ``"missing"``, ``"expired"``, ``"locked"`` or
            ``"invalid"``.
        message: Human-readable explanation for API clients.
    """

    MESSAGES = {
        "missing": "No verification code is pending. Request a new code.",
        "expired": "The verification code has expired. Request a new code.",
        "locked": "Too many incorrect attempts. Request a new code.",
        "invalid": "The verification code is incorrect.",
    }

    def __init__(self, code):
        self.code = code
        self.message = self.MESSAGES[code]
        super().__init__(self.message)


def _hash_code(user, code):
    """Return a keyed hash of a code, bound to the user so hashes cannot be reused."""
    return salted_hmac(_HMAC_SALT, f"{user.pk}:{code}").hexdigest()


def issue_email_otp(user):
    """Create a new verification code for a user and email it to them.

    Any pending code is replaced. Sending failures are logged rather than raised, so the
    caller's request still succeeds and the user can ask for a new code.

    Args:
        user: The user whose email address is being verified.

    Returns:
        ``True`` if the email was handed to the email backend, ``False`` otherwise.
    """
    length = settings.EMAIL_OTP_LENGTH
    code = f"{secrets.randbelow(10**length):0{length}d}"
    now = timezone.now()
    ttl = settings.EMAIL_OTP_TTL_MINUTES
    EmailOTP.objects.update_or_create(
        user=user,
        defaults={
            "code_hash": _hash_code(user, code),
            "attempts": 0,
            "created_at": now,
            "expires_at": now + timedelta(minutes=ttl),
        },
    )
    try:
        send_mail(
            subject="Your Logistic verification code",
            message=(
                f"Hi {user.first_name},\n\n"
                f"Your verification code is {code}. It expires in {ttl} minutes.\n\n"
                "If you did not create a Logistic account, you can ignore this email."
            ),
            from_email=None,
            recipient_list=[user.email],
        )
    except Exception:
        logger.exception("Could not send the verification email to user %s", user.pk)
        return False
    return True


def seconds_until_resend(user):
    """Return how many seconds a user must wait before requesting a new code.

    Args:
        user: The user requesting a new code.

    Returns:
        Whole seconds left in the resend cooldown, or ``0`` if a code can be sent now.
    """
    otp = EmailOTP.objects.filter(user=user).only("created_at").first()
    if otp is None:
        return 0
    cooldown = timedelta(seconds=settings.EMAIL_OTP_RESEND_COOLDOWN_SECONDS)
    remaining = otp.created_at + cooldown - timezone.now()
    return max(0, math.ceil(remaining.total_seconds()))


def verify_email_otp(user, code):
    """Check a code and, if it is correct, mark the user's email address as verified.

    A correct code is consumed. A wrong code counts as a failed attempt; after
    ``EMAIL_OTP_MAX_ATTEMPTS`` failures the code stops working.

    Args:
        user: The user whose email address is being verified.
        code: The code the user entered.

    Raises:
        EmailOTPError: If there is no pending code, or it is expired, locked or wrong.
    """
    with transaction.atomic():
        otp = EmailOTP.objects.select_for_update().filter(user=user).first()
        if otp is None:
            error = "missing"
        elif otp.is_expired:
            error = "expired"
        elif otp.attempts >= settings.EMAIL_OTP_MAX_ATTEMPTS:
            error = "locked"
        elif not constant_time_compare(otp.code_hash, _hash_code(user, code)):
            error = "invalid"
            otp.attempts += 1
            otp.save(update_fields=["attempts"])
        else:
            error = None
            otp.delete()
            user.is_email_verified = True
            user.save(update_fields=["is_email_verified", "updated_at"])
    # Raised outside the atomic block so the failed-attempt counter is committed.
    if error is not None:
        raise EmailOTPError(error)
