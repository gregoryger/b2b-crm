"""Регрессии сценариев демонстрации: документы, деньги и периоды отчётов."""
from datetime import date, datetime, timedelta, timezone

import pytest


@pytest.mark.parametrize("currency", ["RUB", "USD", "EUR"])
@pytest.mark.parametrize("vat_rate", [0, 10, 20])
def test_invoice_inherits_proposal_terms(manager, currency, vat_rate):
    company = manager.post("/companies", json={"name": f"Документы {currency} {vat_rate}"}).json()
    proposal = manager.post("/proposals", json={
        "company_id": company["id"], "currency": currency, "vat_rate": vat_rate,
        "items": [{"name": "Сервер", "quantity": 2, "price": 125.5, "discount_percent": 10}],
    }).json()
    response = manager.post("/invoices", json={"proposal_id": proposal["id"]})
    assert response.status_code == 201, response.text
    invoice = response.json()
    assert (invoice["currency"], invoice["vat_rate"], invoice["amount"]) == (currency, vat_rate, 225.9)
    assert invoice["company"]["id"] == company["id"]
    assert invoice["items"][0]["quantity"] == 2
    assert manager.get(f"/invoices/{invoice['id']}/pdf").content.startswith(b"%PDF")
    if vat_rate == 0:
        act = manager.post("/acts", json={"invoice_id": invoice["id"]}).json()
        assert act["currency"] == currency
        assert manager.get(f"/acts/{act['id']}/pdf").content.startswith(b"%PDF")


def test_invoice_explicit_overrides_and_deal_currency(manager):
    company = manager.post("/companies", json={"name": "Источник счёта"}).json()
    deal = manager.post("/deals", json={"title": "Евро-поставка", "company_id": company["id"],
                                         "currency": "EUR", "amount": 100}).json()
    from_deal = manager.post("/invoices", json={"deal_id": deal["id"]}).json()
    assert from_deal["currency"] == "EUR"
    proposal = manager.post("/proposals", json={"deal_id": deal["id"], "currency": "USD", "vat_rate": 10}).json()
    inherited = manager.post("/invoices", json={"proposal_id": proposal["id"]}).json()
    assert inherited["deal_id"] == deal["id"]
    assert (inherited["currency"], inherited["vat_rate"]) == ("USD", 10)
    overridden = manager.post("/invoices", json={"proposal_id": proposal["id"], "currency": "RUB", "vat_rate": 0}).json()
    assert (overridden["currency"], overridden["vat_rate"]) == ("RUB", 0)


def test_finance_summary_currency_and_report_agree(manager):
    today = date.today()
    before = manager.get("/invoices/summary").json()
    company = manager.post("/companies", json={"name": "Мультивалютные расчёты"}).json()
    invoice = manager.post("/invoices", json={
        "company_id": company["id"], "currency": "USD", "vat_rate": 0,
        "due_date": (today - timedelta(days=1)).isoformat(),
        "items": [{"name": "Поставка", "quantity": 1, "price": 100}],
    }).json()
    manager.post(f"/invoices/{invoice['id']}/payments", json={"amount": 25, "paid_at": today.isoformat()})
    after = manager.get("/invoices/summary").json()
    rate = after["rates"]["USD"]
    assert after["receivable"] - before["receivable"] == pytest.approx(75 * rate)
    assert after["overdue"] - before["overdue"] == pytest.approx(75 * rate)
    assert after["paid_this_month"] - before["paid_this_month"] == pytest.approx(25 * rate)
    report = manager.get("/analytics/reports/receivables").json()
    assert report["totals"]["debt"] == pytest.approx(after["receivable"])
    # Будущая оплата не входит в фактические поступления на сегодня.
    manager.post(f"/invoices/{invoice['id']}/payments", json={"amount": 10, "paid_at": (today + timedelta(days=1)).isoformat()})
    assert manager.get("/invoices/summary").json()["paid_this_month"] == after["paid_this_month"]


