"""
Role-based access decorators.
Usage:
    @coordinator_required
    def my_view(request): ...
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def role_required(*roles):
    """Generic decorator: allows access if user.role is in the given roles list."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            if request.user.role not in roles and not request.user.is_superuser:
                messages.error(request, "You don't have permission to access that page.")
                return redirect('accounts:dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# Convenience shortcuts — import these directly in views
def coordinator_required(view_func):
    return role_required('coordinator')(view_func)

def student_required(view_func):
    return role_required('student')(view_func)

def supervisor_required(view_func):
    return role_required('supervisor')(view_func)

def supervisor_or_coordinator_required(view_func):
    return role_required('supervisor', 'coordinator')(view_func)
