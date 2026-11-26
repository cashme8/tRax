from rest_framework import serializers
from rest_framework.fields import empty


class ExplicitBooleanField(serializers.BooleanField):
    """
    A boolean that must really be sent. DRF's BooleanField reads a value left
    out of an HTML-form request as False (browsers omit unticked checkboxes),
    so `required=True` never triggers. Here a missing value stays missing.
    Use it for flags with tax consequences, where a silent False is dangerous.
    """

    default_empty_html = empty
