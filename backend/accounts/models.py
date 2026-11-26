"""
Custom user model: people log in with their email instead of a username.

Django's built-in User has a `username` field we don't want. AbstractBaseUser
gives us password hashing and login; PermissionsMixin adds the staff/superuser
flags and permissions that Django admin uses.
"""

import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


def normalize_email(email: str) -> str:
    """Emails are compared case-insensitively: 'Ana@Mail.rw' and 'ana@mail.rw' are one user."""
    return email.strip().lower()


class UserManager(BaseUserManager["User"]):
    """How to create users (used by registration and `createsuperuser`)."""

    use_in_migrations = True

    def create_user(self, email: str, password: str | None = None, **extra) -> "User":
        if not email:
            raise ValueError("Users must have an email address.")
        user = self.model(email=normalize_email(email), **extra)
        user.set_password(password)  # stores a salted hash, never the plain password
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra) -> "User":
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("A superuser must have is_staff=True and is_superuser=True.")
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False, help_text="Can log in to Django admin.")
    created_at = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"  # what people type to log in
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]  # asked for by `createsuperuser`, besides email+password

    class Meta:
        ordering = ["email"]

    def __str__(self) -> str:
        return self.email

    def save(self, *args, **kwargs) -> None:
        self.email = normalize_email(self.email)
        super().save(*args, **kwargs)
