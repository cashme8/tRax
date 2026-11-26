"""
Celery app. The worker container runs:  celery -A config worker

Tasks live in each Django app's `tasks.py` and are discovered automatically.
Planned (later milestones):
  TODO(compliance): deadline reminders 7/3/1 days before (email + SMS via Africa's Talking)
  TODO(accounting): EBM/VSDC receipt sync
  TODO(reports): return generation, nightly recalculation
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("trax")
# Reads every setting that starts with CELERY_ from Django settings.
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True)
def ping(self) -> str:
    """Smoke-test task: proves the worker receives jobs from Redis."""
    return "pong"
