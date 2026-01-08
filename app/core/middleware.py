from typing import Iterable, Set
from jose import jwt, JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config.settings import settings


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """Injects user_id into request.state when a valid access token is present."""

    def __init__(self, app, excluded_paths: Iterable[str] | None = None):
        super().__init__(app)
        self.excluded_paths: Set[str] = set(excluded_paths or [])

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if (
            path.startswith("/auth")
            or path.startswith("/docs")
            or path.startswith("/redoc")
            or path.startswith("/openapi")
            or path == "/health"
        ):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1]
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
                if payload.get("type") == "access" and payload.get("sub"):
                    request.state.user_id = int(payload["sub"])
            except JWTError:
                pass

        return await call_next(request)

