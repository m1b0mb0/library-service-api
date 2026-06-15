from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from borrowings.models import Borrowing
from borrowings.serializers import (
    BorrowingSerializer,
    BorrowingListSerializer,
    BorrowingDetailSerializer,
    BorrowingCreateSerializer,
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
        serializer = self.serializer_class
        if self.action == "list":
            serializer = BorrowingListSerializer

        if self.action == "retrieve":
            serializer = BorrowingDetailSerializer

        if self.action == "create":
            serializer = BorrowingCreateSerializer

        return serializer

    def get_queryset(self):
        queryset = self.queryset.filter(user=self.request.user)

        if self.action in ("list", "retrieve"):
            queryset = queryset.select_related("book")

        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
