from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from books.models import Book
from books.serializers import BookSerializer
from borrowings.models import Borrowing
from borrowings.serializers import (
    BorrowingDetailAdminSerializer,
    BorrowingDetailSerializer,
    BorrowingListAdminSerializer,
    BorrowingListSerializer,
    BorrowingSerializer,
)
from users.serializers import UserSerializer


BORROWINGS_URL = reverse("borrowings:borrowing-list")


def detail_url(borrowing_id):
    return reverse("borrowings:borrowing-detail", args=[borrowing_id])


def sample_user(**params):
    defaults = {
        "email": f"user{get_user_model().objects.count() + 1}@example.com",
        "password": "testpass123",
    }
    defaults.update(params)

    return get_user_model().objects.create_user(**defaults)


def sample_book(**params):
    defaults = {
        "title": f"Book {Book.objects.count() + 1}",
        "author": "Test Author",
        "cover": Book.CoverChoices.HARD,
        "inventory": 5,
        "daily_fee": Decimal("1.50"),
    }
    defaults.update(params)

    return Book.objects.create(**defaults)


def sample_borrowing(**params):
    defaults = {
        "expected_return_date": timezone.localdate() + timedelta(days=7),
        "book": sample_book(),
        "user": sample_user(),
    }
    defaults.update(params)

    return Borrowing.objects.create(**defaults)


