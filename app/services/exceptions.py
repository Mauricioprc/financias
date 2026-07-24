class ServiceError(Exception):
    code = "SERVICE_ERROR"
    status_code = 400

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(ServiceError):
    code = "NOT_FOUND"
    status_code = 404


class ValidationError(ServiceError):
    code = "VALIDATION_ERROR"
    status_code = 422


class ForbiddenError(ServiceError):
    code = "FORBIDDEN"
    status_code = 403


class ConflictError(ServiceError):
    code = "CONFLICT"
    status_code = 409
