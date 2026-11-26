"""Test-data builders. UserFactory() makes a saved user with a unique email."""

import factory

from accounts.models import User

DEFAULT_PASSWORD = "Kigali-Strong-Pass-2026"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.rw")
    full_name = factory.Faker("name")
    password = factory.django.Password(DEFAULT_PASSWORD)  # stored hashed