class BorrowingModelTests(TestCase):
    def test_create_borrowing_with_valid_dates(self):
        borrowing = sample_borrowing()

        self.assertIsNotNone(borrowing.id)
        self.assertIsNone(borrowing.actual_return_date)

    def test_expected_return_date_must_be_after_borrow_date(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                sample_borrowing(expected_return_date=timezone.localdate())

    def test_actual_return_date_can_equal_borrow_date(self):
        borrowing = sample_borrowing(actual_return_date=timezone.localdate())

        self.assertEqual(borrowing.actual_return_date, borrowing.borrow_date)

    def test_actual_return_date_cannot_be_before_borrow_date(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                sample_borrowing(
                    actual_return_date=timezone.localdate() - timedelta(days=1)
                )

    def test_borrowing_str(self):
        user = sample_user(email="reader@example.com")
        book = sample_book(title="Django for APIs", author="William Vincent")
        borrowing = sample_borrowing(user=user, book=book)

        self.assertEqual(
            str(borrowing),
            f"{user} borrowed Django for APIs by William Vincent",
        )


class BorrowingSerializerTests(TestCase):
    def test_actual_return_date_can_equal_borrow_date(self):
        borrowing = sample_borrowing()
        serializer = BorrowingSerializer(
            borrowing,
            data={"actual_return_date": borrowing.borrow_date},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_actual_return_date_cannot_be_before_borrow_date(self):
        borrowing = sample_borrowing()
        serializer = BorrowingSerializer(
            borrowing,
            data={"actual_return_date": borrowing.borrow_date - timedelta(days=1)},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("actual_return_date", serializer.errors)


class PublicBorrowingApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_authentication_required_to_list_borrowings(self):
        res = self.client.get(BORROWINGS_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authentication_required_to_retrieve_borrowing(self):
        borrowing = sample_borrowing()

        res = self.client.get(detail_url(borrowing.id))

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authentication_required_to_create_borrowing(self):
        book = sample_book()
        payload = {
            "book": book.id,
            "expected_return_date": timezone.localdate() + timedelta(days=7),
        }

        res = self.client.post(BORROWINGS_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Borrowing.objects.exists())


class PrivateBorrowingApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = sample_user(email="user@example.com")
        self.client.force_authenticate(self.user)

    def test_list_borrowings(self):
        sample_borrowing(
            book=sample_book(title="Atomic Habits"),
            user=self.user,
        )
        sample_borrowing(
            book=sample_book(title="Clean Code"),
            user=self.user,
        )

        res = self.client.get(BORROWINGS_URL)

        borrowings = Borrowing.objects.filter(user=self.user).select_related("book")
        serializer = BorrowingListSerializer(borrowings, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_list_borrowings_contains_short_book_info_without_user(self):
        borrowing = sample_borrowing(
            book=sample_book(title="The Pragmatic Programmer"),
            user=self.user,
        )

        res = self.client.get(BORROWINGS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data[0]["id"], borrowing.id)
        self.assertEqual(res.data[0]["book"], "The Pragmatic Programmer")
        self.assertNotIn("user", res.data[0])

    def test_list_borrowings_returns_only_current_user_borrowings(self):
        own_borrowing = sample_borrowing(user=self.user)
        other_borrowing = sample_borrowing(user=sample_user(email="other@example.com"))

        res = self.client.get(BORROWINGS_URL)

        borrowing_ids = [borrowing["id"] for borrowing in res.data]

        self.assertIn(own_borrowing.id, borrowing_ids)
        self.assertNotIn(other_borrowing.id, borrowing_ids)

    def test_user_id_filter_does_not_expose_other_user_borrowings(self):
        own_borrowing = sample_borrowing(user=self.user)
        other_user = sample_user(email="other@example.com")
        other_borrowing = sample_borrowing(user=other_user)

        res = self.client.get(BORROWINGS_URL, {"user_id": other_user.id})

        borrowing_ids = [borrowing["id"] for borrowing in res.data]

        self.assertIn(own_borrowing.id, borrowing_ids)
        self.assertNotIn(other_borrowing.id, borrowing_ids)

    def test_filter_borrowings_by_active_status(self):
        active_borrowing = sample_borrowing(user=self.user)
        returned_borrowing = sample_borrowing(
            user=self.user,
            actual_return_date=timezone.localdate(),
        )

        res = self.client.get(BORROWINGS_URL, {"is_active": "true"})

        borrowing_ids = [borrowing["id"] for borrowing in res.data]

        self.assertIn(active_borrowing.id, borrowing_ids)
        self.assertNotIn(returned_borrowing.id, borrowing_ids)

    def test_filter_borrowings_by_returned_status(self):
        active_borrowing = sample_borrowing(user=self.user)
        returned_borrowing = sample_borrowing(
            user=self.user,
            actual_return_date=timezone.localdate(),
        )

        res = self.client.get(BORROWINGS_URL, {"is_active": "false"})

        borrowing_ids = [borrowing["id"] for borrowing in res.data]

        self.assertNotIn(active_borrowing.id, borrowing_ids)
        self.assertIn(returned_borrowing.id, borrowing_ids)

    def test_retrieve_borrowing_detail(self):
        borrowing = sample_borrowing(user=self.user)

        res = self.client.get(detail_url(borrowing.id))

        serializer = BorrowingDetailSerializer(borrowing)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_retrieve_borrowing_detail_contains_nested_book_and_user(self):
        book = sample_book(title="Clean Architecture", author="Robert Martin")
        borrowing = sample_borrowing(book=book, user=self.user)

        res = self.client.get(detail_url(borrowing.id))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["id"], borrowing.id)
        self.assertEqual(res.data["book"], BookSerializer(book).data)
        self.assertNotIn("user", res.data)

    def test_retrieve_other_user_borrowing_not_found(self):
        borrowing = sample_borrowing(user=sample_user(email="other@example.com"))

        res = self.client.get(detail_url(borrowing.id))

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_borrowing(self):
        book = sample_book(inventory=3)
        payload = {
            "book": book.id,
            "expected_return_date": timezone.localdate() + timedelta(days=7),
        }

        res = self.client.post(BORROWINGS_URL, payload)
        book.refresh_from_db()
        borrowing = Borrowing.objects.get(id=res.data["id"])

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(borrowing.book, book)
        self.assertEqual(borrowing.user, self.user)
        self.assertEqual(book.inventory, 2)
        self.assertNotIn("user", res.data)

    def test_create_borrowing_with_no_book_inventory_forbidden(self):
        book = sample_book(inventory=0)
        payload = {
            "book": book.id,
            "expected_return_date": timezone.localdate() + timedelta(days=7),
        }

        res = self.client.post(BORROWINGS_URL, payload)
        book.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("book", res.data)
        self.assertEqual(book.inventory, 0)
        self.assertFalse(Borrowing.objects.filter(book=book).exists())

    def test_create_borrowing_with_expected_return_date_today_forbidden(self):
        book = sample_book(inventory=3)
        payload = {
            "book": book.id,
            "expected_return_date": timezone.localdate(),
        }

        res = self.client.post(BORROWINGS_URL, payload)
        book.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expected_return_date", res.data)
        self.assertEqual(book.inventory, 3)
        self.assertFalse(Borrowing.objects.filter(book=book).exists())


class AdminBorrowingApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = sample_user(email="admin@example.com", is_staff=True)
        self.client.force_authenticate(self.admin)

    def test_list_all_borrowings(self):
        sample_borrowing(user=sample_user(email="first@example.com"))
        sample_borrowing(user=sample_user(email="second@example.com"))

        res = self.client.get(BORROWINGS_URL)

        borrowings = Borrowing.objects.select_related("book", "user")
        serializer = BorrowingListAdminSerializer(borrowings, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_admin_list_borrowings_contains_user_info(self):
        user = sample_user(email="reader@example.com")
        borrowing = sample_borrowing(
            book=sample_book(title="The Pragmatic Programmer"),
            user=user,
        )

        res = self.client.get(BORROWINGS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data[0]["id"], borrowing.id)
        self.assertEqual(res.data[0]["book"], "The Pragmatic Programmer")
        self.assertEqual(res.data[0]["user"], user.email)

    def test_filter_borrowings_by_user_id(self):
        target_user = sample_user(email="target@example.com")
        other_user = sample_user(email="other@example.com")
        target_borrowing = sample_borrowing(user=target_user)
        other_borrowing = sample_borrowing(user=other_user)

        res = self.client.get(BORROWINGS_URL, {"user_id": target_user.id})

        borrowing_ids = [borrowing["id"] for borrowing in res.data]

        self.assertIn(target_borrowing.id, borrowing_ids)
        self.assertNotIn(other_borrowing.id, borrowing_ids)

    def test_filter_all_borrowings_by_active_status(self):
        active_borrowing = sample_borrowing(user=sample_user(email="active@example.com"))
        returned_borrowing = sample_borrowing(
            user=sample_user(email="returned@example.com"),
            actual_return_date=timezone.localdate(),
        )

        res = self.client.get(BORROWINGS_URL, {"is_active": "true"})

        borrowing_ids = [borrowing["id"] for borrowing in res.data]

        self.assertIn(active_borrowing.id, borrowing_ids)
        self.assertNotIn(returned_borrowing.id, borrowing_ids)

    def test_filter_user_borrowings_by_active_status(self):
        target_user = sample_user(email="target@example.com")
        active_borrowing = sample_borrowing(user=target_user)
        returned_borrowing = sample_borrowing(
            user=target_user,
            actual_return_date=timezone.localdate(),
        )
        other_user_borrowing = sample_borrowing(
            user=sample_user(email="other@example.com")
        )

        res = self.client.get(
            BORROWINGS_URL,
            {"user_id": target_user.id, "is_active": "true"},
        )

        borrowing_ids = [borrowing["id"] for borrowing in res.data]

        self.assertIn(active_borrowing.id, borrowing_ids)
        self.assertNotIn(returned_borrowing.id, borrowing_ids)
        self.assertNotIn(other_user_borrowing.id, borrowing_ids)

    def test_retrieve_any_borrowing_detail(self):
        user = sample_user(email="reader@example.com")
        borrowing = sample_borrowing(user=user)

        res = self.client.get(detail_url(borrowing.id))

        serializer = BorrowingDetailAdminSerializer(borrowing)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_admin_retrieve_borrowing_detail_contains_nested_user(self):
        user = sample_user(
            email="reader@example.com",
            first_name="Test",
            last_name="Reader",
        )
        borrowing = sample_borrowing(user=user)

        res = self.client.get(detail_url(borrowing.id))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["id"], borrowing.id)
        self.assertEqual(res.data["user"], UserSerializer(user).data)

    def test_create_borrowing_with_past_expected_return_date_forbidden(self):
        book = sample_book(inventory=3)
        payload = {
            "book": book.id,
            "expected_return_date": timezone.localdate() - timedelta(days=1),
        }

        res = self.client.post(BORROWINGS_URL, payload)
        book.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expected_return_date", res.data)
        self.assertEqual(book.inventory, 3)
        self.assertFalse(Borrowing.objects.filter(book=book).exists())
