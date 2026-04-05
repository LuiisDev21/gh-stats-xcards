"""Custom exception hierarchy and HTTP mappings."""

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base application exception with a default status code."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str) -> None:
        """Initialize an application exception.

        Args:
            message: Human-readable error details.
        """

        super().__init__(message)
        self.message = message


class GithubUserNotFound(AppError):
    """Raised when the provided GitHub user does not exist."""

    status_code = 404
    code = "github_user_not_found"


class GithubApiError(AppError):
    """Raised when GitHub GraphQL returns an unexpected error."""

    status_code = 502
    code = "github_api_error"


class GithubRateLimitError(AppError):
    """Raised when GitHub API rate limits the request."""

    status_code = 429
    code = "github_rate_limit"


class InvalidThemeError(AppError):
    """Raised when a requested theme is not supported."""

    status_code = 422
    code = "invalid_theme"


async def app_error_exception_handler(_: Request, exc: AppError) -> JSONResponse:
    """Convert :class:`AppError` instances into JSON error responses."""

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )

