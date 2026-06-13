from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from borrowings.models import Borrowing
from books.serializers import BookSerializer
from users.serializers import UserSerializer


class BorrowingSerializer(serializers.ModelSerializer):

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

    def validate(self, attrs):
        attrs = super().validate(attrs)

        borrow_date = attrs.get(
            "borrow_date", getattr(self.instance, "borrow_date", None)
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
    user = serializers.CharField(source="user.email", read_only=True)


class BorrowingDetailSerializer(BorrowingSerializer):
    book = BookSerializer(read_only=True)
    user = UserSerializer(read_only=True)
