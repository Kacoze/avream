from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ApiError(Exception):
    code: str
    message: str
    status: int = 400
    details: dict[str, Any] | None = None
    retryable: bool = False

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def not_implemented(endpoint: str) -> ApiError:
    return ApiError(
        code="E_NOT_IMPLEMENTED",
        message="Endpoint is defined but not implemented yet",
        status=501,
        details={"endpoint": endpoint},
        retryable=False,
    )


def validation_error(message: str, details: dict[str, Any] | None = None) -> ApiError:
    return ApiError(code="E_VALIDATION", message=message, status=400, details=details, retryable=False)


def conflict_error(message: str, details: dict[str, Any] | None = None) -> ApiError:
    return ApiError(code="E_CONFLICT", message=message, status=409, details=details, retryable=False)


def busy_device_error(message: str, details: dict[str, Any] | None = None) -> ApiError:
    return ApiError(code="E_BUSY_DEVICE", message=message, status=409, details=details, retryable=True)


def permission_error(message: str, details: dict[str, Any] | None = None) -> ApiError:
    return ApiError(code="E_PERMISSION", message=message, status=403, details=details, retryable=False)


def dependency_error(message: str, details: dict[str, Any] | None = None) -> ApiError:
    return ApiError(code="E_DEP_MISSING", message=message, status=412, details=details, retryable=False)


def backend_error(message: str, details: dict[str, Any] | None = None, retryable: bool = True) -> ApiError:
    return ApiError(code="E_BACKEND_FAILED", message=message, status=502, details=details, retryable=retryable)


def timeout_error(message: str, details: dict[str, Any] | None = None) -> ApiError:
    return ApiError(code="E_TIMEOUT", message=message, status=504, details=details, retryable=True)


def unsupported_error(message: str, details: dict[str, Any] | None = None) -> ApiError:
    return ApiError(code="E_UNSUPPORTED", message=message, status=400, details=details, retryable=False)
