import logging
from typing import Generic, TypeVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

T = TypeVar("T")
logger = logging.getLogger(__name__)


class R(BaseModel, Generic[T]):
    success: bool = True
    code: int = 0
    message: str = "OK"
    data: T | None = None


class ApplicationError(RuntimeError):
    def __init__(self, status_code: int, code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def ok(data: T) -> R[T]:
    return R(data=data)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApplicationError)
    async def handle_application_error(
        _request: Request,
        exc: ApplicationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=R[object](
                success=False,
                code=exc.code,
                message=exc.message,
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request,
        _exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=R[object](
                success=False,
                code=42200,
                message="Invalid request parameters",
            ).model_dump(),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        _request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=R[object](
                success=False,
                code=exc.status_code * 100,
                message=str(exc.detail),
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled request error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=R[object](
                success=False,
                code=50000,
                message="Internal server error",
            ).model_dump(),
        )
