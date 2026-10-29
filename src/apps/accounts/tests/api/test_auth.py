from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User

PASSWORD = "Str0ng-Passw0rd!"


class AuthFlowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="jane@example.com", password=PASSWORD, first_name="Jane", last_name="Doe"
        )

    def login(self, email="jane@example.com", password=PASSWORD):
        return self.client.post(
            reverse("accounts:login"), {"email": email, "password": password}, format="json"
        )

    def test_register_returns_user_and_tokens(self):
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
        self.assertIn("access", response.data["tokens"])
        self.assertTrue(User.objects.filter(email="new@example.com").exists())

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
