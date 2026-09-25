"""Генерация PDF (КП, счёт, акт, отчёт) и выгрузок Excel / CSV."""
import base64
import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from app.models import Act, Invoice, Proposal, User
from app.services.common import get_setting
from app.services.money import amount_in_words, calc_lines, fmt_money

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября",
              "ноября", "декабря"]


def _date_ru(d: date | datetime | None) -> str:
    if not d:
        return ""
    return f"«{d.day:02d}» {MONTHS_GEN[d.month - 1]} {d.year} г."


def _num(v) -> str:
    """Количество: без лишних нулей, с пробелом-разделителем тысяч."""
    if v is None or v == "":
        return "—"
    f = float(v)
    if f.is_integer():
        return f"{int(f):,}".replace(",", " ")
    return f"{f:,.3f}".rstrip("0").rstrip(".").replace(",", " ").replace(".", ",")


env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))
env.filters["money"] = fmt_money
env.filters["num"] = _num
env.filters["date_ru"] = _date_ru
env.filters["dmy"] = lambda d: d.strftime("%d.%m.%Y") if d else ""


def html_to_pdf(html: str) -> bytes:
    from weasyprint import HTML  # тяжёлый импорт — только при генерации

    return HTML(string=html, base_url=str(TEMPLATES)).write_pdf()


def _profile(db: Session) -> dict:
    profile = dict(get_setting(db, "company_profile"))
    logo = None
    if profile.get("logo_key"):
        try:
            from app.services.storage import get_storage

            data = get_storage().get(profile["logo_key"])
            mime = "image/svg+xml" if profile["logo_key"].endswith(".svg") else "image/png"
            logo = f"data:{mime};base64,{base64.b64encode(data).decode()}"
        except Exception:
            logo = None
    profile["logo"] = logo
    return profile


# ---------- Подстановка переменных в шаблоны КП ----------

VARIABLES = {
    "{{клиент.название}}": "Наименование клиента",
    "{{клиент.инн}}": "ИНН клиента",
    "{{клиент.адрес}}": "Юридический адрес клиента",
    "{{контакт.имя}}": "Имя и отчество контактного лица",
    "{{контакт.фио}}": "ФИО контактного лица",
    "{{менеджер.фио}}": "ФИО менеджера",
    "{{менеджер.телефон}}": "Телефон менеджера",
    "{{менеджер.email}}": "Email менеджера",
    "{{компания.название}}": "Наименование вашей компании",
    "{{дата}}": "Текущая дата",
    "{{срок_действия}}": "Срок действия КП",
    "{{сумма}}": "Итоговая сумма КП",
}


def fill_variables(text: str, *, proposal: Proposal | None = None, company=None, contact=None,
                   manager: User | None = None, profile: dict | None = None, total=None, currency="RUB",
                   valid_until: date | None = None) -> str:
    if not text:
        return ""
    company = company or (proposal.company if proposal else None)
    contact = contact or (proposal.contact if proposal else None)
    manager = manager or (proposal.owner if proposal else None)
    values = {
        "{{клиент.название}}": company.name if company else "",
        "{{клиент.инн}}": company.inn or "" if company else "",
        "{{клиент.адрес}}": company.legal_address or "" if company else "",
        "{{контакт.имя}}": f"{contact.first_name} {contact.middle_name or ''}".strip() if contact else "",
        "{{контакт.фио}}": contact.full_name if contact else "",
        "{{менеджер.фио}}": manager.full_name if manager else "",
        "{{менеджер.телефон}}": manager.phone or "" if manager else "",
        "{{менеджер.email}}": manager.email if manager else "",
        "{{компания.название}}": (profile or {}).get("name", ""),
        "{{дата}}": date.today().strftime("%d.%m.%Y"),
        "{{срок_действия}}": (valid_until or (proposal.valid_until if proposal else None) or date.today()).strftime("%d.%m.%Y"),
        "{{сумма}}": fmt_money(total if total is not None else (proposal.total if proposal else 0), currency),
    }
    for k, v in values.items():
        text = text.replace(k, v)
    return re.sub(r"\{\{[^}]+\}\}", "", text)


# ---------- PDF документов ----------

def proposal_pdf(db: Session, p: Proposal) -> bytes:
    profile = _profile(db)
    items = [{"name": i.name, "description": i.description, "quantity": float(i.quantity), "unit": i.unit,
              "price": float(i.price), "discount_percent": float(i.discount_percent)} for i in p.items]
    calc = calc_lines(items, p.vat_rate)
    accent = (p.template.accent_color if p.template else None) or profile.get("accent_color") or "#1c7ed6"
    html = env.get_template("proposal.html").render(
        p=p, profile=profile, lines=calc["lines"], total=calc["total"], vat=calc["vat"], accent=accent,
        intro=fill_variables(p.intro_text, proposal=p, profile=profile),
        terms=fill_variables(p.terms_text, proposal=p, profile=profile),
        footer=fill_variables(p.template.footer_text if p.template else "", proposal=p, profile=profile),
        has_discount=any(i["discount_percent"] for i in items),
    )
    return html_to_pdf(html)


