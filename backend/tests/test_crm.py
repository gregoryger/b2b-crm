import io
import json
from datetime import datetime, timedelta, timezone

from app.services.money import amount_in_words


# ---------- Клиенты ----------

def test_company_inn_validation_and_duplicates(manager, manager2):
    assert manager.post("/companies", json={"name": "Плохой ИНН", "inn": "1234567890"}).status_code == 422
    r = manager.post("/companies", json={"name": "ООО «Сбер-тест»", "inn": "7707083893", "email": ""})
    assert r.status_code == 201, r.text
    dup = manager2.post("/companies", json={"name": "Дубль", "inn": "7707083893"})
    assert dup.status_code == 409
    assert "уже есть" in dup.json()["detail"]
    check = manager2.get("/companies/check-inn", params={"inn": "7707083893"}).json()
    assert check["exists"] and check["id"] is None  # чужая компания: название видно, карточка — нет


def test_manager_sees_only_own_companies(manager, head):
    me = manager.get("/auth/me").json()
    items = manager.get("/companies", params={"page_size": 200}).json()["items"]
    assert items and all(i["manager"]["id"] == me["id"] for i in items)
    assert head.get("/companies").json()["total"] > len(items)


def test_company_filters_and_sort(head):
    r = head.get("/companies", params={"status": ["active"], "sort": "-revenue", "page_size": 5}).json()
    revs = [i["total_revenue"] for i in r["items"]]
    assert revs == sorted(revs, reverse=True)
    assert all(i["status"] == "active" for i in r["items"])
    r = head.get("/companies", params={"no_contact_days": 30}).json()
    assert r["total"] >= 0


def test_custom_fields_validation(manager):
    bad = manager.post("/companies", json={"name": "ООО Поля", "custom_fields": {"it_budget": "миллиард"}})
    assert bad.status_code == 422
    ok = manager.post("/companies", json={"name": "ООО Поля", "custom_fields": {"employees": "150", "junk": 1}})
    assert ok.status_code == 201
    assert ok.json()["custom_fields"] == {"employees": 150.0}


def test_contact_and_timeline(manager):
    c = manager.post("/companies", json={"name": "ООО «Лента»"}).json()
    ct = manager.post("/contacts", json={"company_id": c["id"], "last_name": "Иванов", "first_name": "Иван",
                                         "phone_mobile": "+7 900 000 11 22", "role_in_deal": "decision_maker"}).json()
    assert ct["full_name"] == "Иванов Иван"
    manager.patch(f"/contacts/{ct['id']}", json={"position": "Директор"})
    manager.post("/activities", json={"type": "call", "body": "Обсудили поставку", "contact_id": ct["id"]})
    feed = manager.get("/activities", params={"company_id": c["id"]}).json()["items"]
    types = [a["type"] for a in feed]
    assert "call" in types and "field_change" in types
    assert manager.get(f"/companies/{c['id']}").json()["last_contact_at"] is not None


# ---------- Лиды ----------

def test_public_lead_round_robin_and_convert(client, head):
    bad = client.post("/api/v1/public/leads", json={"name": "X", "phone": "123"}, headers={"X-Api-Key": "nope"})
    assert bad.status_code == 401
    ids = []
    for i in range(2):
        r = client.post("/api/v1/public/leads", headers={"X-Api-Key": "crm_demo_website_key_2026"},
                        json={"name": f"Сидоров Пётр {i}", "company": f"ООО «Новый {i}»", "phone": f"+7900555443{i}",
                              "email": f"s{i}@new.example", "message": "Нужен сервер"})
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    leads = [head.get(f"/leads/{i}").json() for i in ids]
    assert all(lead["source"]["name"] == "Форма сайта" for lead in leads)
    assert leads[0]["assignee"]["id"] != leads[1]["assignee"]["id"]  # распределение по кругу

    res = head.post(f"/leads/{ids[0]}/convert", json={"amount": 500000})
    assert res.status_code == 200, res.text
    out = res.json()
    deal = head.get(f"/deals/{out['deal_id']}").json()
    assert deal["amount"] == 500000 and deal["company"]["name"] == "ООО «Новый 0»"
    assert deal["contact"]["full_name"].startswith("Сидоров")
    lead = head.get(f"/leads/{ids[0]}").json()
    assert lead["status"] == "qualified" and lead["deal_id"] == out["deal_id"]
    assert head.post(f"/leads/{ids[0]}/convert", json={}).status_code == 400


def test_lead_reject_requires_reason(head):
    lead = head.post("/leads", json={"title": "Нецелевой"}).json()
    assert head.post(f"/leads/{lead['id']}/reject", json={"reason_id": 999999}).status_code == 422
    reason = next(d for d in head.get("/dictionaries", params={"kind": "loss_reason"}).json())
    r = head.post(f"/leads/{lead['id']}/reject", json={"reason_id": reason["id"], "comment": "Спам"})
    assert r.json()["status"] == "rejected"


# ---------- Сделки ----------

