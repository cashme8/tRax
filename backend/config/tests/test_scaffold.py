"""Step 1 smoke tests: the project boots, the API answers, Celery is wired."""

import pytest
from django.conf import settings

from config.celery import app as celery_app
from config.celery import ping


# ATOMIC_REQUESTS wraps every request in a DB transaction, so even this needs the DB.
@pytest.mark.django_db
def test_health_endpoint_is_public(api_client):
    response = api_client.get("/api/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_requires_login_by_default():
    # Any endpoint that forgets to set permissions is locked, not open.
    assert settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] == [
        "rest_framework.permissions.IsAuthenticated"
    ]


def test_money_is_serialized_as_strings():
    assert settings.REST_FRAMEWORK["COERCE_DECIMAL_TO_STRING"] is True


def test_celery_ping_task_runs():
    # .apply() runs the task in-process, so this needs no Redis or worker.
    assert ping.apply().get() == "pong"
    assert celery_app.main == "trax"