def test_dashboard_chart_respects_dates_and_month_count(manager):
    from app.db.session import SessionLocal
    from app.models import Deal

    for day, amount in [(9, 10), (10, 20), (20, 30), (21, 40)]:
        deal = manager.post("/deals", json={"title": f"Граница периода {day}", "amount": amount}).json()
        with SessionLocal() as db:
            row = db.get(Deal, deal["id"])
            row.status = "won"
            row.closed_at = datetime(2024, 2, day, 12, tzinfo=timezone.utc)
            db.commit()
    dashboard = manager.get("/analytics/dashboard", params={"date_from": "2024-02-10", "date_to": "2024-02-20"}).json()
    assert dashboard["summary"]["revenue"] == 50
    # Короткий период: график — 12 календарных месяцев, заканчивая концом периода (сделка 21.02 не входит).
    chart = dashboard["revenue_by_month"]
    assert [chart[0]["month"], chart[-1]["month"], len(chart)] == ["мар 23", "фев 24", 12]
    assert chart[-1]["revenue"] == 60
    year = manager.get("/analytics/dashboard", params={"date_from": "2024-01-01", "date_to": "2024-12-31"}).json()
    assert len(year["revenue_by_month"]) == 12
    assert sum(m["revenue"] for m in year["revenue_by_month"]) == year["summary"]["revenue"] == 100
    # Период длиннее года показывается целиком.
    long = manager.get("/analytics/dashboard", params={"date_from": "2023-01-01", "date_to": "2024-12-31"}).json()
    assert len(long["revenue_by_month"]) == 24


def test_funnel_duration_respects_manager_scope(manager, manager2):
    from app.db.session import SessionLocal
    from app.models import DealStageHistory

    stage = next(s for s in manager.get("/stages").json() if s["kind"] == "open")
    for api, days in [(manager, 1), (manager2, 5)]:
        deal = api.post("/deals", json={"title": "Время прохождения этапа"}).json()
        with SessionLocal() as db:
            db.add(DealStageHistory(deal_id=deal["id"], from_stage_id=stage["id"], to_stage_id=stage["id"],
                                    changed_at=datetime(2024, 3, 15, tzinfo=timezone.utc), seconds_in_prev=days * 86400))
            db.commit()
    for api, days in [(manager, 1), (manager2, 5)]:
        report = api.get("/analytics/reports/funnel", params={"date_from": "2024-03-01", "date_to": "2024-03-31"}).json()
        assert next(r for r in report["rows"] if r["stage"] == stage["name"])["avg_days"] == days


def test_board_pagination_and_activity_indicator(manager):
    from app.db.session import SessionLocal
    from app.models import Activity, Deal

    me = manager.get("/auth/me").json()
    stage = next(s for s in manager.get("/stages").json() if s["kind"] == "open")
    old = datetime.now(timezone.utc) - timedelta(days=20)
    with SessionLocal() as db:
        rows = [Deal(title=f"Проверка страниц канбана {i}", owner_id=me["id"], stage_id=stage["id"],
                     amount=100, probability=10, created_at=old, updated_at=old, stage_changed_at=old)
                for i in range(105)]
        db.add_all(rows)
        db.flush()
        active_id = rows[0].id
        db.add(Activity(type="note", title="Недавний контакт", object_type="deal", object_id=active_id,
                        deal_id=active_id, user_id=me["id"]))
        db.commit()
    ids = []
    stale_ids = []
    for offset, length in [(0, 30), (30, 30), (60, 30), (90, 15)]:
        page = manager.get("/deals/board", params={"q": "Проверка страниц канбана", "stage_id": stage["id"], "offset": offset}).json()[0]
        assert page["count"] == 105
        assert page["amount"] == 10500
        assert len(page["deals"]) == length
        ids.extend(d["id"] for d in page["deals"])
        stale_ids.extend(d["id"] for d in page["deals"] if d["is_stale"])
    assert len(set(ids)) == 105
    assert len(stale_ids) == 104 and active_id not in stale_ids
    filtered = manager.get("/deals", params={"q": "Проверка страниц канбана", "stale": True, "page_size": 200}).json()
    assert filtered["total"] == 104
    assert manager.get("/deals/board", params={"limit_per_stage": 0}).status_code == 422


def test_integration_modes_are_not_claimed_as_connected(admin, manager):
    from app.core.config import settings
    result = admin.get("/integrations/status")
    assert result.status_code == 200
    data = result.json()
    if settings.TELEPHONY_PROVIDER == "mock":
        assert data["telephony"] == "demo"
    if not settings.IMAP_ENABLED:
        assert data["imap"] == "disabled"
    assert data["accounting"] == "export"
    assert "TOKEN" not in result.text and "PASSWORD" not in result.text
    assert manager.get("/integrations/status").status_code == 403
