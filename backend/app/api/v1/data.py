"""Импорт из CSV/Excel, выгрузка сегментов и глобальный поиск."""
import csv
import io
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require
from app.api.v1.companies import list_companies, search_clause
from app.core.permissions import has_perm
from app.core.security import normalize_phone, phone_hash
from app.db.session import get_db
from app.models import Company, Contact, Deal, DictionaryItem, Lead, User
from app.services import access
from app.services.common import validate_inn
from app.services.documents import rows_csv, rows_xlsx
from app.services.journal import audit, log_activity
from app.services.money import fmt_money

router = APIRouter(tags=["Импорт, экспорт, поиск"])

MAX_ROWS = 20000

COMPANY_FIELDS = {
    "name": "Наименование", "full_name": "Полное наименование", "inn": "ИНН", "kpp": "КПП", "ogrn": "ОГРН",
    "legal_address": "Юр. адрес", "actual_address": "Факт. адрес", "industry": "Отрасль", "region": "Регион",
    "client_type": "Тип клиента", "status": "Статус", "phone": "Телефон", "email": "Email", "website": "Сайт",
    "description": "Описание", "manager_email": "Email ответственного",
    "contact_name": "Контакт: ФИО", "contact_position": "Контакт: должность", "contact_phone": "Контакт: телефон",
    "contact_email": "Контакт: email",
}
HEADER_ALIASES = {
    "наименование": "name", "название": "name", "компания": "name", "организация": "name", "name": "name",
    "полное наименование": "full_name", "инн": "inn", "inn": "inn", "кпп": "kpp", "огрн": "ogrn",
    "юр. адрес": "legal_address", "юридический адрес": "legal_address", "адрес": "legal_address",
    "факт. адрес": "actual_address", "фактический адрес": "actual_address", "отрасль": "industry",
    "регион": "region", "город": "region", "тип клиента": "client_type", "тип": "client_type", "статус": "status",
    "телефон": "phone", "phone": "phone", "email": "email", "e-mail": "email", "почта": "email", "сайт": "website",
    "описание": "description", "комментарий": "description", "ответственный": "manager_email",
    "email ответственного": "manager_email", "контакт": "contact_name", "фио": "contact_name",
    "контактное лицо": "contact_name", "контакт: фио": "contact_name", "должность": "contact_position",
    "контакт: должность": "contact_position", "телефон контакта": "contact_phone", "контакт: телефон": "contact_phone",
    "email контакта": "contact_email", "контакт: email": "contact_email",
}
STATUS_ALIASES = {"потенциальный": "prospect", "активный": "active", "клиент": "active", "неактивный": "inactive",
                  "партнёр": "partner", "партнер": "partner"}


def _read_table(file: UploadFile) -> list[dict]:
    data = file.file.read(20 * 1024 * 1024)
    name = (file.filename or "").lower()
    rows: list[list] = []
    if name.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb.active
        for r in ws.iter_rows(values_only=True):
            rows.append(["" if v is None else str(v).strip() for v in r])
    elif name.endswith((".csv", ".txt")):
        text = None
        for enc in ("utf-8-sig", "cp1251"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise HTTPException(422, "Не удалось определить кодировку файла")
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=";,\t") if text.strip() else csv.excel
        rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO(text), dialect)]
    else:
        raise HTTPException(422, "Поддерживаются файлы CSV и Excel (.xlsx)")
    rows = [r for r in rows if any(r)]
    if len(rows) < 2:
        raise HTTPException(422, "Файл пуст или содержит только заголовок")
    if len(rows) > MAX_ROWS + 1:
        raise HTTPException(422, f"Не более {MAX_ROWS} строк за один импорт")
    headers = [h.lower().strip() for h in rows[0]]
    return [{h: (r[i] if i < len(r) else "") for i, h in enumerate(headers)} for r in rows[1:]]


def _auto_mapping(headers: list[str]) -> dict[str, str]:
    mapping = {}
    for h in headers:
        key = HEADER_ALIASES.get(h.lower().strip())
        if key and key not in mapping.values():
            mapping[h] = key
    return mapping


