import pyotp
from sqlalchemy import text

from app.db.session import engine
from tests.conftest import Api


def test_login_wrong_password(client):
    r = client.post("/api/v1/auth/login", json={"email": "orlova@demo.ru", "password": "wrong"},
                    headers={"X-Real-IP": "10.1.0.1"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Неверный email или пароль"


def test_me_and_permissions(manager, head):
    me = manager.get("/auth/me").json()
    assert me["role"] == "manager"
    assert "deals.view_all" not in me["permissions"]
    assert "deals.view_all" in head.get("/auth/me").json()["permissions"]


def test_unauthorized(client):
    assert client.get("/api/v1/companies").status_code == 401
    assert client.get("/api/v1/companies", headers={"Authorization": "Bearer bad"}).status_code == 401


def test_account_lock_after_failed_attempts(client, admin):
    r = admin.post("/users", json={"email": "lock@demo.ru", "full_name": "Блокировка Тест", "role": "manager",
                                   "password": "secret123"})
    assert r.status_code == 201, r.text
    for i in range(5):
        client.post("/api/v1/auth/login", json={"email": "lock@demo.ru", "password": "bad"},
                    headers={"X-Real-IP": f"10.2.0.{i}"})
    r = client.post("/api/v1/auth/login", json={"email": "lock@demo.ru", "password": "secret123"},
                    headers={"X-Real-IP": "10.2.1.1"})
    assert r.status_code == 423


def test_refresh_rotation_and_reuse_detection(client):
    r = client.post("/api/v1/auth/login", json={"email": "nikitin@demo.ru", "password": "demo12345"},
                    headers={"X-Real-IP": "10.3.0.1"})
    rt = r.json()["refresh_token"]
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": rt})
    assert r2.status_code == 200
    new_rt = r2.json()["refresh_token"]
    # повторное использование старого токена — отказ и отзыв всех сессий
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": rt}).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": new_rt}).status_code == 401


def test_two_factor_flow(client, admin):
    admin.post("/users", json={"email": "twofa@demo.ru", "full_name": "Двухфакторный Тест", "role": "manager",
                               "password": "secret123"})
    tok = client.post("/api/v1/auth/login", json={"email": "twofa@demo.ru", "password": "secret123"},
                      headers={"X-Real-IP": "10.4.0.1"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    secret = client.post("/api/v1/auth/me/2fa/setup", headers=h).json()["secret"]
    assert client.post("/api/v1/auth/me/2fa/enable", headers=h, json={"code": "000000"}).status_code == 400
    assert client.post("/api/v1/auth/me/2fa/enable", headers=h,
                       json={"code": pyotp.TOTP(secret).now()}).status_code == 200
    r = client.post("/api/v1/auth/login", json={"email": "twofa@demo.ru", "password": "secret123"},
                    headers={"X-Real-IP": "10.4.0.2"}).json()
    assert r["two_factor_required"] and r["access_token"] is None
    r2 = client.post("/api/v1/auth/2fa", json={"token": r["two_factor_token"], "code": pyotp.TOTP(secret).now()},
                     headers={"X-Real-IP": "10.4.0.3"})
    assert r2.status_code == 200 and r2.json()["access_token"]


def test_login_rate_limit(client):
    codes = [client.post("/api/v1/auth/login", json={"email": "x@demo.ru", "password": "x"},
                         headers={"X-Real-IP": "10.9.9.9"}).status_code for _ in range(12)]
    assert 429 in codes


def test_sensitive_fields_encrypted_in_db(manager):
    c = manager.post("/companies", json={"name": "ООО «Шифр»", "phone": "+7 (913) 555-66-77"}).json()
    with engine.connect() as conn:
        raw = conn.scalar(text("SELECT phone FROM companies WHERE id = :id"), {"id": c["id"]})
        pwd = conn.scalar(text("SELECT password_hash FROM users WHERE email = 'head@demo.ru'"))
    assert raw and "555" not in raw  # в БД — шифротекст
    assert pwd.startswith("$2b$")  # bcrypt
    assert manager.get(f"/companies/{c['id']}").json()["phone"] == "+7 (913) 555-66-77"
    # поиск по телефону в любом формате — через слепой индекс
    found = manager.get("/companies", params={"q": "89135556677"}).json()["items"]
    assert any(i["id"] == c["id"] for i in found)


def test_xss_and_sql_injection_are_harmless(manager):
    payload = "<script>alert(1)</script>'; DROP TABLE companies; --"
    r = manager.post("/companies", json={"name": payload})
    assert r.status_code == 201
    assert manager.get("/companies", params={"q": "'; DROP TABLE"}).status_code == 200
    assert manager.get(f"/companies/{r.json()['id']}").json()["name"] == payload  # хранится как текст


def test_security_headers(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    r = client.get("/api/v1/stages", headers={"Authorization": f"Bearer {Api(client, 'head@demo.ru').h['Authorization'][7:]}"})
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "X-RateLimit-Limit" in r.headers


def test_admin_only_endpoints(manager, admin):
    assert manager.get("/users").status_code == 403
    assert admin.get("/users").status_code == 200
    assert manager.get("/audit").status_code == 403
