import re
from datetime import timedelta

from django.core import mail
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import EmailOTP, User

PASSWORD = "Str0ng-Passw0rd!"


def sent_code():
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)


class AuthFlowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="jane@example.com",
            password=PASSWORD,
            first_name="Jane",
            last_name="Doe",
            is_email_verified=True,
        )

    def login(self, email="jane@example.com", password=PASSWORD):
        return self.client.post(
            reverse("accounts:login"), {"email": email, "password": password}, format="json"
        )

    def test_register_emails_a_code_and_issues_no_tokens(self):
        payload = {
            "email": "New@Example.com",
            "first_name": "New",
            "last_name": "User",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
        }
        response = self.client.post(reverse("accounts:register"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["email"], "new@example.com")
        self.assertFalse(response.data["user"]["is_email_verified"])
        self.assertNotIn("tokens", response.data)
        self.assertEqual(mail.outbox[0].to, ["new@example.com"])
        self.assertTrue(EmailOTP.objects.filter(user__email="new@example.com").exists())

    def test_register_rejects_duplicate_email(self):
        payload = {
            "email": "JANE@example.com",
            "first_name": "J",
            "last_name": "D",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
        }
        response = self.client.post(reverse("accounts:register"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_register_rejects_password_mismatch(self):
        payload = {
            "email": "x@example.com",
            "first_name": "X",
            "last_name": "Y",
            "password": PASSWORD,
            "password_confirm": "different",
        }
        response = self.client.post(reverse("accounts:register"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_success(self):
        response = self.login()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("refresh", response.data["tokens"])

    def test_login_wrong_password(self):
        response = self.login(password="wrong")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_me_requires_auth(self):
        response = self.client.get(reverse("accounts:me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_and_logout(self):
        tokens = self.login().data["tokens"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        me = self.client.get(reverse("accounts:me"))
        self.assertEqual(me.data["email"], "jane@example.com")

        logout = self.client.post(
            reverse("accounts:logout"), {"refresh": tokens["refresh"]}, format="json"
        )
        self.assertEqual(logout.status_code, status.HTTP_205_RESET_CONTENT)

        refresh = self.client.post(
            reverse("accounts:token-refresh"), {"refresh": tokens["refresh"]}, format="json"
        )
        self.assertEqual(refresh.status_code, status.HTTP_401_UNAUTHORIZED)


class EmailVerificationTests(APITestCase):
    def setUp(self):
        payload = {
            "email": "new@example.com",
            "first_name": "New",
            "last_name": "User",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
        }
        self.client.post(reverse("accounts:register"), payload, format="json")
        self.user = User.objects.get(email="new@example.com")

    def verify(self, code, email="new@example.com"):
        return self.client.post(
            reverse("accounts:verify-email"), {"email": email, "code": code}, format="json"
        )

    def resend(self, email="new@example.com"):
        return self.client.post(
            reverse("accounts:resend-verification"), {"email": email}, format="json"
        )

    def wrong_code(self):
        return "000000" if sent_code() != "000000" else "111111"

    def expire_cooldown(self):
        EmailOTP.objects.filter(user=self.user).update(
            created_at=timezone.now() - timedelta(hours=1)
        )

    def test_login_is_refused_until_verified(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "new@example.com", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "email_not_verified")

    def test_verify_returns_tokens_and_allows_login(self):
        response = self.verify(sent_code())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["user"]["is_email_verified"])
        self.assertIn("access", response.data["tokens"])

        login = self.client.post(
            reverse("accounts:login"),
            {"email": "new@example.com", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)

    def test_verify_twice_is_rejected(self):
        code = sent_code()
        self.verify(code)
        response = self.verify(code)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_verify_wrong_code(self):
        response = self.verify(self.wrong_code())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("code", response.data)

    def test_verify_malformed_code(self):
        response = self.verify("12ab")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_unknown_email(self):
        response = self.verify("123456", email="nobody@example.com")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_expired_code_then_resend(self):
        old = sent_code()
        EmailOTP.objects.filter(user=self.user).update(
            expires_at=timezone.now(), created_at=timezone.now() - timedelta(hours=1)
        )
        response = self.verify(old)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expired", str(response.data["code"][0]))

        self.assertEqual(self.resend().status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(self.verify(sent_code()).status_code, status.HTTP_200_OK)

    def test_resend_respects_cooldown(self):
        response = self.resend()
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("Retry-After", response.headers)
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_unlocks_after_too_many_attempts(self):
        wrong = self.wrong_code()
        with self.settings(EMAIL_OTP_MAX_ATTEMPTS=2):
            self.verify(wrong)
            self.verify(wrong)
            self.assertIn("Too many", str(self.verify(sent_code()).data["code"][0]))
            self.expire_cooldown()
            self.resend()
            self.assertEqual(self.verify(sent_code()).status_code, status.HTTP_200_OK)

    def test_resend_does_not_reveal_accounts(self):
        unknown = self.resend(email="nobody@example.com")
        self.assertEqual(unknown.status_code, status.HTTP_200_OK)
        self.verify(sent_code())
        verified = self.resend()
        self.assertEqual(verified.status_code, status.HTTP_200_OK)
        self.assertEqual(unknown.data, verified.data)
        self.assertEqual(len(mail.outbox), 1)

    def test_admin_created_users_are_verified(self):
        admin = User.objects.create_superuser(
            email="root@example.com", password=PASSWORD, first_name="R", last_name="U"
        )
        self.client.force_authenticate(admin)
        payload = {
            "email": "staff@example.com",
            "first_name": "S",
            "last_name": "T",
            "password": PASSWORD,
        }
        response = self.client.post(reverse("accounts:user-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.get(email="staff@example.com").is_email_verified)