def test_deal_rbac(manager, manager2, marketer, head):
    other = head.get("/deals", params={"owner_id": manager2.get("/auth/me").json()["id"], "page_size": 1}).json()
    deal_id = other["items"][0]["id"]
    assert manager.get(f"/deals/{deal_id}").status_code == 404
    assert manager2.get(f"/deals/{deal_id}").status_code == 200
    assert marketer.get("/deals").status_code == 403


def test_deal_lifecycle(manager):
    stages = manager.get("/stages").json()
    lost = next(s for s in stages if s["kind"] == "lost")
    won = next(s for s in stages if s["kind"] == "won")
    company = manager.post("/companies", json={"name": "ООО «Жизненный цикл»"}).json()
    products = manager.get("/products").json()
    deal = manager.post("/deals", json={
        "title": "Поставка", "company_id": company["id"],
        "products": [{"product_id": products[0]["id"], "name": products[0]["name"], "quantity": 2,
                      "price": 100000, "discount_percent": 10}]}).json()
    assert deal["amount"] == 180000 and deal["probability"] == 10
    assert manager.post(f"/deals/{deal['id']}/move", json={"stage_id": lost["id"]}).status_code == 422
    r = manager.post(f"/deals/{deal['id']}/move", json={"stage_id": won["id"]}).json()
    assert r["status"] == "won" and r["closed_at"]
    assert manager.get(f"/companies/{company['id']}").json()["status"] == "active"
    hist = manager.get(f"/deals/{deal['id']}/history").json()
    assert [h["to"] for h in hist][-1] == won["name"]
    # руководитель видит изменение суммы в аудите
    manager.patch(f"/deals/{deal['id']}", json={"amount": 1})
    assert manager.delete(f"/deals/{deal['id']}").status_code == 403  # удаление — только руководитель


def test_board(head):
    board = head.get("/deals/board").json()
    assert [c["stage"]["name"] for c in board][0] == "Первичный контакт"
    assert sum(c["count"] for c in board) > 0


# ---------- Задачи ----------

def test_task_reminder(manager):
    from app.worker.tasks import process_reminders

    due = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    t = manager.post("/tasks", json={"title": "Звонок клиенту", "type": "call", "due_at": due,
                                     "reminder_minutes": 15}).json()
    assert process_reminders() >= 1
    notes = manager.get("/notifications").json()
    assert any("Напоминание" in n["title"] for n in notes)
    done = manager.post(f"/tasks/{t['id']}/complete", json={"result": "Дозвонился"}).json()
    assert done["status"] == "done"


def test_ics_feed(client, manager):
    url = manager.get("/tasks/ics-url").json()["url"]
    path = url.split("localhost:8080")[1]
    r = client.get(path)
    assert r.status_code == 200 and "BEGIN:VCALENDAR" in r.text
    assert client.get(path.replace(".ics", "x.ics")).status_code == 404


# ---------- КП, счета, акты ----------

