from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


CREATE_USER_URL = reverse("users:register")
MANAGE_USER_URL = reverse("users:manage")


def create_user(**params):
    return get_user_model().objects.create_user(**params)


class UserManagerTests(TestCase):
    def test_create_user_with_email_successful(self):
        email = "test@EXAMPLE.COM"
        password = "testpass123"

        user = create_user(email=email, password=password)

        self.assertEqual(user.email, email.lower())
        self.assertTrue(user.check_password(password))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_without_email_raises_error(self):
        with self.assertRaises(ValueError):
            create_user(email="", password="testpass123")

    def test_create_superuser_successful(self):
        email = "admin@example.com"
        password = "testpass123"

        user = get_user_model().objects.create_superuser(
            email=email,
            password=password,
        )

        self.assertEqual(user.email, email)
        self.assertTrue(user.check_password(password))
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_create_superuser_with_is_staff_false_raises_error(self):
        with self.assertRaises(ValueError):
            get_user_model().objects.create_superuser(
                email="admin@example.com",
                password="testpass123",
                is_staff=False,
            )

    def test_create_superuser_with_is_superuser_false_raises_error(self):
        with self.assertRaises(ValueError):
            get_user_model().objects.create_superuser(
                email="admin@example.com",
                password="testpass123",
                is_superuser=False,
            )


class PublicUserApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_create_user_successful(self):
        payload = {
            "email": "user@example.com",
            "password": "testpass123",
        }

        res = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        user = get_user_model().objects.get(email=payload["email"])
        self.assertTrue(user.check_password(payload["password"]))
        self.assertNotIn("password", res.data)
        self.assertFalse(res.data["is_staff"])

    def test_create_user_with_short_password_bad_request(self):
        payload = {
            "email": "user@example.com",
            "password": "pw",
        }

        res = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", res.data)
        self.assertFalse(
            get_user_model().objects.filter(email=payload["email"]).exists()
        )

    def test_manage_user_requires_authentication(self):
        res = self.client.get(MANAGE_USER_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateUserApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user(
            email="user@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(self.user)

    def test_retrieve_profile_successful(self):
        res = self.client.get(MANAGE_USER_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["email"], self.user.email)
        self.assertNotIn("password", res.data)

    def test_update_user_password(self):
        payload = {
            "password": "newpass123",
        }

        res = self.client.patch(MANAGE_USER_URL, payload)
        self.user.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(self.user.check_password(payload["password"]))

    def test_update_user_email_without_changing_password(self):
        old_password = self.user.password
        payload = {
            "email": "new@example.com",
        }

        res = self.client.patch(MANAGE_USER_URL, payload)
        self.user.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(self.user.email, payload["email"])
        self.assertEqual(self.user.password, old_password)
