from functools import wraps
from typing import Callable

from flask import request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from marshmallow import Schema

from app.services.exceptions import ForbiddenError


def require_user(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        if user_id is None:
            raise ForbiddenError("Usuário não autenticado.")
        return fn(int(user_id), *args, **kwargs)

    return wrapper


def validate_json(schema: Schema) -> Callable:
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            payload = schema.load(request.get_json(silent=True) or {})
            return fn(payload, *args, **kwargs)

        return wrapper

    return decorator


def validate_query(schema: Schema) -> Callable:
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            payload = schema.load(request.args.to_dict())
            return fn(payload, *args, **kwargs)

        return wrapper

    return decorator
