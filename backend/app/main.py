import logging

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

from app.api.v1 import (
    activities,
    analytics,
    auth,
    companies,
    contacts,
    data,
    deals,
    finance,
    leads,
    proposals,
    public,
    reference,
    tasks,
    users,
)
from app.core.config import settings
from app.core.ratelimit import RateLimitMiddleware
from app.db.session import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("crm")

DESCRIPTION = """
REST API CRM-системы для B2B-продаж.

**Аутентификация:** `POST /api/v1/auth/login` → `access_token` (15 мин) + `refresh_token` (7 дней).
Передавайте заголовок `Authorization: Bearer <access_token>`, обновляйте токен через `POST /api/v1/auth/refresh`.

**Приём лидов с сайта:** `POST /api/v1/public/leads` с заголовком `X-Api-Key` (ключ создаётся в разделе
«Администрирование → Интеграции»).

**Лимиты:** 100 запросов в минуту на пользователя, 10 попыток входа в минуту с IP, 30 заявок в минуту с IP.
"""

app = FastAPI(
    title=f"{settings.APP_NAME} API",
    version="1.0.0",
    description=DESCRIPTION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    # Публичный приём лидов вызывается с сайтов заказчика — разрешаем CORS для любых источников
    if request.url.path.startswith("/api/v1/public/") and request.method == "OPTIONS":
        return Response(status_code=204, headers={
            "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, X-Api-Key", "Access-Control-Max-Age": "86400"})
    response = await call_next(request)
    if request.url.path.startswith("/api/v1/public/"):
        response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.url.path.startswith("/api/") and not request.url.path.startswith(("/api/docs", "/api/redoc")):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


FIELD_RU = {"missing": "обязательное поле", "string_too_short": "слишком короткое значение",
            "string_too_long": "слишком длинное значение", "value_error": "некорректное значение",
            "greater_than_equal": "значение слишком мало", "less_than_equal": "значение слишком велико",
            "int_parsing": "ожидается число", "float_parsing": "ожидается число", "date_from_datetime_parsing":
            "некорректная дата", "literal_error": "недопустимое значение", "greater_than": "значение слишком мало"}


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = []
    for e in exc.errors():
        loc = ".".join(str(p) for p in e["loc"] if p not in ("body", "query"))
        msg = FIELD_RU.get(e["type"], e["msg"])
        if e["type"] == "value_error" and "email" in str(e.get("msg", "")).lower():
            msg = "некорректный email"
        errors.append({"field": loc, "message": msg})
    text_msg = "; ".join(f"{x['field']}: {x['message']}" for x in errors[:5])
    return JSONResponse({"detail": f"Проверьте данные — {text_msg}", "errors": errors}, status_code=422)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Необработанная ошибка %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Внутренняя ошибка сервера. Мы уже разбираемся."}, status_code=500)


api = APIRouter(prefix="/api/v1")
for module in (auth, users, reference, companies, contacts, leads, deals, tasks, activities, proposals, finance,
               analytics, data, public):
    api.include_router(module.router)
app.include_router(api)


@app.get("/api/health", tags=["Служебное"], summary="Проверка работоспособности (для мониторинга и балансировщика)")
def health():
    status = {"api": "ok"}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        status["database"] = "ok"
    except Exception:
        status["database"] = "error"
    try:
        from app.core.ratelimit import _redis

        r = _redis()
        status["redis"] = "ok" if r is not None and r.ping() else "error"
    except Exception:
        status["redis"] = "error"
    code = 200 if status["database"] == "ok" else 503
    return JSONResponse(status, status_code=code)
