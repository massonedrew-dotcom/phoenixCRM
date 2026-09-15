import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base for errors rendered as {"detail": ..., "code": ...}."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "BAD_REQUEST"
    detail: str = "Некорректный запрос"

    def __init__(self, detail: str | None = None, code: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        if code is not None:
            self.code = code
        super().__init__(self.detail)


class NotAuthenticated(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "NOT_AUTHENTICATED"
    detail = "Требуется вход в систему"


class InvalidCredentials(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "INVALID_CREDENTIALS"
    detail = "Неверный логин или пароль"


class Forbidden(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"
    detail = "Недостаточно прав"


class NotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"
    detail = "Не найдено"


class Conflict(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"
    detail = "Конфликт данных"


class FileTooLarge(AppError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    code = "FILE_TOO_LARGE"
    detail = "Файл слишком большой"


class UnsupportedMediaType(AppError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    code = "UNSUPPORTED_MEDIA_TYPE"
    detail = "Неподдерживаемый тип файла"


class RateLimited(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "RATE_LIMITED"
    detail = "Слишком много попыток входа. Повторите через минуту"


def _error_response(status_code: int, detail: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail, "code": code})


async def _app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    response = _error_response(exc.status_code, exc.detail, exc.code)
    if isinstance(exc, NotAuthenticated | InvalidCredentials):
        response.headers["WWW-Authenticate"] = "Bearer"
    return response


HTTP_STATUS_DETAILS = {
    status.HTTP_404_NOT_FOUND: ("Не найдено", "NOT_FOUND"),
    status.HTTP_405_METHOD_NOT_ALLOWED: ("Метод не поддерживается", "METHOD_NOT_ALLOWED"),
}


async def _http_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    detail, code = HTTP_STATUS_DETAILS.get(exc.status_code, (str(exc.detail), "HTTP_ERROR"))
    return _error_response(exc.status_code, detail, code)


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return _error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "Внутренняя ошибка сервера", "INTERNAL_ERROR"
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
