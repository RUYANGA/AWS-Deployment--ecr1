from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User

PASSWORD = "Str0ng-Passw0rd!"
NEW_PASSWORD = "An0ther-Str0ng-Pass!"


class ProfileUpdateTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="jane@example.com", password=PASSWORD, first_name="Jane", last_name="Doe"
        )
        User.objects.create_user(
            email="taken@example.com", password=PASSWORD, first_name="T", last_name="K"
        )
        self.client.force_authenticate(self.user)
        self.url = reverse("accounts:me")

    def patch(self, payload):
        return self.client.patch(self.url, payload, format="json")

    def test_update_names_and_phone_without_password(self):
        response = self.patch({"first_name": "Janet", "phone_number": "+250788000000"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "Janet")
        self.assertEqual(response.data["phone_number"], "+250788000000")
        self.assertNotIn("password", response.data)

    def test_change_email_requires_current_password(self):
        response = self.patch({"email": "new@example.com"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("current_password", response.data)

    def test_change_email_with_wrong_current_password(self):
        response = self.patch({"email": "new@example.com", "current_password": "wrong"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("current_password", response.data)

    def test_change_email(self):
        response = self.patch({"email": "New@Example.com", "current_password": PASSWORD})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "new@example.com")

    def test_change_email_to_taken_address(self):
        response = self.patch({"email": "TAKEN@example.com", "current_password": PASSWORD})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_password_confirm_must_match(self):
        response = self.patch(
            {
                "password": NEW_PASSWORD,
                "password_confirm": "different",
                "current_password": PASSWORD,
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password_confirm", response.data)

    def test_password_without_confirm_is_rejected(self):
        response = self.patch({"password": NEW_PASSWORD, "current_password": PASSWORD})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_weak_password_is_rejected(self):
        response = self.patch(
            {"password": "123", "password_confirm": "123", "current_password": PASSWORD}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_then_login(self):
        response = self.patch(
            {
                "password": NEW_PASSWORD,
                "password_confirm": NEW_PASSWORD,
                "current_password": PASSWORD,
            }
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(None)
        login = self.client.post(
            reverse("accounts:login"),
            {"email": "jane@example.com", "password": NEW_PASSWORD},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)

    def test_full_payload(self):
        response = self.patch(
            {
                "email": "jane.doe@example.com",
                "first_name": "Jane",
                "last_name": "Doe-Smith",
                "phone_number": "+250788111222",
                "password": NEW_PASSWORD,
                "password_confirm": NEW_PASSWORD,
                "current_password": PASSWORD,
            }
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "jane.doe@example.com")
        self.assertEqual(self.user.last_name, "Doe-Smith")
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
