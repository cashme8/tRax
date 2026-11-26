from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.views import LoginView, MeView, RegisterView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    # POST a refresh token → a new access token (the app does this every ~15 minutes).
    path("refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", MeView.as_view(), name="me"),
]
