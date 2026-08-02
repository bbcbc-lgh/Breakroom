from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from CyberTown.Observability.RequestContext import get_request_id


class PublicError(Exception):
    def __init__(self, status_code: int, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable


def _payload(code: str, message: str, retryable: bool) -> dict:
    return {
        "request_id": get_request_id(),
        "error": {"code": code, "message": message, "retryable": retryable},
    }


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(PublicError)
    async def handle_public_error(_request: Request, exc: PublicError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(exc.code, exc.message, exc.retryable),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_payload("INVALID_REQUEST", "请求字段无效，请检查后重试。", False),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=_payload("INTERNAL_ERROR", "服务暂时无法完成请求，请稍后重试。", True),
        )
