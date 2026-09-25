"""Ограничение частоты запросов (rate limiting) — фиксированное окно в Redis.

По умолчанию 100 запросов в минуту на пользователя (или IP для анонимных запросов),
для входа в систему и публичного приёма лидов — строже, для защиты от перебора и спама.
"""
import logging
import time

import jwt
import redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings

log = logging.getLogger(__name__)

_client: redis.Redis | None = None
_memory: dict[str, tuple[int, int]] = {}


def _redis() -> redis.Redis | None:
    global _client
    if _client is None:
        try:
            _client = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=0.3, socket_connect_timeout=0.3)
        except Exception:
            return None
    return _client


def hit(key: str, limit: int, window: int = 60) -> tuple[bool, int]:
    """Возвращает (разрешено, осталось)."""
    bucket = int(time.time() // window)
    full = f"rl:{key}:{bucket}"
    try:
        r = _redis()
        if r is None:
            raise redis.RedisError("no redis")
        pipe = r.pipeline()
        pipe.incr(full)
        pipe.expire(full, window + 5)
        count = pipe.execute()[0]
    except redis.RedisError:
        # Redis недоступен — считаем в памяти процесса (деградация, но без отказа в обслуживании)
        prev_bucket, count = _memory.get(key, (bucket, 0))
        count = count + 1 if prev_bucket == bucket else 1
        _memory[key] = (bucket, count)
    return count <= limit, max(limit - count, 0)


def client_ip(request: Request) -> str:
    """IP клиента: заголовок X-Real-IP выставляет nginx (клиентские значения он перезаписывает).
    Порт API наружу не публикуется, поэтому подделать заголовок в обход nginx нельзя."""
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    return request.client.host if request.client else "unknown"


_ip = client_ip


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/") or request.method == "OPTIONS" or path in ("/api/health",):
            return await call_next(request)
        if path.endswith("/auth/login") or path.endswith("/auth/2fa"):
            key, limit = f"login:{_ip(request)}", settings.LOGIN_RATE_LIMIT_PER_MINUTE
        elif "/public/" in path:
            key, limit = f"public:{_ip(request)}", 30
        else:
            key, limit = f"ip:{_ip(request)}", settings.RATE_LIMIT_PER_MINUTE
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                try:
                    payload = jwt.decode(auth[7:], settings.SECRET_KEY, algorithms=["HS256"])
                    key = f"user:{payload['sub']}"
                except jwt.PyJWTError:
                    pass
        allowed, remaining = hit(key, limit)
        if not allowed:
            return JSONResponse({"detail": "Слишком много запросов. Подождите минуту и повторите."}, status_code=429,
                                headers={"Retry-After": "60", "X-RateLimit-Limit": str(limit)})
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
