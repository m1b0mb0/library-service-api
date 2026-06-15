from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from borrowings.models import Borrowing
from borrowings.serializers import (
    BorrowingSerializer,
    BorrowingListSerializer,
    BorrowingDetailSerializer,
    BorrowingCreateSerializer,
    BorrowingListAdminSerializer,
    BorrowingDetailAdminSerializer,
)


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

        return serializer

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            queryset = self.queryset
        else:
            queryset = self.queryset.filter(user=self.request.user)

        if self.action in ("list", "retrieve"):
            if user.is_staff:
                queryset = queryset.select_related("book", "user")
            else:
                queryset = queryset.select_related("book")

            is_active = self.request.query_params.get("is_active")

            if is_active:
                is_active = is_active.lower() == "true"
                queryset = queryset.filter(actual_return_date__isnull=is_active)

        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
