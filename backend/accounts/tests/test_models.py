import uuid

import pytest

from accounts.models import User

pytestmark = pytest.mark.django_db


def test_user_has_uuid_primary_key():
    user = User.objects.create_user("ana@example.rw", "x-Strong-Pass-1", full_name="Ana")
    assert isinstance(user.pk, uuid.UUID)


def test_create_user_requires_email():
    with pytest.raises(ValueError):
        User.objects.create_user("", "x-Strong-Pass-1")


def test_create_superuser_sets_flags():
    admin = User.objects.create_superuser("root@example.rw", "x-Strong-Pass-1", full_name="Root")
    assert admin.is_staff and admin.is_superuser


def test_regular_user_is_not_staff():
    user = User.objects.create_user("ana@example.rw", "x-Strong-Pass-1", full_name="Ana")
    assert not user.is_staff and not user.is_superuser
