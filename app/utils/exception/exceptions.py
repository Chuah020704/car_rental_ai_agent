"""Domain exception hierarchy.

Every exception the app raises *on purpose* (as opposed to a bug) inherits from
AppException. app_car_rental.py registers one FastAPI exception handler per
subclass so each maps to a sensible HTTP status code and a safe, generic message
for the frontend — the real `detail` is logged, never leaked to the client.
"""


class AppException(Exception):
    """Base class for every intentionally-raised application error."""

    status_code: int = 500

    def __init__(self, detail: str, user_message: str | None = None) -> None:
        self.detail = detail
        self.user_message = user_message
        super().__init__(detail)


class ConfigurationException(AppException):
    """Raised when config.yaml or required settings fail to load."""

    status_code = 500


class ModelServiceException(AppException):
    """Raised when an LLM provider call fails (timeout, auth, rate limit)."""

    status_code = 502


class RAGServiceException(AppException):
    """Raised when the vector store / retriever is unavailable or misconfigured."""

    status_code = 502


class ReservationNotFoundException(AppException):
    """Raised when a reservation ID doesn't exist in the repository."""

    status_code = 404


class VehicleNotFoundException(AppException):
    """Raised when a vehicle ID doesn't exist in the repository."""

    status_code = 404


class NotAuthorizedException(AppException):
    """Raised when the authenticated customer doesn't own the resource requested."""

    status_code = 403


class InvalidStateTransitionException(AppException):
    """Raised when a reservation mutation is rejected by a business rule."""

    status_code = 409


class InternalServerException(AppException):
    """Catch-all for unexpected internal failures."""

    status_code = 500
