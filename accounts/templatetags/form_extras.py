"""
Custom template filters for rendering Django form fields generically.
Needed because Django templates block access to dunder attributes
like __class__.__name__, so widget-type detection must happen here
in Python instead of directly in the template.
"""
from django import template
from django.forms.widgets import Textarea, Select, SelectMultiple

register = template.Library()


@register.filter
def widget_type(field):
    """
    Returns a simple string describing the field's widget type:
    'textarea', 'select', or 'input'.
    Usage in template: {{ field|widget_type }}
    """
    widget = field.field.widget
    if isinstance(widget, Textarea):
        return 'textarea'
    if isinstance(widget, (Select, SelectMultiple)):
        return 'select'
    return 'input'


@register.filter
def input_type(field):
    """
    Returns the HTML input type for simple Input-based widgets,
    defaulting to 'text' if not available.
    """
    return getattr(field.field.widget, 'input_type', 'text') or 'text'
