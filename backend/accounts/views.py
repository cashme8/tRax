from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.models import User
from accounts.serializers import (
    EmailTokenObtainPairSerializer,
    RegisterSerializer,
    UserSerializer,
)


class RegisterView(generics.CreateAPIView):
    """POST email, full_name, password → the new user plus access/refresh tokens."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []  # ignore any (possibly stale) token sent with a signup
    # TODO(before production): rate-limit signups and logins (DRF throttling).


class LoginView(TokenObtainPairView):
    """POST email, password → access token (short-lived) + refresh token."""

    serializer_class = EmailTokenObtainPairSerializer


class MeView(generics.RetrieveUpdateAPIView):
    """GET the logged-in user; PATCH to change full_name."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self) -> User:
        return self.request.user
