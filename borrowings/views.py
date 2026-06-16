from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db.models import F
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from borrowings.models import Borrowing
from borrowings.serializers import (
    BorrowingSerializer,
    BorrowingListSerializer,
    BorrowingDetailSerializer,
    BorrowingCreateSerializer,
    BorrowingListAdminSerializer,
    BorrowingDetailAdminSerializer,
    BorrowingReturnSerializer,
)
from borrowings.notifications import send_telegram_message


class BorrowingViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Borrowing.objects.all()
    serializer_class = BorrowingSerializer
    permission_classes = (IsAuthenticated,)

    def get_serializer_class(self):
        user = self.request.user

        serializer = self.serializer_class
        if self.action == "list":
            if user.is_staff:
                serializer = BorrowingListAdminSerializer
            else:
                serializer = BorrowingListSerializer

        if self.action == "retrieve":
            if user.is_staff:
                serializer = BorrowingDetailAdminSerializer
            else:
                serializer = BorrowingDetailSerializer

        if self.action == "create":
            serializer = BorrowingCreateSerializer

        if self.action == "return_borrowing":
            serializer = BorrowingReturnSerializer

        return serializer

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            queryset = self.queryset
        else:
            queryset = self.queryset.filter(user=self.request.user)

        if self.action == "list":
            if user.is_staff:
                queryset = queryset.select_related("book", "user")

                user_id = self.request.query_params.get("user_id")
                if user_id:
                    queryset = queryset.filter(user__id=user_id)
            else:
                queryset = queryset.select_related("book")

            is_active = self.request.query_params.get("is_active")

            if is_active:
                is_active = is_active.lower()
                if is_active in ("true", "false"):
                    is_active = is_active == "true"
                    queryset = queryset.filter(actual_return_date__isnull=is_active)

        if self.action in ("retrieve", "return_borrowing"):
            if user.is_staff:
                queryset = queryset.select_related("book", "user")
            else:
                queryset = queryset.select_related("book")

        return queryset

    @staticmethod
    def build_borrowing_create_message(borrowing: Borrowing) -> str:
        return (
            "New borrowing created\n"
            f"Borrowing ID: {borrowing.id}\n"
            f"User: {borrowing.user.email}\n"
            f"Book: {borrowing.book.title}\n"
            f"Borrow date: {borrowing.borrow_date}\n"
            f"Expected return date: {borrowing.expected_return_date}"
        )

    def perform_create(self, serializer):
        with transaction.atomic():
            borrowing = serializer.save(user=self.request.user)
            message = self.build_borrowing_create_message(borrowing)

            transaction.on_commit(lambda: send_telegram_message(message))

    @action(detail=True, methods=["post"], url_path="return")
    def return_borrowing(self, request, pk=None):
        """Return borrowed book"""

        with transaction.atomic():
            borrowing = get_object_or_404(
                self.get_queryset().select_for_update(),
                pk=pk,
            )
            if borrowing.actual_return_date:
                return Response(
                    {"detail": "This borrowing has already been returned."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            borrowing.actual_return_date = timezone.localdate()
            borrowing.save(update_fields=["actual_return_date"])

            borrowing.book.inventory = F("inventory") + 1
            borrowing.book.save(update_fields=["inventory"])

        serializer = self.get_serializer(borrowing)
        return Response(serializer.data, status=status.HTTP_200_OK)
