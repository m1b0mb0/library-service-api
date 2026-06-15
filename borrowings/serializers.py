from django.utils import timezone
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.db.models import F

from borrowings.models import Borrowing
from books.serializers import BookSerializer
from users.serializers import UserSerializer
from books.models import Book


class BorrowingSerializer(serializers.ModelSerializer):

    class Meta:
        model = Borrowing
        fields = (
            "id",
            "borrow_date",
            "expected_return_date",
            "actual_return_date",
            "book",
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)

        borrow_date = (
            attrs.get("borrow_date")
            or getattr(self.instance, "borrow_date", None)
            or timezone.localdate()
        )
        expected_return_date = attrs.get(
            "expected_return_date", getattr(self.instance, "expected_return_date", None)
        )
        actual_return_date = attrs.get(
            "actual_return_date", getattr(self.instance, "actual_return_date", None)
        )

        if borrow_date and expected_return_date and expected_return_date <= borrow_date:
            raise ValidationError(
                {
                    "expected_return_date": "Expected return date must be after borrow date."
                }
            )

        if borrow_date and actual_return_date and actual_return_date < borrow_date:
            raise ValidationError(
                {
                    "actual_return_date": "Actual return date cannot be before borrow date."
                }
            )

        return attrs


class BorrowingListSerializer(BorrowingSerializer):
    book = serializers.CharField(source="book.title", read_only=True)


class BorrowingListAdminSerializer(BorrowingSerializer):
    book = serializers.CharField(source="book.title", read_only=True)
    user = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = Borrowing
        fields = (
            "id",
            "borrow_date",
            "expected_return_date",
            "actual_return_date",
            "book",
            "user",
        )


class BorrowingDetailSerializer(BorrowingSerializer):
    book = BookSerializer(read_only=True)


class BorrowingDetailAdminSerializer(BorrowingListAdminSerializer):
    book = BookSerializer(read_only=True)
    user = UserSerializer(read_only=True)


class BorrowingCreateSerializer(BorrowingSerializer):

    class Meta:
        model = Borrowing
        fields = ("id", "book", "borrow_date", "expected_return_date")
        read_only_fields = ("id", "borrow_date")

    def create(self, validated_data):
        with transaction.atomic():
            book = Book.objects.select_for_update().get(id=validated_data["book"].id)

            if book.inventory < 1:
                raise ValidationError(
                    {"book": f"There are no available '{book.title}' books"}
                )

            borrowing = Borrowing.objects.create(**validated_data)

            book.inventory = F("inventory") - 1
            book.save(update_fields=["inventory"])

            return borrowing


class BorrowingReturnSerializer(serializers.ModelSerializer):
    book = BookSerializer(read_only=True)
    user = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = Borrowing
        fields = (
            "id",
            "user",
            "book",
            "borrow_date",
            "expected_return_date",
            "actual_return_date",
        )
        read_only_fields = (
            "id",
            "borrow_date",
            "expected_return_date",
            "actual_return_date",
        )
