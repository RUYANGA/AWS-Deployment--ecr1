import re
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import EmailOTP, User
from apps.accounts.utils import (
    EmailOTPError,
    issue_email_otp,
    seconds_until_resend,
    verify_email_otp,
)


def sent_code():
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)


class EmailOTPTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="jane@example.com", password="x", first_name="Jane", last_name="Doe"
        )

    def assert_rejected(self, code, reason):
        with self.assertRaises(EmailOTPError) as ctx:
            verify_email_otp(self.user, code)
        self.assertEqual(ctx.exception.code, reason)

    def test_new_users_are_unverified_and_superusers_verified(self):
        self.assertFalse(self.user.is_email_verified)
        root = User.objects.create_superuser(
            email="root@example.com", password="x", first_name="R", last_name="U"
        )
        self.assertTrue(root.is_email_verified)

    def test_issue_emails_a_code_and_stores_only_its_hash(self):
        self.assertTrue(issue_email_otp(self.user))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["jane@example.com"])
        self.assertNotEqual(EmailOTP.objects.get(user=self.user).code_hash, sent_code())

    def test_correct_code_verifies_and_is_consumed(self):
        issue_email_otp(self.user)
        verify_email_otp(self.user, sent_code())
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)
        self.assertFalse(EmailOTP.objects.filter(user=self.user).exists())

    def test_wrong_code_counts_attempts_then_locks(self):
        issue_email_otp(self.user)
        code = sent_code()
        wrong = "000000" if code != "000000" else "111111"
        with self.settings(EMAIL_OTP_MAX_ATTEMPTS=2):
            self.assert_rejected(wrong, "invalid")
            self.assert_rejected(wrong, "invalid")
            self.assertEqual(EmailOTP.objects.get(user=self.user).attempts, 2)
            self.assert_rejected(code, "locked")

    def test_expired_code_is_rejected(self):
        issue_email_otp(self.user)
        EmailOTP.objects.filter(user=self.user).update(expires_at=timezone.now())
        self.assert_rejected(sent_code(), "expired")

    def test_missing_code_is_rejected(self):
        self.assert_rejected("123456", "missing")

    def test_new_code_replaces_the_old_one(self):
        issue_email_otp(self.user)
        old = sent_code()
        EmailOTP.objects.filter(user=self.user).update(attempts=3)
        issue_email_otp(self.user)
        new = sent_code()
        self.assertEqual(EmailOTP.objects.filter(user=self.user).count(), 1)
        self.assertEqual(EmailOTP.objects.get(user=self.user).attempts, 0)
        if old != new:
            self.assert_rejected(old, "invalid")
        verify_email_otp(self.user, new)

    @override_settings(EMAIL_OTP_RESEND_COOLDOWN_SECONDS=60)
    def test_resend_cooldown(self):
        self.assertEqual(seconds_until_resend(self.user), 0)
        issue_email_otp(self.user)
        self.assertTrue(0 < seconds_until_resend(self.user) <= 60)
        EmailOTP.objects.filter(user=self.user).update(
            created_at=timezone.now() - timedelta(seconds=61)
        )
        self.assertEqual(seconds_until_resend(self.user), 0)

    def test_send_failure_is_reported_not_raised(self):
        with (
            mock.patch("apps.accounts.utils.otp.send_mail", side_effect=OSError("smtp down")),
            self.assertLogs("apps.accounts.utils.otp", level="ERROR"),
        ):
            self.assertFalse(issue_email_otp(self.user))
        self.assertTrue(EmailOTP.objects.filter(user=self.user).exists())
