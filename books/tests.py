from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from books.models import Book
from books.serializers import BookSerializer


BOOK_URL = reverse("books:book-list")


def detail_url(book_id):
    return reverse("books:book-detail", args=[book_id])


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


class PublicBookApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list_books(self):
        sample_book(title="Atomic Habits")
        sample_book(title="Clean Code")

        res = self.client.get(BOOK_URL)

        books = Book.objects.all()
        serializer = BookSerializer(books, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_retrieve_book_detail(self):
        book = sample_book(title="The Pragmatic Programmer")

        url = detail_url(book.id)
        res = self.client.get(url)

        serializer = BookSerializer(book)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_create_book_forbidden_for_anonymous_user(self):
        payload = {
            "title": "New Book",
            "author": "New Author",
            "cover": Book.CoverChoices.SOFT,
            "inventory": 7,
            "daily_fee": "2.00",
        }

        res = self.client.post(BOOK_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Book.objects.filter(title=payload["title"]).exists())

    def test_update_book_forbidden_for_anonymous_user(self):
        book = sample_book(title="Original Title")
        payload = {"title": "Updated Title"}

        res = self.client.patch(detail_url(book.id), payload)
        book.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(book.title, "Original Title")

    def test_delete_book_forbidden_for_anonymous_user(self):
        book = sample_book()

        res = self.client.delete(detail_url(book.id))

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(Book.objects.filter(id=book.id).exists())


class AuthenticatedBookApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="user@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(self.user)

    def test_create_book_forbidden_for_regular_user(self):
        payload = {
            "title": "Regular User Book",
            "author": "Test Author",
            "cover": Book.CoverChoices.HARD,
            "inventory": 3,
            "daily_fee": "1.25",
        }

        res = self.client.post(BOOK_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Book.objects.filter(title=payload["title"]).exists())

    def test_update_book_forbidden_for_regular_user(self):
        book = sample_book(title="Original Title")
        payload = {"title": "Updated Title"}

        res = self.client.patch(detail_url(book.id), payload)
        book.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(book.title, "Original Title")

    def test_delete_book_forbidden_for_regular_user(self):
        book = sample_book()

        res = self.client.delete(detail_url(book.id))

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Book.objects.filter(id=book.id).exists())


class AdminBookApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = get_user_model().objects.create_user(
            email="admin@example.com",
            password="testpass123",
            is_staff=True,
        )
        self.client.force_authenticate(self.admin)

    def test_create_book(self):
        payload = {
            "title": "Admin Book",
            "author": "Admin Author",
            "cover": Book.CoverChoices.SOFT,
            "inventory": 9,
            "daily_fee": "3.75",
        }

        res = self.client.post(BOOK_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        book = Book.objects.get(id=res.data["id"])
        for key, value in payload.items():
            self.assertEqual(str(value), str(getattr(book, key)))

    def test_update_book(self):
        book = sample_book(title="Original Title")
        payload = {"title": "Updated Title", "inventory": 12}

        res = self.client.patch(detail_url(book.id), payload)
        book.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(book.title, payload["title"])
        self.assertEqual(book.inventory, payload["inventory"])

    def test_delete_book(self):
        book = sample_book()

        res = self.client.delete(detail_url(book.id))

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Book.objects.filter(id=book.id).exists())

    def test_book_str(self):
        book = sample_book(title="Django for APIs", author="William Vincent")

        self.assertEqual(str(book), "Django for APIs by William Vincent")