@router.post("/import/companies/preview", summary="Импорт: предпросмотр и сопоставление колонок")
def import_preview(file: UploadFile = File(...), user: User = Depends(require("import")),
                   db: Session = Depends(get_db)):
    rows = _read_table(file)
    headers = list(rows[0].keys())
    return {"headers": headers, "mapping": _auto_mapping(headers), "fields": COMPANY_FIELDS, "total": len(rows),
            "sample": rows[:10]}


@router.post("/import/companies", summary="Импорт компаний и контактов из CSV/Excel")
def import_companies(
    request: Request,
    file: UploadFile = File(...),
    mapping: str = Form(..., description='JSON: {"Колонка файла": "поле CRM"}'),
    on_duplicate: str = Form(default="skip", description="skip | update"),
    default_manager_id: int | None = Form(default=None),
    user: User = Depends(require("import")),
    db: Session = Depends(get_db),
):
    import json

    try:
        colmap: dict[str, str] = {k.lower().strip(): v for k, v in json.loads(mapping).items() if v}
    except (ValueError, AttributeError):
        raise HTTPException(422, "Некорректное сопоставление колонок")
    if "name" not in colmap.values():
        raise HTTPException(422, "Сопоставьте колонку с наименованием компании")
    rows = _read_table(file)

    dicts: dict[str, dict[str, int]] = {}
    for kind in ("industry", "region", "client_type"):
        dicts[kind] = {i.name.lower(): i.id for i in db.scalars(select(DictionaryItem).where(DictionaryItem.kind == kind))}
    managers = {u.email.lower(): u.id for u in db.scalars(select(User).where(User.is_active.is_(True)))}
    manager_default = default_manager_id or user.id
    stats = {"created": 0, "updated": 0, "skipped": 0, "contacts": 0, "errors": []}

    def dict_id(kind: str, value: str) -> int | None:
        if not value:
            return None
        key = value.lower().strip()
        if key not in dicts[kind]:
            item = DictionaryItem(kind=kind, name=value.strip()[:255], sort=500)
            db.add(item)
            db.flush()
            dicts[kind][key] = item.id
        return dicts[kind][key]

    for idx, raw in enumerate(rows, start=2):
        rec = {field: raw.get(col, "").strip() for col, field in colmap.items()}
        name = rec.get("name")
        if not name:
            stats["skipped"] += 1
            continue
        inn = "".join(ch for ch in rec.get("inn", "") if ch.isdigit()) or None
        if inn and (err := validate_inn(inn)):
            stats["errors"].append({"row": idx, "error": f"{name}: {err}"})
            inn = None
        values = {
            "name": name[:255], "full_name": rec.get("full_name") or None, "inn": inn,
            "kpp": rec.get("kpp") or None, "ogrn": rec.get("ogrn") or None,
            "legal_address": rec.get("legal_address") or None, "actual_address": rec.get("actual_address") or None,
            "industry_id": dict_id("industry", rec.get("industry", "")),
            "region_id": dict_id("region", rec.get("region", "")),
            "client_type_id": dict_id("client_type", rec.get("client_type", "")),
            "status": STATUS_ALIASES.get(rec.get("status", "").lower(), "prospect"),
            "phone": rec.get("phone") or None, "email": rec.get("email") or None, "website": rec.get("website") or None,
            "description": rec.get("description") or None,
        }
        manager_id = managers.get(rec.get("manager_email", "").lower()) or manager_default
        if not has_perm(user.role, "companies.reassign"):
            manager_id = user.id
        existing = db.scalars(select(Company).where(Company.inn == inn, Company.deleted_at.is_(None))).first() \
            if inn else None
        if existing:
            if on_duplicate != "update":
                stats["skipped"] += 1
                continue
            for k, v in values.items():
                if v not in (None, "") and k != "status":
                    setattr(existing, k, v)
            existing.phone_hash = phone_hash(existing.phone)
            company = existing
            stats["updated"] += 1
        else:
            company = Company(**values, manager_id=manager_id, custom_fields={})
            company.phone_hash = phone_hash(company.phone)
            db.add(company)
            db.flush()
            log_activity(db, type="created", title="Компания импортирована", object_type="company",
                         object_id=company.id, user=user, company_id=company.id)
            stats["created"] += 1
        if rec.get("contact_name"):
            parts = rec["contact_name"].split()
            last, first = (parts + ["—", "—"])[:2]
            middle = " ".join(parts[2:]) or None
            contact = Contact(company_id=company.id, owner_id=company.manager_id, last_name=last, first_name=first,
                              middle_name=middle, full_name=" ".join(parts), position=rec.get("contact_position") or None,
                              phone_mobile=rec.get("contact_phone") or None, email=rec.get("contact_email") or None,
                              custom_fields={})
            contact.phone_mobile_hash = phone_hash(contact.phone_mobile)
            db.add(contact)
            stats["contacts"] += 1
        if idx % 500 == 0:
            db.flush()
    audit(db, user, "import", f"Импорт компаний: создано {stats['created']}, обновлено {stats['updated']}, "
                              f"пропущено {stats['skipped']}", entity="company", request=request)
    db.commit()
    stats["errors"] = stats["errors"][:100]
    return stats


