import ipaddress
import uuid
from contextvars import ContextVar
from dataclasses import dataclass

from starlette.types import ASGIApp, Receive, Scope, Send


@dataclass
class RequestContext:
    """Per-request data read by the audit writer."""

    ip: str | None = None
    user_id: uuid.UUID | None = None


_request_context: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


def get_request_context() -> RequestContext:
    context = _request_context.get()
    if context is None:
        context = RequestContext()
        _request_context.set(context)
    return context


def _client_ip(scope: Scope) -> str | None:
    client = scope.get("client")
    if not client:
        return None
    try:
        return str(ipaddress.ip_address(client[0]))
    except ValueError:
        return None


class RequestContextMiddleware:
    """Creates a fresh RequestContext for every HTTP request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        token = _request_context.set(RequestContext(ip=_client_ip(scope)))
        try:
            await self.app(scope, receive, send)
        finally:
            _request_context.reset(token)
