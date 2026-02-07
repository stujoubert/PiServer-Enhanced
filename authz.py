from functools import wraps
from flask import session, redirect, url_for, abort, request

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "account_id" not in session:
            return redirect(url_for("auth.login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if session.get("role") not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator
