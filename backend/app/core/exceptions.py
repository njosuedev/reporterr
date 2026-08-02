"""Domain-level exceptions, mapped to HTTP responses by app.main exception handlers."""


class AppError(Exception):
    """Base class for all application (domain) errors."""

    status_code: int = 400

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class ValidationFailedError(AppError):
    status_code = 422


class UnauthorizedError(AppError):
    status_code = 401


class ForbiddenError(AppError):
    status_code = 403


class FileProcessingError(AppError):
    """Raised when an uploaded Excel file cannot be parsed or fails validation."""

    status_code = 422