@router.get("/import/template", summary="Шаблон файла для импорта")
def import_template(user: User = Depends(require("import"))):
    cols = [(k, v) for k, v in COMPANY_FIELDS.items()]
    sample = [{"name": "ООО «Пример»", "inn": "7707083893", "industry": "Производство", "region": "Москва",
               "status": "Потенциальный", "phone": "+7 495 000-00-00", "email": "info@example.ru",
               "contact_name": "Иванов Иван Иванович", "contact_position": "Директор",
               "contact_email": "ivanov@example.ru"}]
    return Response(rows_xlsx("Шаблон импорта компаний", cols, sample),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=import_template.xlsx"})


# ---------- Экспорт сегментов ----------

STATUS_RU = {"prospect": "Потенциальный", "active": "Активный", "inactive": "Неактивный", "partner": "Партнёр"}


@router.get("/export/companies", summary="Выгрузка сегмента компаний (с теми же фильтрами, что и список)")
def export_companies(
    request: Request,
    format: str = "xlsx",
    with_contacts: bool = True,
    q: str | None = None,
    industry_id: list[int] = Query(default=[]),
    region_id: list[int] = Query(default=[]),
    client_type_id: list[int] = Query(default=[]),
    status: list[str] = Query(default=[]),
    manager_id: int | None = None,
    revenue_min: float | None = None,
    revenue_max: float | None = None,
    no_contact_days: int | None = None,
    user: User = Depends(require("export")),
    db: Session = Depends(get_db),
):
    page = list_companies(q=q, industry_id=industry_id, region_id=region_id, client_type_id=client_type_id,
                          status=status, manager_id=manager_id, source_id=None, revenue_min=revenue_min,
                          revenue_max=revenue_max, last_contact_from=None, last_contact_to=None,
                          no_contact_days=no_contact_days, sort="name", page=1, page_size=200, user=user, db=db)
    total = page["total"]
    items = page["items"]
    p = 2
    while len(items) < total and p <= 100:
        items += list_companies(q=q, industry_id=industry_id, region_id=region_id, client_type_id=client_type_id,
                                status=status, manager_id=manager_id, source_id=None, revenue_min=revenue_min,
                                revenue_max=revenue_max, last_contact_from=None, last_contact_to=None,
                                no_contact_days=no_contact_days, sort="name", page=p, page_size=200, user=user,
                                db=db)["items"]
        p += 1
    rows = []
    contacts_by_company: dict[int, list[Contact]] = {}
    if with_contacts and items:
        for c in db.scalars(select(Contact).where(Contact.company_id.in_([i.id for i in items]),
                                                  Contact.deleted_at.is_(None))).unique():
            contacts_by_company.setdefault(c.company_id, []).append(c)
    for c in items:
        base = {"name": c.name, "inn": c.inn, "kpp": c.kpp, "industry": c.industry.name if c.industry else "",
                "region": c.region.name if c.region else "", "status": STATUS_RU.get(c.status, c.status),
                "phone": c.phone, "email": c.email, "website": c.website,
                "manager": c.manager.full_name if c.manager else "", "revenue": c.total_revenue,
                "last_contact": c.last_contact_at.strftime("%d.%m.%Y") if c.last_contact_at else ""}
        contacts = contacts_by_company.get(c.id) or [None]
        for ct in contacts:
            rows.append({**base, "contact": ct.full_name if ct else "", "position": ct.position if ct else "",
                         "contact_email": ct.email if ct else "", "contact_phone": ct.phone_mobile if ct else ""})
    cols = [("name", "Компания"), ("inn", "ИНН"), ("kpp", "КПП"), ("industry", "Отрасль"), ("region", "Регион"),
            ("status", "Статус"), ("phone", "Телефон"), ("email", "Email"), ("website", "Сайт"),
            ("manager", "Ответственный"), ("revenue", "Сумма покупок, ₽"), ("last_contact", "Последний контакт")]
    if with_contacts:
        cols += [("contact", "Контакт"), ("position", "Должность"), ("contact_email", "Email контакта"),
                 ("contact_phone", "Телефон контакта")]
    audit(db, user, "export", f"Выгрузка базы клиентов: {len(items)} компаний ({format})", entity="company",
          request=request)
    db.commit()
    if format == "csv":
        return Response(rows_csv(cols, rows), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": "attachment; filename=companies.csv"})
    return Response(rows_xlsx("Клиенты", cols, rows),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote('Клиенты.xlsx')}"})


# ---------- Глобальный поиск ----------

@router.get("/search", summary="Глобальный поиск: компании, контакты, сделки, лиды (название, ИНН, телефон, ФИО)")
def global_search(q: str = Query(min_length=2), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = q.strip()
    like = f"%{q.lower()}%"
    res: dict[str, list] = {"companies": [], "contacts": [], "deals": [], "leads": []}
    comp = access.scope_companies(select(Company).where(Company.deleted_at.is_(None), search_clause(q)), user)
    res["companies"] = [{"id": c.id, "title": c.name, "subtitle": f"ИНН {c.inn}" if c.inn else (c.region.name if c.region else "")}
                        for c in db.scalars(comp.limit(7)).unique()]
    cconds = [func.lower(Contact.full_name).like(like), func.lower(func.coalesce(Contact.email, "")).like(like)]
    if (n := normalize_phone(q)) and len(n) >= 6:
        cconds += [Contact.phone_mobile_hash == phone_hash(q), Contact.phone_work_hash == phone_hash(q)]
    cont = access.scope_contacts(select(Contact).where(Contact.deleted_at.is_(None), or_(*cconds)), user)
    res["contacts"] = [{"id": c.id, "title": c.full_name,
                        "subtitle": " · ".join(x for x in (c.position, c.company.name if c.company else None) if x)}
                       for c in db.scalars(cont.limit(7)).unique()]
    if has_perm(user.role, "deals.view"):
        deals = access.scope_deals(select(Deal).where(Deal.deleted_at.is_(None), or_(
            func.lower(Deal.title).like(like), Deal.company_id.in_(select(Company.id).where(search_clause(q))))), user)
        res["deals"] = [{"id": d.id, "title": d.title,
                         "subtitle": f"{d.stage.name} · {fmt_money(d.amount, d.currency).replace(',00', '')}"}
                        for d in db.scalars(deals.limit(7)).unique()]
    lconds = [func.lower(Lead.title).like(like), func.lower(func.coalesce(Lead.company_name, "")).like(like),
              func.lower(func.coalesce(Lead.contact_name, "")).like(like), Lead.inn.like(f"{q}%")]
    if (n := normalize_phone(q)) and len(n) >= 6:
        lconds.append(Lead.phone_hash == phone_hash(q))
    leads = access.scope_leads(select(Lead).where(Lead.deleted_at.is_(None), or_(*lconds)), user)
    res["leads"] = [{"id": lead.id, "title": lead.title, "subtitle": lead.company_name or ""}
                    for lead in db.scalars(leads.order_by(Lead.created_at.desc()).limit(5)).unique()]
    return res
