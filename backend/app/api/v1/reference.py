import hashlib
import re

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require
from app.core.config import settings
from app.core.security import random_token
from app.db.session import get_db
from app.models import (
    ApiKey,
    Company,
    CustomField,
    Deal,
    DictionaryItem,
    Lead,
    MarketingSpend,
    PipelineStage,
    Product,
    User,
)
from app.schemas.reference import (
    CustomFieldIn,
    CustomFieldOut,
    CustomFieldUpdate,
    DictionaryItemIn,
    DictionaryItemOut,
    DictionaryItemUpdate,
    MarketingSpendIn,
    MarketingSpendOut,
    ProductIn,
    ProductOut,
    StageIn,
    StageOrderIn,
    StageOut,
)
from app.schemas.users import ApiKeyCreated, ApiKeyOut
from app.services.common import DEFAULT_SETTINGS, get_setting, set_setting
from app.services.journal import audit
from app.services.storage import get_storage, make_key

router = APIRouter(tags=["Справочники и настройки"])


# ---------- Справочники ----------

@router.get("/dictionaries", response_model=list[DictionaryItemOut])
def dictionaries(kind: str | None = None, active_only: bool = False, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    q = select(DictionaryItem).order_by(DictionaryItem.kind, DictionaryItem.sort, DictionaryItem.name)
    if kind:
        q = q.where(DictionaryItem.kind == kind)
    if active_only:
        q = q.where(DictionaryItem.is_active.is_(True))
    return db.scalars(q).all()


@router.post("/dictionaries", response_model=DictionaryItemOut, status_code=201)
def create_dictionary_item(data: DictionaryItemIn, request: Request, user: User = Depends(require("dictionaries.edit")),
                           db: Session = Depends(get_db)):
    item = DictionaryItem(**data.model_dump())
    db.add(item)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Такое значение уже есть в справочнике")
    audit(db, user, "dictionary_create", f"Справочник «{data.kind}»: добавлено «{data.name}»", entity="dictionary",
          entity_id=item.id, request=request)
    db.commit()
    return item


@router.patch("/dictionaries/{item_id}", response_model=DictionaryItemOut)
def update_dictionary_item(item_id: int, data: DictionaryItemUpdate, user: User = Depends(require("dictionaries.edit")),
                           db: Session = Depends(get_db)):
    item = db.get(DictionaryItem, item_id)
    if item is None:
        raise HTTPException(404, "Значение не найдено")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Такое значение уже есть в справочнике")
    return item


@router.delete("/dictionaries/{item_id}")
def delete_dictionary_item(item_id: int, request: Request, user: User = Depends(require("dictionaries.edit")),
                           db: Session = Depends(get_db)):
    item = db.get(DictionaryItem, item_id)
    if item is None:
        raise HTTPException(404, "Значение не найдено")
    used = (db.scalar(select(func.count()).select_from(Company).where(
        (Company.industry_id == item_id) | (Company.region_id == item_id) | (Company.client_type_id == item_id) |
        (Company.source_id == item_id))) or 0) + (db.scalar(select(func.count()).select_from(Lead).where(
            (Lead.source_id == item_id) | (Lead.reject_reason_id == item_id))) or 0)
    if used:
        item.is_active = False
        db.commit()
        return {"detail": f"Значение используется в {used} записях — оно скрыто из выбора, но не удалено"}
    audit(db, user, "dictionary_delete", f"Удалено значение справочника «{item.name}»", entity="dictionary",
          entity_id=item.id, request=request)
    db.delete(item)
    db.commit()
    return {"detail": "Удалено"}


# ---------- Этапы воронки ----------

@router.get("/stages", response_model=list[StageOut])
def stages(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(PipelineStage).order_by(PipelineStage.sort, PipelineStage.id)).all()


@router.post("/stages", response_model=StageOut, status_code=201)
def create_stage(data: StageIn, user: User = Depends(require("pipeline.edit")), db: Session = Depends(get_db)):
    stage = PipelineStage(**data.model_dump())
    db.add(stage)
    db.commit()
    return stage


@router.put("/stages/order", response_model=list[StageOut])
def reorder_stages(data: StageOrderIn, user: User = Depends(require("pipeline.edit")), db: Session = Depends(get_db)):
    for idx, sid in enumerate(data.ids):
        stage = db.get(PipelineStage, sid)
        if stage:
            stage.sort = (idx + 1) * 10
    db.commit()
    return db.scalars(select(PipelineStage).order_by(PipelineStage.sort)).all()


@router.patch("/stages/{stage_id}", response_model=StageOut)
def update_stage(stage_id: int, data: StageIn, user: User = Depends(require("pipeline.edit")),
                 db: Session = Depends(get_db)):
    stage = db.get(PipelineStage, stage_id)
    if stage is None:
        raise HTTPException(404, "Этап не найден")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(stage, k, v)
    db.commit()
    return stage


@router.delete("/stages/{stage_id}")
def delete_stage(stage_id: int, user: User = Depends(require("pipeline.edit")), db: Session = Depends(get_db)):
    stage = db.get(PipelineStage, stage_id)
    if stage is None:
        raise HTTPException(404, "Этап не найден")
    used = db.scalar(select(func.count()).select_from(Deal).where(Deal.stage_id == stage_id)) or 0
    if used:
        raise HTTPException(409, f"На этапе {used} сделок. Перенесите их или сделайте этап неактивным")
    db.delete(stage)
    db.commit()
    return {"detail": "Удалено"}


# ---------- Каталог продуктов ----------

@router.get("/products", response_model=list[ProductOut])
def products(q: str | None = None, active_only: bool = False, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    stmt = select(Product).order_by(Product.category, Product.name)
    if q:
        stmt = stmt.where(func.lower(Product.name).like(f"%{q.lower()}%"))
    if active_only:
        stmt = stmt.where(Product.is_active.is_(True))
    return db.scalars(stmt).all()


@router.post("/products", response_model=ProductOut, status_code=201)
def create_product(data: ProductIn, user: User = Depends(require("products.edit")), db: Session = Depends(get_db)):
    p = Product(**data.model_dump())
    db.add(p)
    db.commit()
    return p


@router.patch("/products/{product_id}", response_model=ProductOut)
def update_product(product_id: int, data: ProductIn, request: Request, user: User = Depends(require("products.edit")),
                   db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if p is None:
        raise HTTPException(404, "Продукт не найден")
    values = data.model_dump(exclude_unset=True)
    if "price" in values and float(p.price) != values["price"]:
        audit(db, user, "price_change", f"Изменена цена «{p.name}»: {float(p.price)} → {values['price']}",
              entity="product", entity_id=p.id, request=request)
    for k, v in values.items():
        setattr(p, k, v)
    db.commit()
    return p


# ---------- Пользовательские поля ----------

def _slug(label: str) -> str:
    tr = str.maketrans("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
                       "abvgdeejziiklmnoprstufhccss_y_eua")
    s = re.sub(r"[^a-z0-9]+", "_", label.lower().translate(tr)).strip("_")
    return (s or "field")[:40]


@router.get("/custom-fields", response_model=list[CustomFieldOut])
def custom_fields(entity: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(CustomField).order_by(CustomField.entity, CustomField.sort, CustomField.id)
    if entity:
        q = q.where(CustomField.entity == entity)
    return db.scalars(q).all()


@router.post("/custom-fields", response_model=CustomFieldOut, status_code=201)
def create_custom_field(data: CustomFieldIn, request: Request, user: User = Depends(require("custom_fields.edit")),
                        db: Session = Depends(get_db)):
    if data.field_type == "select" and not data.options:
        raise HTTPException(422, "Для поля-списка укажите варианты значений")
    base = key = _slug(data.label)
    n = 1
    while db.scalars(select(CustomField).where(CustomField.entity == data.entity, CustomField.key == key)).first():
        n += 1
        key = f"{base}_{n}"
    f = CustomField(key=key, **data.model_dump())
    db.add(f)
    audit(db, user, "custom_field_create", f"Добавлено поле «{data.label}» ({data.entity})", entity="custom_field",
          request=request)
    db.commit()
    return f


@router.patch("/custom-fields/{field_id}", response_model=CustomFieldOut)
def update_custom_field(field_id: int, data: CustomFieldUpdate, user: User = Depends(require("custom_fields.edit")),
                        db: Session = Depends(get_db)):
    f = db.get(CustomField, field_id)
    if f is None:
        raise HTTPException(404, "Поле не найдено")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(f, k, v)
    db.commit()
    return f


@router.delete("/custom-fields/{field_id}")
def delete_custom_field(field_id: int, request: Request, user: User = Depends(require("custom_fields.edit")),
                        db: Session = Depends(get_db)):
    f = db.get(CustomField, field_id)
    if f is None:
        raise HTTPException(404, "Поле не найдено")
    audit(db, user, "custom_field_delete", f"Удалено поле «{f.label}» ({f.entity})", entity="custom_field",
          entity_id=f.id, request=request)
    db.delete(f)
    db.commit()
    return {"detail": "Удалено. Ранее введённые значения сохранены в карточках, но не отображаются"}


# ---------- Маркетинговые бюджеты ----------

@router.get("/marketing-spend", response_model=list[MarketingSpendOut], tags=["Маркетинг"])
def marketing_spend(user: User = Depends(require("analytics.team")), db: Session = Depends(get_db)):
    return db.scalars(select(MarketingSpend).order_by(MarketingSpend.month.desc())).all()


@router.put("/marketing-spend", response_model=MarketingSpendOut, tags=["Маркетинг"])
def upsert_marketing_spend(data: MarketingSpendIn, user: User = Depends(require("marketing.edit")),
                           db: Session = Depends(get_db)):
    month = data.month.replace(day=1)
    row = db.scalars(select(MarketingSpend).where(MarketingSpend.source_id == data.source_id,
                                                  MarketingSpend.month == month)).first()
    if row is None:
        row = MarketingSpend(source_id=data.source_id, month=month, amount=data.amount, comment=data.comment)
        db.add(row)
    else:
        row.amount, row.comment = data.amount, data.comment
    db.commit()
    return row


@router.delete("/marketing-spend/{row_id}", tags=["Маркетинг"])
def delete_marketing_spend(row_id: int, user: User = Depends(require("marketing.edit")), db: Session = Depends(get_db)):
    row = db.get(MarketingSpend, row_id)
    if row:
        db.delete(row)
        db.commit()
    return {"detail": "Удалено"}


# ---------- Системные настройки ----------

PUBLIC_SETTINGS = {"company_profile", "currencies"}


@router.get("/integrations/status", summary="Режимы интеграций без секретов подключения")
def integration_status(user: User = Depends(require("settings.manage"))):
    return {
        "smtp": "demo" if settings.SMTP_HOST in ("mailpit", "localhost", "127.0.0.1") else
                "configured" if settings.SMTP_HOST else "not_configured",
        "imap": "disabled" if not settings.IMAP_ENABLED else
                "configured" if settings.IMAP_HOST and settings.IMAP_USER and settings.IMAP_PASSWORD else "not_configured",
        "telephony": "demo" if settings.TELEPHONY_PROVIDER == "mock" else
                     "configured" if settings.TELEPHONY_API_URL else "not_configured",
        "telegram": "configured" if settings.TELEGRAM_BOT_TOKEN else "not_configured",
        "accounting": "export",
        "rate_limit": settings.RATE_LIMIT_PER_MINUTE,
    }


@router.get("/settings")
def get_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    keys = DEFAULT_SETTINGS.keys() if user.role == "admin" else PUBLIC_SETTINGS
    return {k: get_setting(db, k) for k in keys}


@router.put("/settings/{key}")
def put_setting(key: str, value: dict, request: Request, user: User = Depends(require("settings.manage")),
                db: Session = Depends(get_db)):
    if key not in DEFAULT_SETTINGS:
        raise HTTPException(404, "Неизвестная настройка")
    current = get_setting(db, key)
    merged = {**current, **value} if isinstance(current, dict) else value
    if key == "lead_distribution" and merged.get("mode") not in ("round_robin", "least_loaded", "off"):
        raise HTTPException(422, "Неизвестный режим распределения")
    set_setting(db, key, merged)
    audit(db, user, "settings_change", f"Изменены настройки «{key}»", entity="settings", request=request)
    db.commit()
    return merged


@router.post("/settings/logo")
def upload_logo(file: UploadFile = File(...), user: User = Depends(require("settings.manage")),
                db: Session = Depends(get_db)):
    if file.content_type not in ("image/png", "image/jpeg", "image/svg+xml"):
        raise HTTPException(422, "Логотип должен быть в формате PNG, JPG или SVG")
    data = file.file.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(413, "Размер логотипа не должен превышать 2 МБ")
    key = make_key("branding", file.filename or "logo.png")
    get_storage().put(key, data, file.content_type)
    profile = get_setting(db, "company_profile")
    profile["logo_key"] = key
    set_setting(db, "company_profile", profile)
    db.commit()
    return {"logo_key": key}


@router.get("/settings/logo")
def get_logo(db: Session = Depends(get_db)):
    key = get_setting(db, "company_profile").get("logo_key")
    if not key:
        raise HTTPException(404, "Логотип не загружен")
    mime = "image/svg+xml" if key.endswith(".svg") else ("image/jpeg" if key.endswith((".jpg", ".jpeg")) else "image/png")
    return Response(get_storage().get(key), media_type=mime, headers={"Cache-Control": "max-age=300"})


# ---------- API-ключи для сайта и внешних систем ----------

def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


@router.get("/api-keys", response_model=list[ApiKeyOut], tags=["Интеграции"])
def api_keys(user: User = Depends(require("integrations.manage")), db: Session = Depends(get_db)):
    return db.scalars(select(ApiKey).order_by(ApiKey.id.desc())).all()


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=201, tags=["Интеграции"])
def create_api_key(name: str, request: Request, user: User = Depends(require("integrations.manage")),
                   db: Session = Depends(get_db)):
    key = "crm_" + random_token(24)
    row = ApiKey(name=name[:255], prefix=key[:12], key_hash=hash_key(key), created_by=user.id)
    db.add(row)
    db.flush()
    audit(db, user, "api_key_create", f"Создан API-ключ «{name}»", entity="api_key", entity_id=row.id,
          request=request)
    db.commit()
    return ApiKeyCreated(**ApiKeyOut.model_validate(row).model_dump(), key=key)


@router.delete("/api-keys/{key_id}", tags=["Интеграции"])
def revoke_api_key(key_id: int, request: Request, user: User = Depends(require("integrations.manage")),
                   db: Session = Depends(get_db)):
    row = db.get(ApiKey, key_id)
    if row is None:
        raise HTTPException(404, "Ключ не найден")
    row.is_active = False
    audit(db, user, "api_key_revoke", f"Отозван API-ключ «{row.name}»", entity="api_key", entity_id=row.id,
          request=request)
    db.commit()
    return {"detail": "Ключ отозван"}
