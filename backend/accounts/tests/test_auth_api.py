"""Register / login / refresh / me."""

import pytest
from rest_framework.test import APIClient

from accounts.models import User
from accounts.tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db

REGISTER = "/api/auth/register/"
LOGIN = "/api/auth/login/"
REFRESH = "/api/auth/refresh/"
ME = "/api/auth/me/"


def register(client: APIClient, **overrides):
    payload = {"email": "ana@example.rw", "full_name": "Ana Uwase", "password": DEFAULT_PASSWORD}
    payload.update(overrides)
    return client.post(REGISTER, payload, format="json")


# --- register -----------------------------------------------------------


def test_register_creates_user_and_returns_tokens(api_client):
    response = register(api_client)

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "ana@example.rw"
    assert body["user"]["full_name"] == "Ana Uwase"
    assert body["access"] and body["refresh"]
    assert "password" not in body["user"]

    user = User.objects.get(email="ana@example.rw")
    assert user.check_password(DEFAULT_PASSWORD)
    assert user.password != DEFAULT_PASSWORD  # stored hashed


def test_register_lowercases_email(api_client):
    register(api_client, email="  Ana@Example.RW ")
    assert User.objects.filter(email="ana@example.rw").exists()


def test_register_rejects_duplicate_email_case_insensitively(api_client):
    UserFactory(email="ana@example.rw")
    response = register(api_client, email="ANA@example.rw")
    assert response.status_code == 400
    assert "email" in response.json()


@pytest.mark.parametrize("weak", ["short", "12345678901", "password123"])
def test_register_rejects_weak_passwords(api_client, weak):
    response = register(api_client, password=weak)
    assert response.status_code == 400
    assert "password" in response.json()
    assert not User.objects.exists()


def test_register_requires_full_name(api_client):
    response = register(api_client, full_name="")
    assert response.status_code == 400
    assert "full_name" in response.json()


# --- login / refresh ----------------------------------------------------


def test_login_returns_tokens(api_client):
    UserFactory(email="ana@example.rw")
    response = api_client.post(
        LOGIN, {"email": "Ana@Example.rw", "password": DEFAULT_PASSWORD}, format="json"
    )
    assert response.status_code == 200
    assert {"access", "refresh"} <= response.json().keys()


def test_login_with_wrong_password_fails(api_client):
    UserFactory(email="ana@example.rw")
    response = api_client.post(
        LOGIN, {"email": "ana@example.rw", "password": "wrong-password"}, format="json"
    )
    assert response.status_code == 401


def test_inactive_user_cannot_log_in(api_client):
    UserFactory(email="ana@example.rw", is_active=False)
    response = api_client.post(
        LOGIN, {"email": "ana@example.rw", "password": DEFAULT_PASSWORD}, format="json"
    )
    assert response.status_code == 401


def test_refresh_gives_new_access_token(api_client):
    tokens = register(api_client).json()
    response = api_client.post(REFRESH, {"refresh": tokens["refresh"]}, format="json")
    assert response.status_code == 200
    assert response.json()["access"]


# --- me -----------------------------------------------------------------


def test_me_requires_login(api_client):
    assert api_client.get(ME).status_code == 401


def test_me_returns_current_user_with_bearer_token(api_client):
    access = register(api_client).json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    response = api_client.get(ME)

    assert response.status_code == 200
    assert response.json()["email"] == "ana@example.rw"


def test_me_can_update_full_name_but_not_email(api_client):
    access = register(api_client).json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    response = api_client.patch(
        ME, {"full_name": "Ana M. Uwase", "email": "hacker@example.rw"}, format="json"
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Ana M. Uwase"
    assert response.json()["email"] == "ana@example.rw"  # email is read-only


def test_garbage_token_is_rejected(api_client):
    api_client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
    assert api_client.get(ME).status_code == 401
