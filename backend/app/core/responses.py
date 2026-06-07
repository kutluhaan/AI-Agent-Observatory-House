import uuid
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


# ─── Response Models ──────────────────────────────────────


class Meta(BaseModel):
    request_id: str


class SuccessResponse(BaseModel):
    success: bool = True
    data: Any
    meta: Meta


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict = {}


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
    meta: Meta


def success(data: Any, request_id: str | None = None) -> dict:
    return {
        "success": True,
        "data": data,
        "meta": {"request_id": request_id or str(uuid.uuid4())},
    }


def error(
    code: str,
    message: str,
    details: dict | None = None,
    request_id: str | None = None,
) -> dict:
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
        "meta": {"request_id": request_id or str(uuid.uuid4())},
    }


# ─── Custom Exceptions ────────────────────────────────────


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, code: str, message: str):
        super().__init__(code=code, message=message, status_code=404)


class ConflictError(AppError):
    def __init__(self, code: str, message: str):
        super().__init__(code=code, message=message, status_code=409)


class UnauthorizedError(AppError):
    def __init__(self, code: str, message: str):
        super().__init__(code=code, message=message, status_code=401)


class ForbiddenError(AppError):
    def __init__(self, code: str, message: str):
        super().__init__(code=code, message=message, status_code=403)


class ValidationError(AppError):
    def __init__(self, fields: list[dict]):
        super().__init__(
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            status_code=422,
            details={"fields": fields},
        )


class RateLimitError(AppError):
    def __init__(self, retry_after_seconds: int = 60):
        super().__init__(
            code="RATE_LIMIT_EXCEEDED",
            message="Too many requests. Please try again later.",
            status_code=429,
            details={"retry_after_seconds": retry_after_seconds},
        )


# ─── Exception Handlers ───────────────────────────────────


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error(
            code=exc.code,
            message=exc.message,
            details=exc.details,
        ),
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=error(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred. Please try again later.",
        ),
    )
