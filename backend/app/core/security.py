from hmac import compare_digest

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()
        if _is_public_request(request) or not settings.api_auth_token:
            return await call_next(request)

        supplied = request.headers.get("x-api-key") or request.query_params.get("api_key")
        if not supplied or not compare_digest(supplied, settings.api_auth_token):
            return JSONResponse({"detail": "Invalid or missing API key"}, status_code=401)
        return await call_next(request)


def _is_public_request(request: Request) -> bool:
    if request.method == "OPTIONS":
        return True
    return request.url.path in {"/health", "/docs", "/openapi.json", "/redoc"}