def invoice_pdf(db: Session, inv: Invoice) -> bytes:
    profile = _profile(db)
    calc = calc_lines(inv.items or [], inv.vat_rate)
    html = env.get_template("invoice.html").render(
        inv=inv, profile=profile, lines=calc["lines"], total=calc["total"], vat=calc["vat"],
        words=amount_in_words(calc["total"], inv.currency),
    )
    return html_to_pdf(html)


def act_pdf(db: Session, act: Act) -> bytes:
    profile = _profile(db)
    calc = calc_lines(act.items or [], act.vat_rate)
    html = env.get_template("act.html").render(
        act=act, profile=profile, lines=calc["lines"], total=calc["total"], vat=calc["vat"],
        words=amount_in_words(calc["total"], act.currency),
    )
    return html_to_pdf(html)


# ---------- Выгрузки отчётов ----------

def _cell(value, col_type: str):
    if value is None:
        return ""
    if col_type in ("money", "float", "pct") and isinstance(value, (int, float, Decimal)):
        return float(value)
    return value


def report_csv(report: dict) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow([c["label"] for c in report["columns"]])
    for row in report["rows"]:
        w.writerow([str(_cell(row.get(c["key"]), c["type"])).replace(".", ",")
                    if c["type"] in ("money", "float", "pct") and row.get(c["key"]) is not None
                    else _cell(row.get(c["key"]), c["type"]) for c in report["columns"]])
    if report.get("totals"):
        w.writerow([report["totals"].get(c["key"], "") for c in report["columns"]])
    return buf.getvalue().encode("utf-8-sig")  # BOM — чтобы Excel корректно открыл кириллицу


def report_xlsx(report: dict) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = re.sub(r"[\\/*?:\[\]]", " ", report["title"])[:31]
    ws.append([report["title"]])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([report.get("subtitle") or ""])
    ws.append([])
    header_row = 4
    ws.append([c["label"] for c in report["columns"]])
    thin = Side(style="thin", color="BBBBBB")
    for i, _ in enumerate(report["columns"], 1):
        cell = ws.cell(row=header_row, column=i)
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="E9ECEF")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        cell.border = Border(bottom=thin, top=thin, left=thin, right=thin)
    formats = {"money": "#,##0.00", "float": "#,##0.##", "pct": "0.0", "int": "0"}
    for row in report["rows"]:
        ws.append([_cell(row.get(c["key"]), c["type"]) for c in report["columns"]])
        r = ws.max_row
        for i, c in enumerate(report["columns"], 1):
            if c["type"] in formats:
                ws.cell(row=r, column=i).number_format = formats[c["type"]]
    if report.get("totals"):
        ws.append([_cell(report["totals"].get(c["key"]), c["type"]) for c in report["columns"]])
        for i in range(1, len(report["columns"]) + 1):
            ws.cell(row=ws.max_row, column=i).font = Font(bold=True)
    for i, c in enumerate(report["columns"], 1):
        width = max([len(str(c["label"]))] + [len(str(r.get(c["key"], ""))) for r in report["rows"][:500]])
        ws.column_dimensions[get_column_letter(i)].width = min(max(width + 2, 10), 50)
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def report_pdf(db: Session, report: dict) -> bytes:
    profile = _profile(db)
    html = env.get_template("report.html").render(r=report, profile=profile, now=datetime.now())
    return html_to_pdf(html)


def rows_xlsx(title: str, columns: list[tuple[str, str]], rows: list[dict]) -> bytes:
    report = {"title": title, "subtitle": f"Выгрузка от {date.today():%d.%m.%Y}",
              "columns": [{"key": k, "label": label, "type": "text"} for k, label in columns], "rows": rows}
    return report_xlsx(report)


def rows_csv(columns: list[tuple[str, str]], rows: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow([label for _, label in columns])
    for r in rows:
        w.writerow([r.get(k, "") if r.get(k) is not None else "" for k, _ in columns])
    return buf.getvalue().encode("utf-8-sig")


def export_report(db: Session, report: dict, fmt: str) -> tuple[bytes, str, str]:
    """Возвращает (данные, mime, расширение)."""
    if fmt == "xlsx":
        return report_xlsx(report), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    if fmt == "csv":
        return report_csv(report), "text/csv; charset=utf-8", "csv"
    return report_pdf(db, report), "application/pdf", "pdf"