def test_proposal_flow(client, manager):
    deal = manager.get("/deals", params={"status": ["open"], "page_size": 1}).json()["items"][0]
    p = manager.post("/proposals", json={"deal_id": deal["id"], "template_id": 1}).json()
    assert p["number"].startswith("КП-") and p["items"]
    pdf = manager.get(f"/proposals/{p['id']}/pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    sent = manager.post(f"/proposals/{p['id']}/send", json={"to": "client@example.com"}).json()
    assert sent["status"] == "sent"
    token = sent["public_url"].rsplit("/", 1)[1]
    pub = client.get(f"/api/v1/public/proposals/{token}").json()
    assert pub["number"] == p["number"] and pub["total"] > 0
    assert "{{" not in pub["intro"]  # переменные подставлены
    assert manager.get(f"/proposals/{p['id']}").json()["status"] == "viewed"
    r = client.post(f"/api/v1/public/proposals/{token}/decision", json={"decision": "approved"})
    assert r.json()["status"] == "approved"
    assert client.post(f"/api/v1/public/proposals/{token}/decision", json={"decision": "rejected"}).status_code == 400


def test_invoice_payment_act_and_1c(head, manager):
    deal = manager.get("/deals", params={"page_size": 1}).json()["items"][0]
    inv = manager.post("/invoices", json={"deal_id": deal["id"]}).json()
    assert inv["status"] == "issued" and inv["amount"] > 0
    assert manager.post(f"/invoices/{inv['id']}/payments",
                        json={"amount": inv["amount"] * 2, "paid_at": "2026-01-10"}).status_code == 422
    part = manager.post(f"/invoices/{inv['id']}/payments", json={"amount": 100, "paid_at": "2026-01-10"}).json()
    assert part["status"] == "partially_paid" and part["debt"] == round(inv["amount"] - 100, 2)
    full = manager.post(f"/invoices/{inv['id']}/payments",
                        json={"amount": part["debt"], "paid_at": "2026-01-11"}).json()
    assert full["status"] == "paid"
    assert manager.get(f"/invoices/{inv['id']}/pdf").content[:4] == b"%PDF"
    act = manager.post("/acts", json={"invoice_id": inv["id"]}).json()
    assert manager.get(f"/acts/{act['id']}/pdf").content[:4] == b"%PDF"
    xml = head.get("/integrations/1c/export", params={"date_from": "2020-01-01", "date_to": "2030-01-01"})
    assert xml.status_code == 200 and "СчетНаОплату" in xml.text


def test_amount_in_words():
    assert amount_in_words(1234567.89) == "Один миллион двести тридцать четыре тысячи пятьсот шестьдесят семь рублей 89 копеек"
    assert amount_in_words(21) == "Двадцать один рубль 00 копеек"
    assert amount_in_words(2002) == "Две тысячи два рубля 00 копеек"


# ---------- Аналитика ----------

def test_reports(head, manager, marketer):
    for name in ("summary", "funnel", "managers", "sources", "products", "receivables"):
        r = head.get(f"/analytics/reports/{name}", params={"date_from": "2025-09-01", "date_to": "2026-12-31"})
        assert r.status_code == 200, name
        assert r.json()["columns"]
    funnel = head.get("/analytics/reports/funnel", params={"date_from": "2025-01-01", "date_to": "2026-12-31"}).json()
    reached = [row["reached"] for row in funnel["rows"][:-1]]
    assert reached == sorted(reached, reverse=True)  # воронка монотонна
    # менеджер видит только себя
    rows = manager.get("/analytics/reports/managers").json()["rows"]
    assert len(rows) == 1
    assert marketer.get("/analytics/reports/receivables").status_code == 403
    custom = head.get("/analytics/reports/custom", params={"metric": "revenue", "group_by": "manager",
                                                           "date_from": "2025-01-01", "date_to": "2026-12-31"}).json()
    assert custom["rows"]
    dash = head.get("/analytics/dashboard").json()
    assert {"summary", "revenue_by_month", "forecast", "funnel", "top_managers", "tasks"} <= dash.keys()


def test_report_exports(head):
    for fmt, magic in (("pdf", b"%PDF"), ("xlsx", b"PK"), ("csv", "Менеджер".encode("utf-8-sig")[:3])):
        r = head.get("/analytics/reports/managers/export", params={"format": fmt})
        assert r.status_code == 200 and r.content[:len(magic)] == magic, fmt


# ---------- Импорт / экспорт / поиск / аудит ----------

def test_import_companies(head):
    csv_data = ("Наименование;ИНН;Отрасль;Регион;Контакт;Телефон контакта\n"
                "ООО «Импорт-1»;;Новая отрасль;Москва;Петров Пётр Петрович;+79001112233\n"
                "ООО «Импорт-2»;1111111111;Производство;;;\n").encode("utf-8")
    files = {"file": ("clients.csv", io.BytesIO(csv_data), "text/csv")}
    prev = head.post("/import/companies/preview", files=files).json()
    assert prev["total"] == 2 and prev["mapping"]["наименование"] == "name"
    files = {"file": ("clients.csv", io.BytesIO(csv_data), "text/csv")}
    res = head.post("/import/companies", files=files, data={"mapping": json.dumps(prev["mapping"])}).json()
    assert res["created"] == 2 and res["contacts"] == 1
    assert res["errors"] and "ИНН" in res["errors"][0]["error"]


def test_export_and_search(head):
    r = head.get("/export/companies", params={"format": "xlsx"})
    assert r.status_code == 200 and r.content[:2] == b"PK"
    s = head.get("/search", params={"q": "Сиб"}).json()
    assert s["companies"]
    inn = s["companies"][0]["subtitle"].replace("ИНН ", "")
    assert head.get("/search", params={"q": inn}).json()["companies"]


def test_audit_log(head, admin):
    c = head.post("/companies", json={"name": "ООО «На удаление»"}).json()
    assert head.delete(f"/companies/{c['id']}").status_code == 200
    log = admin.get("/audit", params={"action": ["delete"], "entity": "company"}).json()["items"]
    assert any("На удаление" in row["summary"] for row in log)


def test_telephony_webhook(client, head):
    bad = client.post("/api/v1/integrations/telephony/events", json={"event": "completed", "call_id": "1",
                                                                     "phone": "+79000000000"})
    assert bad.status_code == 403
    r = client.post("/api/v1/integrations/telephony/events", headers={"X-Webhook-Secret": "test-secret"},
                    json={"event": "completed", "call_id": "2", "phone": "+7 (901) 222-33-44", "direction": "in",
                          "duration": 40})
    assert r.status_code == 200
    leads = head.get("/leads", params={"q": "89012223344"}).json()["items"]
    assert leads and leads[0]["source"]["name"] == "Телефон"


def test_email_with_tracking(client, manager):
    c = manager.post("/companies", json={"name": "ООО «Почта»"}).json()
    em = manager.post("/emails", json={"to": "x@example.com", "subject": "Тест", "body": "Привет",
                                       "company_id": c["id"]}).json()
    assert em["status"] in ("queued", "sent", "failed")
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import EmailMessage

    with SessionLocal() as db:
        token = db.scalar(select(EmailMessage.tracking_token).where(EmailMessage.id == em["id"]))
    r = client.get(f"/api/v1/t/{token}.gif")
    assert r.status_code == 200 and r.headers["content-type"] == "image/gif"
    assert manager.get("/emails", params={"company_id": c["id"]}).json()[0]["opened_at"]
