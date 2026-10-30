from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User

PASSWORD = "Str0ng-Passw0rd!"


def make_user(email, **extra):
    return User.objects.create_user(
        email=email, password=PASSWORD, first_name="First", last_name="Last", **extra
    )


class UserManagementTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com", is_staff=True)
        self.alice = make_user("alice@example.com")
        self.bob = make_user("bob@example.com", is_active=False)
        self.root = User.objects.create_superuser(
            email="root@example.com", password=PASSWORD, first_name="Root", last_name="User"
        )
        self.client.force_authenticate(self.admin)

    def detail(self, user, name="user-detail"):
        return reverse(f"accounts:{name}", args=[user.pk])

    # --- access control -------------------------------------------------
    def test_anonymous_is_rejected(self):
        self.client.force_authenticate(None)
        response = self.client.get(reverse("accounts:user-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_regular_user_is_forbidden(self):
        self.client.force_authenticate(self.alice)
        response = self.client.get(reverse("accounts:user-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_cannot_modify_superuser(self):
        response = self.client.patch(self.detail(self.root), {"first_name": "X"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_can_modify_superuser(self):
        self.client.force_authenticate(self.root)
        other = User.objects.create_superuser(
            email="root2@example.com", password=PASSWORD, first_name="R", last_name="T"
        )
        response = self.client.patch(self.detail(other), {"first_name": "X"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # --- list -------------------------------------------------------------
    def test_list_is_paginated(self):
        response = self.client.get(reverse("accounts:user-list"), {"page_size": 2})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 4)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["next"])

    def test_search_and_filters(self):
        url = reverse("accounts:user-list")
        response = self.client.get(url, {"search": "alice"})
        self.assertEqual([u["email"] for u in response.data["results"]], ["alice@example.com"])
        response = self.client.get(url, {"is_active": "false"})
        self.assertEqual([u["email"] for u in response.data["results"]], ["bob@example.com"])

    def test_invalid_boolean_filter(self):
        response = self.client.get(reverse("accounts:user-list"), {"is_staff": "maybe"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_ordering(self):
        response = self.client.get(reverse("accounts:user-list"), {"ordering": "email"})
        emails = [u["email"] for u in response.data["results"]]
        self.assertEqual(emails, sorted(emails))

    # --- create / update ----------------------------------------------------
    def test_create_user(self):
        payload = {
            "email": "New@Example.com",
            "first_name": "New",
            "last_name": "User",
            "password": PASSWORD,
            "is_superuser": True,
        }
        response = self.client.post(reverse("accounts:user-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["email"], "new@example.com")
        self.assertFalse(response.data["is_superuser"])
        self.assertNotIn("password", response.data)

    def test_create_duplicate_email(self):
        payload = {
            "email": "ALICE@example.com",
            "first_name": "A",
            "last_name": "B",
            "password": PASSWORD,
        }
        response = self.client.post(reverse("accounts:user-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_create_weak_password(self):
        payload = {"email": "w@example.com", "first_name": "W", "last_name": "P", "password": "123"}
        response = self.client.post(reverse("accounts:user-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_user(self):
        response = self.client.patch(
            self.detail(self.alice), {"first_name": "Alicia", "is_staff": True}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.first_name, "Alicia")
        self.assertTrue(self.alice.is_staff)

    def test_update_email_to_existing_is_rejected(self):
        response = self.client.patch(
            self.detail(self.alice), {"email": "bob@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_demote_or_deactivate_self(self):
        for field in ("is_staff", "is_active"):
            response = self.client.patch(self.detail(self.admin), {field: False}, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, field)

    # --- actions -----------------------------------------------------------
    def test_deactivate_blocks_existing_tokens(self):
        access = str(RefreshToken.for_user(self.alice).access_token)
        response = self.client.post(self.detail(self.alice, "user-deactivate"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_active"])

        self.client.force_authenticate(None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.get(reverse("accounts:me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_activate(self):
        response = self.client.post(self.detail(self.bob, "user-activate"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_active"])

    def test_cannot_deactivate_self(self):
        response = self.client.post(self.detail(self.admin, "user-deactivate"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_set_password(self):
        new_password = "An0ther-Str0ng-Pass!"
        response = self.client.post(
            self.detail(self.alice, "user-set-password"),
            {"new_password": new_password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.check_password(new_password))

    # --- delete ------------------------------------------------------------
    def test_delete_user(self):
        response = self.client.delete(self.detail(self.alice))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(pk=self.alice.pk).exists())

    def test_cannot_delete_self(self):
        response = self.client.delete(self.detail(self.admin))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
