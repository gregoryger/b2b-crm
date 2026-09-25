"""Наполнение системы: справочники по умолчанию и демонстрационные данные.

    python -m app.seed            — справочники и администратор (если база пуста)
    python -m app.seed --demo     — + демо-данные за 12 месяцев (для показа и обучения)
    python -m app.seed --demo --reset — очистить базу и заполнить заново
"""
import argparse
import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, text

from app.core.security import hash_password, phone_hash
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import (
    Activity,
    Act,
    ApiKey,
    Company,
    Contact,
    CustomField,
    Deal,
    DealContact,
    DealMember,
    DealProduct,
    DealStageHistory,
    DictionaryItem,
    EmailMessage,
    Invoice,
    Lead,
    MarketingSpend,
    Notification,
    Payment,
    PipelineStage,
    Product,
    Proposal,
    ProposalItem,
    ProposalTemplate,
    ReportSchedule,
    Task,
    User,
)
from app.services.common import set_setting

STAGES = [
    ("Первичный контакт", 10, "gray", "open"),
    ("Выявление потребностей", 20, "blue", "open"),
    ("КП", 40, "cyan", "open"),
    ("Переговоры", 60, "violet", "open"),
    ("Договор", 80, "orange", "open"),
    ("Оплата", 90, "yellow", "open"),
    ("Успех", 100, "green", "won"),
    ("Отказ", 0, "red", "lost"),
]
DICTS = {
    "industry": ["Производство", "Дистрибуция", "Розничная торговля", "Строительство", "Госсектор", "Логистика",
                 "IT и телеком", "Финансы и страхование", "Медицина", "Образование", "HoReCa", "Энергетика"],
    "region": ["Москва", "Санкт-Петербург", "Новосибирская обл.", "Красноярский край", "Свердловская обл.",
               "Республика Татарстан", "Краснодарский край", "Нижегородская обл.", "Самарская обл.",
               "Приморский край", "Иркутская обл.", "Ростовская обл."],
    "client_type": ["Конечный заказчик", "Дистрибьютор", "Розница", "Госсектор", "Интегратор"],
    "loss_reason": ["Высокая цена", "Выбрали конкурента", "Нет бюджета", "Не выходит на связь",
                    "Нецелевой запрос", "Проект отложен", "Не устроили сроки"],
}
SOURCES = [("website", "Форма сайта"), ("email", "Email"), ("phone", "Телефон"), ("manual", "Ручной ввод"),
           ("api", "Лендинги (API)"), ("yandex_direct", "Яндекс Директ"), ("exhibition", "Выставки"),
           ("referral", "Рекомендации")]


def seed_reference(db) -> None:
    if db.scalar(select(PipelineStage.id).limit(1)) is None:
        for i, (name, prob, color, kind) in enumerate(STAGES, 1):
            db.add(PipelineStage(name=name, sort=i * 10, probability=prob, color=color, kind=kind))
    if db.scalar(select(DictionaryItem.id).limit(1)) is None:
        for kind, names in DICTS.items():
            for i, name in enumerate(names, 1):
                db.add(DictionaryItem(kind=kind, name=name, sort=i * 10))
        for i, (code, name) in enumerate(SOURCES, 1):
            db.add(DictionaryItem(kind="lead_source", code=code, name=name, sort=i * 10))
    db.flush()


def seed_admin(db) -> None:
    if db.scalar(select(User.id).limit(1)) is None:
        db.add(User(email="admin@crm.local", full_name="Администратор системы", role="admin",
                    password_hash=hash_password("admin12345"), must_change_password=True, onboarding_done=True))
        print("Создан администратор: admin@crm.local / admin12345 (смените пароль при первом входе)")


# ---------------- Демо-данные ----------------

MALE = [("Смирнов", "Андрей", "Павлович"),
        ("Кузнецов", "Олег", "Викторович"), ("Волков", "Максим", "Андреевич"), ("Фёдоров", "Илья", "Николаевич"),
        ("Морозов", "Сергей", "Александрович"), ("Лебедев", "Роман", "Олегович"), ("Егоров", "Павел", "Юрьевич"),
        ("Зайцев", "Артём", "Дмитриевич"), ("Соловьёв", "Виктор", "Геннадьевич"), ("Беляев", "Константин", "Ильич"),
        ("Тарасов", "Михаил", "Борисович"), ("Белов", "Николай", "Степанович"), ("Комаров", "Евгений", "Романович"),
        ("Киселёв", "Антон", "Валерьевич"), ("Макаров", "Григорий", "Львович"), ("Андреев", "Кирилл", "Олегович"),
        ("Сергеев", "Виталий", "Иванович")]
FEMALE = [("Новикова", "Ольга", "Дмитриевна"), ("Семёнова", "Наталья", "Олеговна"), ("Тихонова", "Вера", "Андреевна"),
          ("Лазарева", "Марина", "Сергеевна"), ("Филиппова", "Анастасия", "Игоревна"),
          ("Голубева", "Ирина", "Павловна"), ("Виноградова", "Татьяна", "Алексеевна"), ("Богданова", "Юлия", "Романовна"),
          ("Воробьёва", "Светлана", "Николаевна"), ("Медведева", "Алина", "Максимовна"), ("Жукова", "Дарья", "Евгеньевна")]
POSITIONS = [("Генеральный директор", "decision_maker"), ("Коммерческий директор", "decision_maker"),
             ("Финансовый директор", "decision_maker"), ("Руководитель отдела закупок", "influencer"),
             ("Менеджер по закупкам", "influencer"), ("IT-директор", "technical"), ("Главный инженер", "technical"),
             ("Системный администратор", "technical"), ("Офис-менеджер", "other"), ("Руководитель проекта", "influencer")]
COMPANY_ROOTS = ["СибТехСнаб", "УралМеталлТорг", "ВолгаАгроПром", "СеверСтройИнвест", "ДальЛогистик", "ТрансКом",
                 "ПромАвтоматика", "ЭнергоРесурс", "МедТехника Плюс", "Альфа-Дистрибуция", "ГлавСнаб", "Невский Порт",
                 "БалтТрейд", "ТехноСфера", "Кристалл-М", "Меридиан", "Вектор Групп", "Горизонт", "Орион Системс",
                 "Континент", "Прогресс-Холдинг", "ЕнисейСтрой", "Байкал Сервис", "Азимут", "Стандарт Плюс",
                 "Фарма Логистик", "ЭкоПродукт", "Гранит", "Сигма Инжиниринг", "РегионСнаб", "Полюс Трейд",
                 "Технопарк Регион", "СтройМаркет", "Агро-Сибирь", "Мегаполис Ритейл", "Спектр", "Инфолинк",
                 "Атлант Групп", "Вертикаль", "КамаТехСервис", "ДонАгро", "ЮгСтройКомплект", "Приморский Терминал",
                 "Иркут Энерго Сервис", "Сфера Здоровья", "Эталон", "Магистраль", "Нижегородский Станкозавод",
                 "Самара Хим", "Логос", "Новые Технологии", "Премьер Отель Групп", "Академия Знаний",
                 "Городская клиническая больница №4", "Центр образования «Лидер»", "ФинКонсалт", "Страховой дом «Опора»",
                 "Ритейл Хаб", "СмартОфис", "Техносила Опт"]
PRODUCTS = [
    ("Сервер Rack 2U, 2×Xeon, 128 ГБ", "Оборудование", "шт.", 685000, 540000),
    ("Система хранения данных 48 ТБ", "Оборудование", "шт.", 1240000, 990000),
    ("Коммутатор 48 портов L3", "Оборудование", "шт.", 186000, 142000),
    ("Рабочая станция инженера", "Оборудование", "шт.", 164000, 128000),
    ("Ноутбук бизнес-класса", "Оборудование", "шт.", 98000, 79000),
    ("Лицензия ПО учёта, на пользователя/год", "Лицензии", "лиц.", 24000, 9000),
    ("Лицензия защиты конечных точек/год", "Лицензии", "лиц.", 4200, 2100),
    ("Внедрение и настройка", "Услуги", "час", 4500, 1800),
    ("Техническая поддержка «Стандарт»/мес", "Услуги", "мес.", 65000, 26000),
    ("Техническая поддержка «Премиум»/мес", "Услуги", "мес.", 145000, 58000),
    ("Аудит IT-инфраструктуры", "Услуги", "усл.", 180000, 60000),
    ("Обучение персонала (группа до 10 чел.)", "Услуги", "усл.", 95000, 30000),
    ("Монтаж СКС, за порт", "Услуги", "порт", 3200, 1500),
    ("Облачное резервное копирование, 1 ТБ/мес", "Облачные сервисы", "мес.", 12000, 5000),
]


def gen_inn(rnd: random.Random) -> str:
    while True:
        d = [rnd.randint(0, 9) for _ in range(9)]
        d[0] = rnd.randint(1, 9)
        coefs = [2, 4, 10, 3, 5, 9, 4, 6, 8]
        c = sum(a * b for a, b in zip(coefs, d)) % 11 % 10
        inn = "".join(map(str, d)) + str(c)
        return inn


def gen_phone(rnd: random.Random, mobile: bool = True) -> str:
    code = rnd.choice(["903", "905", "910", "915", "916", "926", "985", "999", "913", "923"]) if mobile else \
        rnd.choice(["495", "812", "383", "391", "343", "843", "861", "831", "846", "423"])
    n = rnd.randint(1000000, 9999999)
    return f"+7 ({code}) {str(n)[:3]}-{str(n)[3:5]}-{str(n)[5:]}"


def translit(s: str) -> str:
    table = str.maketrans({"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z",
                           "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
                           "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh",
                           "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya"})
    return "".join(ch for ch in s.lower().translate(table) if ch.isalnum())


def utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def work_time(dt: datetime, rnd: random.Random) -> datetime:
    """Сдвигает момент на рабочее время по Москве (пн–пт, 9–19)."""
    dt = utc(dt)
    while dt.weekday() >= 5:
        dt -= timedelta(days=1)
    return dt.replace(hour=rnd.randint(6, 15), minute=rnd.choice([0, 5, 10, 15, 20, 30, 40, 45, 50]), second=0)


def reset_db() -> None:
    with engine.begin() as conn:
        names = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    print("База очищена")


def seed_demo(db) -> None:
    rnd = random.Random(2026)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    today = now.date()

    stages = {s.name: s for s in db.scalars(select(PipelineStage))}
    open_stages = [s for s in sorted(stages.values(), key=lambda s: s.sort) if s.kind == "open"]
    won_stage = next(s for s in stages.values() if s.kind == "won")
    lost_stage = next(s for s in stages.values() if s.kind == "lost")
    dic = {kind: list(db.scalars(select(DictionaryItem).where(DictionaryItem.kind == kind)))
           for kind in ("industry", "region", "client_type", "loss_reason", "lead_source")}
    src_by_code = {s.code: s for s in dic["lead_source"]}

    # ---- Профиль компании-продавца ----
    set_setting(db, "company_profile", {
        "name": "ООО «ТехноПартнёр»", "full_name": "Общество с ограниченной ответственностью «ТехноПартнёр»",
        "inn": "7701234565", "kpp": "770101001", "ogrn": "1207700123456",
        "address": "123112, г. Москва, Пресненская наб., д. 10, стр. 2, офис 415",
        "phone": "+7 (495) 120-45-67", "email": "sales@technopartner.example", "website": "technopartner.example",
        "bank_name": "ПАО «Банк Пример», г. Москва", "bik": "044525000", "account": "40702810900000012345",
        "corr_account": "30101810400000000225", "director": "Соколова А. В.", "accountant": "Павлова Е. И.",
        "logo_key": None, "accent_color": "#1c7ed6",
    })

    # ---- Пользователи ----
    pwd = hash_password("demo12345")
    users = {
        "admin": User(email="admin@demo.ru", full_name="Григорьев Владимир Петрович", role="admin",
                      position="Системный администратор", password_hash=pwd, phone="+7 (495) 120-45-60"),
        "head": User(email="head@demo.ru", full_name="Соколова Анна Викторовна", role="head",
                     position="Руководитель отдела продаж", department="Отдел продаж", password_hash=pwd,
                     phone="+7 (495) 120-45-61", sip_extension="101"),
        "m1": User(email="petrov@demo.ru", full_name="Петров Дмитрий Сергеевич", role="manager",
                   position="Менеджер по работе с ключевыми клиентами", department="Отдел продаж",
                   password_hash=pwd, phone="+7 (916) 204-11-22", sip_extension="102"),
        "m2": User(email="kozlova@demo.ru", full_name="Козлова Мария Андреевна", role="manager",
                   position="Менеджер по продажам", department="Отдел продаж", password_hash=pwd,
                   phone="+7 (916) 204-33-44", sip_extension="103"),
        "m3": User(email="nikitin@demo.ru", full_name="Никитин Алексей Игоревич", role="manager",
                   position="Менеджер по продажам", department="Отдел продаж", password_hash=pwd,
                   phone="+7 (926) 311-55-66", sip_extension="104"),
        "m4": User(email="orlova@demo.ru", full_name="Орлова Екатерина Сергеевна", role="manager",
                   position="Младший менеджер по продажам", department="Отдел продаж", password_hash=pwd,
                   phone="+7 (926) 311-77-88", sip_extension="105"),
        "mk": User(email="marketer@demo.ru", full_name="Васильев Игорь Николаевич", role="marketer",
                   position="Маркетолог", department="Маркетинг", password_hash=pwd, phone="+7 (495) 120-45-65"),
    }
    for u in users.values():
        u.created_at = now - timedelta(days=400)
        u.last_login = now - timedelta(hours=rnd.randint(1, 30))
    db.add_all(users.values())
    db.flush()
    managers = [users["m1"], users["m2"], users["m3"], users["m4"]]
    # «сила» менеджеров: у кого-то конверсия выше — чтобы отчёты были показательными
    skill = {users["m1"].id: 0.62, users["m2"].id: 0.55, users["m3"].id: 0.45, users["m4"].id: 0.35,
             users["head"].id: 0.6}

    # ---- Каталог ----
    products = []
    for name, cat, unit, price, cost in PRODUCTS:
        p = Product(name=name, category=cat, unit=unit, price=price, cost=cost, sku=f"TP-{len(products) + 101}",
                    vat_rate=20)
        products.append(p)
    db.add_all(products)

    # ---- Пользовательские поля ----
    db.add_all([
        CustomField(entity="company", key="employees", label="Количество сотрудников", field_type="number", sort=10),
        CustomField(entity="company", key="it_budget", label="Годовой IT-бюджет", field_type="select", sort=20,
                    options=["до 1 млн ₽", "1–5 млн ₽", "5–20 млн ₽", "более 20 млн ₽"]),
        CustomField(entity="deal", key="competitors", label="Конкуренты в сделке", field_type="text", sort=10),
        CustomField(entity="deal", key="contract_type", label="Тип договора", field_type="select", sort=20,
                    options=["Поставка", "Услуги", "Комплексный", "Рамочный"]),
        CustomField(entity="deal", key="tender", label="Через тендер", field_type="checkbox", sort=30),
        CustomField(entity="contact", key="birthday", label="День рождения", field_type="date", sort=10),
    ])

    # ---- Шаблоны КП ----
    t_std = ProposalTemplate(
        name="Стандартное КП (оборудование и услуги)", description="Универсальный шаблон для большинства клиентов",
        intro_text=("Уважаемый(ая) {{контакт.имя}}!\n\nБлагодарим за интерес к решениям {{компания.название}}. "
                    "По итогам нашего обсуждения подготовили предложение для {{клиент.название}}. "
                    "Состав и стоимость приведены ниже; готовы скорректировать конфигурацию под ваши задачи."),
        terms_text=("• Цены указаны в рублях, включая НДС 20%.\n• Срок поставки оборудования — 10–15 рабочих дней "
                    "с момента оплаты.\n• Оплата: 50% предоплата, 50% по факту поставки.\n• Гарантия на "
                    "оборудование — 36 месяцев.\n• Предложение действительно до {{срок_действия}}."),
        footer_text="{{менеджер.фио}} · {{менеджер.телефон}} · {{менеджер.email}}", accent_color="#1c7ed6",
    )
    t_gov = ProposalTemplate(
        name="КП для госсектора", description="С учётом требований 44-ФЗ/223-ФЗ",
        industry_id=next(i.id for i in dic["industry"] if i.name == "Госсектор"),
        intro_text=("В ответ на запрос {{клиент.название}} направляем коммерческое предложение для обоснования "
                    "начальной (максимальной) цены контракта."),
        terms_text=("• Цены включают НДС 20%, доставку и разгрузку.\n• Оборудование внесено в реестр "
                    "российской промышленной продукции.\n• Оплата по факту поставки в течение 7 рабочих дней.\n"
                    "• Предложение действительно до {{срок_действия}}."),
        footer_text="Ответственный: {{менеджер.фио}}, {{менеджер.телефон}}", accent_color="#0b7285",
    )
    t_srv = ProposalTemplate(
        name="Сервисный контракт (поддержка)", description="Ежемесячная техническая поддержка",
        intro_text=("{{контакт.имя}}, добрый день!\n\nПредлагаем взять IT-инфраструктуру {{клиент.название}} "
                    "на сопровождение: мониторинг 24/7, выезд инженера, гарантированное время реакции."),
        terms_text=("• Минимальный срок договора — 12 месяцев.\n• Время реакции на критический инцидент — 1 час.\n"
                    "• Оплата ежемесячно, до 10 числа.\n• Итоговая стоимость в месяц: {{сумма}}."),
        footer_text="{{компания.название}}", accent_color="#5f3dc4", default_items=[{"product_id": None}],
    )
    db.add_all([t_std, t_gov, t_srv])
    db.flush()
    t_srv.default_items = [{"product_id": products[9].id, "quantity": 1}, {"product_id": products[13].id, "quantity": 2}]

    # ---- Компании и контакты ----
    companies: list[Company] = []
    contacts_by_company: dict[int, list[Contact]] = {}
    used_people = set()
    for i, root in enumerate(COMPANY_ROOTS):
        industry = rnd.choice(dic["industry"])
        if "больница" in root:
            industry = next(x for x in dic["industry"] if x.name == "Медицина")
        elif "образования" in root or "Академия" in root:
            industry = next(x for x in dic["industry"] if x.name == "Образование")
        elif "Отель" in root:
            industry = next(x for x in dic["industry"] if x.name == "HoReCa")
        gov = industry.name in ("Госсектор", "Медицина", "Образование") and rnd.random() < 0.7
        form = rnd.choice(["ГБУ", "ГКУ", "ФГБУ"]) if gov else rnd.choice(["ООО", "ООО", "ООО", "АО", "ПАО"])
        name = f"{form} «{root}»" if not root.startswith(("Городская", "Центр")) else root
        region = rnd.choice(dic["region"])
        # большая часть клиентов — давние, часть пришла в течение года
        created = now - timedelta(days=rnd.randint(380, 900) if rnd.random() < 0.75 else rnd.randint(20, 380))
        manager = rnd.choice(managers + [users["head"]] if rnd.random() < 0.1 else managers)
        domain = translit(root.split()[0])[:14] or f"company{i}"
        c = Company(
            name=name, full_name=None, inn=gen_inn(rnd), kpp=f"{rnd.randint(1000, 9999)}01001",
            ogrn=f"1{rnd.randint(10, 23):02d}{rnd.randint(1000000000, 9999999999)}",
            legal_address=f"{region.name}, ул. {rnd.choice(['Ленина', 'Советская', 'Промышленная', 'Мира', 'Заводская', 'Кирова', 'Гагарина'])}, д. {rnd.randint(1, 120)}",
            industry_id=industry.id, region_id=region.id,
            client_type_id=(next(x for x in dic["client_type"] if x.name == "Госсектор").id if gov
                            else rnd.choice(dic["client_type"]).id),
            source_id=rnd.choice(dic["lead_source"]).id, manager_id=manager.id, status="prospect",
            phone=gen_phone(rnd, mobile=False), email=f"info@{domain}.ru", website=f"{domain}.ru",
            custom_fields={"employees": rnd.choice([25, 60, 120, 250, 480, 900, 1500, 3200]),
                           "it_budget": rnd.choice(["до 1 млн ₽", "1–5 млн ₽", "5–20 млн ₽", "более 20 млн ₽"])},
            created_at=created, updated_at=created,
        )
        c.phone_hash = phone_hash(c.phone)
        db.add(c)
        db.flush()
        companies.append(c)
        people = []
        for _ in range(rnd.choice([1, 2, 2, 3, 3, 4])):
            pool = MALE if rnd.random() < 0.6 else FEMALE
            for _ in range(20):
                last, first, middle = rnd.choice(pool)
                if (c.id, last) not in used_people:
                    break
            used_people.add((c.id, last))
            pos, role = rnd.choice(POSITIONS)
            ct = Contact(company_id=c.id, owner_id=manager.id, last_name=last, first_name=first, middle_name=middle,
                         full_name=f"{last} {first} {middle}", position=pos, role_in_deal=role,
                         phone_mobile=gen_phone(rnd), phone_work=c.phone if rnd.random() < 0.5 else None,
                         email=f"{translit(first)[0]}.{translit(last)}@{domain}.ru",
                         telegram=f"@{translit(first)}_{translit(last)}"[:30] if rnd.random() < 0.4 else None,
                         custom_fields={}, created_at=created, updated_at=created)
            ct.phone_mobile_hash = phone_hash(ct.phone_mobile)
            ct.phone_work_hash = phone_hash(ct.phone_work)
            db.add(ct)
            people.append(ct)
        db.flush()
        contacts_by_company[c.id] = people
        db.add(Activity(type="created", title="Компания добавлена в базу", object_type="company", object_id=c.id,
                        user_id=manager.id, company_id=c.id, meta={}, occurred_at=created))

    # ---- Маркетинговые бюджеты за 12 месяцев ----
    budgets = {"yandex_direct": 180000, "exhibition": 120000, "website": 60000, "api": 45000, "email": 15000}
    m = (today.replace(day=1) - timedelta(days=360)).replace(day=1)
    while m <= today:
        for code, base in budgets.items():
            if code == "exhibition" and m.month not in (3, 4, 9, 10, 11):
                continue
            db.add(MarketingSpend(source_id=src_by_code[code].id, month=m,
                                  amount=round(base * rnd.uniform(0.75, 1.3), -3)))
        m = (m.replace(day=28) + timedelta(days=4)).replace(day=1)

    # ---- Сделки (часть — из лидов) ----
    def add_history(deal: Deal, path: list[PipelineStage], start: datetime, end: datetime, user: User):
        """Равномерно раскладывает переходы по этапам между start и end."""
        steps = len(path)
        prev_stage, prev_time = None, start
        for idx, st in enumerate(path):
            t = start + (end - start) * (idx / max(steps - 1, 1)) if idx else start
            t = utc(t)
            db.add(DealStageHistory(deal_id=deal.id, from_stage_id=prev_stage.id if prev_stage else None,
                                    to_stage_id=st.id, user_id=user.id, changed_at=t,
                                    seconds_in_prev=int((t - prev_time).total_seconds()) if prev_stage else None))
            if prev_stage:
                db.add(Activity(type="stage_change", title=f"Этап: {prev_stage.name} → {st.name}" if st.kind == "open"
                                else ("Сделка выиграна 🎉" if st.kind == "won" else "Сделка проиграна"),
                                object_type="deal", object_id=deal.id, user_id=user.id, deal_id=deal.id,
                                company_id=deal.company_id, meta={"from": prev_stage.name, "to": st.name},
                                occurred_at=t))
            prev_stage, prev_time = st, t
        deal.stage_changed_at = prev_time

    deal_titles = ["Поставка серверного оборудования", "Модернизация ЛВС", "Лицензии ПО учёта",
                   "Техподдержка инфраструктуры", "Оснащение нового офиса", "Аудит IT-инфраструктуры",
                   "Замена парка рабочих станций", "Система хранения данных", "Антивирусная защита",
                   "Облачное резервное копирование", "Монтаж СКС", "Обучение персонала", "Комплексный проект"]
    deals: list[Deal] = []
    won_deals: list[Deal] = []
    lead_counter = 0

    def make_lines(title: str) -> list[tuple[Product, float, float]]:
        lines = []
        if "сервер" in title.lower():
            lines = [(products[0], rnd.randint(1, 4), 0), (products[7], rnd.choice([16, 24, 40]), 0)]
        elif "ЛВС" in title or "СКС" in title:
            lines = [(products[2], rnd.randint(2, 6), 0), (products[12], rnd.choice([48, 96, 150, 240]), 0)]
        elif "Лицензии" in title:
            lines = [(products[5], rnd.choice([10, 25, 50, 80]), rnd.choice([0, 5, 10]))]
        elif "Техподдержка" in title:
            lines = [(products[rnd.choice([8, 9])], 12, rnd.choice([0, 5]))]
        elif "офиса" in title or "рабочих" in title:
            lines = [(products[rnd.choice([3, 4])], rnd.randint(8, 40), rnd.choice([0, 3, 7])),
                     (products[6], rnd.randint(10, 50), 0)]
        elif "хранения" in title:
            lines = [(products[1], 1, rnd.choice([0, 5])), (products[7], 24, 0)]
        elif "Антивирус" in title:
            lines = [(products[6], rnd.choice([50, 120, 300]), rnd.choice([0, 10]))]
        elif "Облачное" in title:
            lines = [(products[13], rnd.choice([12, 24, 60]), 0)]
        elif "Аудит" in title:
            lines = [(products[10], 1, 0)]
        elif "Обучение" in title:
            lines = [(products[11], rnd.randint(1, 3), 0)]
        else:
            lines = [(products[0], rnd.randint(1, 2), 0), (products[5], rnd.randint(10, 30), 5),
                     (products[7], 40, 0), (products[8], 12, 0)]
        return lines

    n_deals = 150
    for i in range(n_deals):
        created = work_time(now - timedelta(days=rnd.randint(1, 365)), rnd)
        existing = [c for c in companies if c.created_at < created - timedelta(days=1)]
        company = rnd.choice(existing or companies)
        owner = db.get(User, company.manager_id)
        contact = rnd.choice(contacts_by_company[company.id])
        title = rnd.choice(deal_titles)
        age = (now - created).days
        # исход сделки зависит от возраста и «силы» менеджера
        if age < 25:
            outcome = "open"
        elif age < 70:
            outcome = rnd.choices(["open", "won", "lost"], [0.55, 0.25, 0.2])[0]
        else:
            p = skill.get(owner.id, 0.45)
            outcome = rnd.choices(["open", "won", "lost"], [0.08, p, 1 - p - 0.08])[0]

        source = rnd.choices(list(src_by_code.values()), [18, 10, 12, 8, 8, 20, 10, 14])[0]
        lead = None
        if rnd.random() < 0.8:
            lead_counter += 1
            lead_created = work_time(created - timedelta(days=rnd.randint(1, 4)), rnd)
            lead = Lead(title=f"Запрос: {title[0].lower() + title[1:]}", source_id=source.id, status="qualified",
                        assigned_to=owner.id, company_name=company.name, inn=company.inn,
                        contact_name=contact.full_name, contact_position=contact.position,
                        phone=contact.phone_mobile, phone_hash=contact.phone_mobile_hash, email=contact.email,
                        message="Просим прислать коммерческое предложение и сроки поставки.",
                        company_id=company.id, contact_id=contact.id, custom_fields={},
                        first_response_at=lead_created + timedelta(minutes=rnd.randint(5, 240)),
                        qualified_at=created, created_at=lead_created, updated_at=created,
                        utm_source="yandex" if source.code == "yandex_direct" else None,
                        utm_campaign="it_infra_b2b" if source.code == "yandex_direct" else None)
            db.add(lead)
            db.flush()
            db.add(Activity(type="created", title="Лид создан", object_type="lead", object_id=lead.id,
                            lead_id=lead.id, meta={"source": source.code}, occurred_at=lead_created))

        lines = make_lines(title)
        deal = Deal(title=f"{title} — {company.name.split('«')[-1].rstrip('»')}"[:255], company_id=company.id,
                    contact_id=contact.id, lead_id=lead.id if lead else None, owner_id=owner.id,
                    stage_id=open_stages[0].id, currency="RUB", custom_fields={
                        "contract_type": rnd.choice(["Поставка", "Услуги", "Комплексный"]),
                        "tender": rnd.random() < 0.15,
                        "competitors": rnd.choice(["", "", "ИнфоСистемы", "ТехЛайн, Компьюлинк", "Сервионика"])},
                    created_at=created, updated_at=created, stage_changed_at=created, amount=0)
        db.add(deal)
        db.flush()
        total = Decimal(0)
        for prod, qty, disc in lines:
            price = Decimal(str(prod.price))
            dp = DealProduct(deal_id=deal.id, product_id=prod.id, name=prod.name, quantity=qty, unit=prod.unit,
                             price=price, discount_percent=disc)
            db.add(dp)
            total += dp.total
        deal.amount = total
        if lead:
            lead.deal_id = deal.id
            lead.estimated_amount = total
        db.add(DealContact(deal_id=deal.id, contact_id=contact.id, role=contact.role_in_deal))
        if rnd.random() < 0.3:
            db.add(DealMember(deal_id=deal.id, user_id=users["head"].id, role="Куратор"))
        db.add(Activity(type="converted" if lead else "created",
                        title="Лид конвертирован в сделку" if lead else f"Создана сделка «{deal.title}»",
                        object_type="deal", object_id=deal.id, user_id=owner.id, deal_id=deal.id,
                        company_id=company.id, lead_id=lead.id if lead else None, meta={}, occurred_at=created))

        if outcome == "open":
            depth = min(int(age / 12), len(open_stages) - 1)
            depth = rnd.randint(max(0, depth - 2), depth)
            path = open_stages[:depth + 1]
            end = created + (now - created) * rnd.uniform(0.4, 0.95)
            add_history(deal, path, created, end, owner)
            st = path[-1]
            deal.stage_id, deal.probability, deal.status = st.id, st.probability, "open"
            deal.close_date = today + timedelta(days=rnd.randint(-10, 75))
        elif outcome == "won":
            duration = timedelta(days=rnd.randint(18, min(max(age - 1, 19), 110)))
            end = min(created + duration, now - timedelta(days=1))
            path = open_stages + [won_stage] if rnd.random() < 0.7 else open_stages[:1] + open_stages[2:] + [won_stage]
            add_history(deal, path, created, end, owner)
            deal.stage_id, deal.probability, deal.status, deal.closed_at = won_stage.id, 100, "won", utc(end)
            deal.close_date = end.date()
            won_deals.append(deal)
            company.status = "active"
        else:
            duration = timedelta(days=rnd.randint(10, min(max(age - 1, 11), 90)))
            end = min(created + duration, now - timedelta(days=1))
            depth = rnd.randint(0, len(open_stages) - 2)
            add_history(deal, open_stages[:depth + 1] + [lost_stage], created, end, owner)
            deal.stage_id, deal.probability, deal.status, deal.closed_at = lost_stage.id, 0, "lost", utc(end)
            deal.close_date = end.date()
            deal.lost_reason_id = rnd.choice(dic["loss_reason"]).id
            deal.lost_comment = rnd.choice(["", "Клиент выбрал более дешёвое предложение",
                                            "Бюджет перенесён на следующий год", "Не дозвонились 3 раза"])
        deal.updated_at = deal.stage_changed_at
        deals.append(deal)

        # взаимодействия по сделке
        span_end = deal.closed_at or now
        for _ in range(rnd.randint(2, 7)):
            t = work_time(created + (span_end - created) * rnd.random(), rnd)
            if t > now:
                t = now - timedelta(hours=rnd.randint(1, 5))
            kind = rnd.choices(["call", "email_out", "meeting", "note", "email_in"], [40, 25, 12, 13, 10])[0]
            titles = {"call": [f"Исходящий звонок: {contact.full_name}", f"Входящий звонок: {contact.full_name}"],
                      "email_out": ["Письмо: уточнение конфигурации", "Письмо: коммерческое предложение",
                                    "Письмо: график поставки"],
                      "meeting": ["Встреча в офисе клиента", "Онлайн-демонстрация решения", "Встреча с ЛПР"],
                      "note": ["Заметка"], "email_in": ["Входящее письмо: вопросы по КП", "Входящее письмо: реквизиты"]}
            bodies = {"call": ["Обсудили сроки и бюджет. Клиент ждёт КП до конца недели.",
                               "Уточнили количество рабочих мест, договорились о демо.",
                               "ЛПР в отпуске до следующей недели, перезвонить.",
                               "Согласовали скидку 5% при 100% предоплате."],
                      "note": ["Клиент сравнивает с двумя конкурентами, важна цена и сроки.",
                               "Решение принимает финансовый директор, нужен расчёт ТСО.",
                               "Интересуются расширенной гарантией."]}
            db.add(Activity(type=kind, title=rnd.choice(titles[kind]),
                            body=rnd.choice(bodies.get(kind, [None])) if kind in bodies else None,
                            object_type="deal", object_id=deal.id, user_id=owner.id, deal_id=deal.id,
                            company_id=company.id, contact_id=contact.id,
                            meta={"duration": rnd.randint(60, 900), "direction": rnd.choice(["in", "out"])}
                            if kind == "call" else {}, occurred_at=utc(t)))
            if company.last_contact_at is None or utc(t) > company.last_contact_at:
                company.last_contact_at = utc(t)

    db.flush()

    # ---- Лиды в работе, новые и отклонённые (не превратившиеся в сделки) ----
    lead_names = [("Нужна техподдержка офиса на 40 мест", 1200000), ("Запрос цены на серверы", 1800000),
                  ("Лицензии для филиала", 450000), ("Монтаж сети на новом складе", 900000),
                  ("Интересует облачный бэкап", 300000), ("Тендер на поставку ноутбуков", 2600000),
                  ("Консультация по импортозамещению", None), ("Обучение сотрудников", 190000),
                  ("Аудит безопасности", 360000), ("Замена СХД", 2400000)]
    new_companies = ["ООО «Северный Ветер»", "ООО «Промтехкомплект»", "АО «Речной Порт»", "ООО «Дельта Фуд»",
                     "ООО «Клиника Здоровье+»", "ООО «Архитектурное бюро Линия»", "ИП Смирнова О. А.",
                     "ООО «ТрансЛес»", "ООО «Цифровой Двор»", "АО «Завод Металлоконструкций»",
                     "ООО «Бизнес Центр Сити»", "ООО «ФудМаркет»"]
    for i in range(70):
        created = work_time(now - timedelta(days=rnd.randint(0, 180)), rnd)
        if created > now:
            created = now - timedelta(minutes=rnd.randint(20, 180))
        age = (now - created).days
        status = "new" if age < 2 and rnd.random() < 0.7 else (
            "in_progress" if age < 20 else rnd.choice(["rejected", "rejected", "in_progress"]))
        pool = MALE if rnd.random() < 0.6 else FEMALE
        last, first, middle = rnd.choice(pool)
        title, est = rnd.choice(lead_names)
        src = rnd.choices(list(src_by_code.values()), [22, 10, 12, 5, 8, 25, 8, 10])[0]
        phone = gen_phone(rnd)
        cname = rnd.choice(new_companies)
        lead = Lead(title=title, source_id=src.id, status=status, assigned_to=rnd.choice(managers).id,
                    company_name=cname, contact_name=f"{last} {first}",
                    contact_position=rnd.choice(POSITIONS)[0], phone=phone, phone_hash=phone_hash(phone),
                    email=f"{translit(first)}.{translit(last)}@mail.example", estimated_amount=est,
                    message=rnd.choice(["Прошу перезвонить", "Пришлите прайс-лист", "Нужна консультация специалиста",
                                        "Хотим получить КП до конца месяца", None]),
                    utm_source="yandex" if src.code == "yandex_direct" else None,
                    utm_medium="cpc" if src.code == "yandex_direct" else None,
                    custom_fields={}, created_at=created, updated_at=created)
        if status != "new":
            lead.first_response_at = created + timedelta(minutes=rnd.randint(4, 150))
        if status == "rejected":
            lead.reject_reason_id = rnd.choice(dic["loss_reason"]).id
        db.add(lead)
        db.flush()
        db.add(Activity(type="created", title="Лид создан", object_type="lead", object_id=lead.id, lead_id=lead.id,
                        meta={"source": src.code}, occurred_at=created))
        if status == "in_progress":
            db.add(Activity(type="call", title=f"Исходящий звонок: {last} {first}",
                            body="Выяснили потребность, запросили реквизиты.", object_type="lead", object_id=lead.id,
                            lead_id=lead.id, user_id=lead.assigned_to, meta={"direction": "out", "duration": 240},
                            occurred_at=lead.first_response_at))
    db.flush()

    # ---- Задачи ----
    task_titles = {"call": ["Позвонить: уточнить решение по КП", "Созвон с ЛПР", "Напомнить об оплате счёта",
                            "Уточнить сроки тендера"],
                   "meeting": ["Встреча в офисе клиента", "Демонстрация решения", "Переговоры по договору"],
                   "email": ["Отправить обновлённую спецификацию", "Направить проект договора"],
                   "proposal": ["Подготовить КП", "Пересчитать КП со скидкой"],
                   "other": ["Согласовать скидку с руководителем", "Проверить наличие на складе"]}
    open_deals = [d for d in deals if d.status == "open"]
    for d in open_deals:
        for _ in range(rnd.randint(1, 2)):
            ttype = rnd.choices(list(task_titles), [45, 20, 15, 12, 8])[0]
            offset_h = rnd.choice([-72, -30, -5, 2, 5, 20, 26, 50, 75, 120, 170, 240])
            due = work_time(now + timedelta(hours=offset_h), rnd).replace(minute=rnd.choice([0, 30]))
            db.add(Task(title=rnd.choice(task_titles[ttype]), type=ttype,
                        priority=rnd.choices(["low", "medium", "high"], [2, 5, 3])[0], status="open",
                        assignee_id=d.owner_id, author_id=d.owner_id, due_at=due,
                        duration_minutes=60 if ttype == "meeting" else 30, deal_id=d.id, company_id=d.company_id,
                        contact_id=d.contact_id, reminder_minutes=rnd.choice([None, 15, 60, 1440]),
                        created_at=due - timedelta(days=3)))
    for d in rnd.sample(deals, 90):
        ttype = rnd.choice(["call", "meeting", "email"])
        due = d.created_at + timedelta(days=rnd.randint(1, 20))
        if due > now:
            continue
        db.add(Task(title=rnd.choice(task_titles[ttype]), type=ttype, priority="medium", status="done",
                    assignee_id=d.owner_id, author_id=d.owner_id, due_at=due, deal_id=d.id, company_id=d.company_id,
                    completed_at=due + timedelta(hours=1), result="Выполнено, результат зафиксирован в ленте",
                    created_at=due - timedelta(days=2)))
    # задачи руководителя
    for i, title in enumerate(["Планёрка отдела продаж", "Разбор воронки с менеджерами", "Встреча с ключевым клиентом"]):
        db.add(Task(title=title, type="meeting", priority="high", status="open", assignee_id=users["head"].id,
                    author_id=users["head"].id,
                    due_at=work_time(now + timedelta(days=i + 1), rnd).replace(hour=[7, 11, 13][i], minute=0),
                    duration_minutes=60, reminder_minutes=15))

    # ---- КП, счета, оплаты, акты ----
    def proposal_for(d: Deal, status: str, sent_at: datetime | None) -> Proposal:
        p = Proposal(number=f"КП-{d.created_at.year}-{d.id:04d}", title=f"Коммерческое предложение: {d.title}"[:255],
                     deal_id=d.id, company_id=d.company_id, contact_id=d.contact_id, template_id=t_std.id,
                     owner_id=d.owner_id, status=status, currency="RUB", vat_rate=20,
                     valid_until=(sent_at or d.created_at).date() + timedelta(days=14),
                     intro_text=t_std.intro_text, terms_text=t_std.terms_text, total=d.amount,
                     tracking_token=f"demo{d.id:05d}{rnd.randint(100000, 999999)}", sent_at=sent_at,
                     sent_to=db.get(Contact, d.contact_id).email if d.contact_id else None,
                     viewed_at=sent_at + timedelta(hours=rnd.randint(1, 40)) if sent_at and status != "sent" else None,
                     created_at=d.created_at + timedelta(days=3))
        db.add(p)
        db.flush()
        for idx, dp in enumerate(d.products):
            db.add(ProposalItem(proposal_id=p.id, product_id=dp.product_id, name=dp.name, quantity=dp.quantity,
                                unit=dp.unit, price=dp.price, discount_percent=dp.discount_percent, sort=idx))
        return p

    kp_stage_sort = open_stages[2].sort
    for d in deals:
        stage = next(s for s in stages.values() if s.id == d.stage_id)
        if d.status == "won" or (d.status == "open" and stage.sort >= kp_stage_sort) or (
                d.status == "lost" and rnd.random() < 0.5):
            sent = d.created_at + timedelta(days=rnd.randint(3, 10))
            if sent > now:
                sent = now - timedelta(hours=5)
            status = "approved" if d.status == "won" else ("rejected" if d.status == "lost" else
                                                           rnd.choice(["sent", "viewed", "viewed"]))
            proposal_for(d, status, sent)
    # пара черновиков
    for d in rnd.sample(open_deals, min(4, len(open_deals))):
        if not db.scalar(select(Proposal.id).where(Proposal.deal_id == d.id)):
            proposal_for(d, "draft", None)

    inv_n = 0
    for d in sorted(won_deals, key=lambda x: x.closed_at):
        inv_n += 1
        issued = (d.closed_at - timedelta(days=rnd.randint(2, 8))).date()
        items = [{"product_id": dp.product_id, "name": dp.name, "quantity": float(dp.quantity), "unit": dp.unit,
                  "price": float(dp.price), "discount_percent": float(dp.discount_percent),
                  "total": float(dp.total)} for dp in d.products]
        inv = Invoice(number=f"СЧ-{issued.year}-{inv_n:04d}", deal_id=d.id, company_id=d.company_id,
                      owner_id=d.owner_id, issued_at=issued, due_date=issued + timedelta(days=rnd.choice([10, 14, 30, 45])),
                      currency="RUB", vat_rate=20, items=items, amount=d.amount, paid_amount=0, status="issued",
                      created_at=utc(datetime.combine(issued, datetime.min.time())))
        db.add(inv)
        db.flush()
        days_since = (today - issued).days
        r = rnd.random()
        if days_since > 20 and r < 0.85 or days_since <= 20 and r < 0.45:
            paid_at = min(issued + timedelta(days=rnd.randint(1, 25)), today)
            db.add(Payment(invoice_id=inv.id, amount=d.amount, paid_at=paid_at, created_by=d.owner_id))
            inv.paid_amount, inv.status, inv.paid_at = d.amount, "paid", paid_at
            db.add(Activity(type="payment", title=f"Оплата по счёту {inv.number}", object_type="deal",
                            object_id=d.id, deal_id=d.id, company_id=d.company_id, user_id=d.owner_id, meta={},
                            occurred_at=utc(datetime.combine(paid_at, datetime.min.time())) + timedelta(hours=9)))
            db.add(Act(number=f"АКТ-{paid_at.year}-{inv_n:04d}", invoice_id=inv.id, deal_id=d.id,
                       company_id=d.company_id, act_date=paid_at, amount=d.amount, vat_rate=20, items=items,
                       status=rnd.choice(["signed", "signed", "sent"])))
        elif r < 0.93:
            part = (Decimal(d.amount) * Decimal("0.5")).quantize(Decimal("0.01"))
            paid_at = min(issued + timedelta(days=rnd.randint(1, 10)), today)
            db.add(Payment(invoice_id=inv.id, amount=part, paid_at=paid_at, comment="Предоплата 50%",
                           created_by=d.owner_id))
            inv.paid_amount, inv.status = part, "partially_paid"
    # ещё неоплаченные счета по сделкам на этапе «Оплата»
    pay_stage = open_stages[-1]
    for d in [x for x in open_deals if x.stage_id == pay_stage.id]:
        inv_n += 1
        issued = today - timedelta(days=rnd.randint(1, 8))
        items = [{"product_id": dp.product_id, "name": dp.name, "quantity": float(dp.quantity), "unit": dp.unit,
                  "price": float(dp.price), "discount_percent": float(dp.discount_percent),
                  "total": float(dp.total)} for dp in d.products]
        db.add(Invoice(number=f"СЧ-{issued.year}-{inv_n:04d}", deal_id=d.id, company_id=d.company_id,
                       owner_id=d.owner_id, issued_at=issued, due_date=issued + timedelta(days=rnd.choice([10, 14, 21])), currency="RUB",
                       vat_rate=20, items=items, amount=d.amount, paid_amount=0, status="issued"))

    # ---- Письма с трекингом ----
    for d in rnd.sample(deals, 25):
        ct = db.get(Contact, d.contact_id)
        sent = d.created_at + timedelta(days=2)
        if sent > now:
            continue
        db.add(EmailMessage(direction="out", status="sent", subject="Материалы по нашему проекту",
                            body="Добрый день! Направляю материалы, о которых говорили.", from_email=d.owner.email,
                            to_email=ct.email, user_id=d.owner_id, company_id=d.company_id, contact_id=ct.id,
                            deal_id=d.id, tracking_token=f"demoem{d.id}{rnd.randint(1000, 9999)}", sent_at=sent,
                            opened_at=sent + timedelta(hours=3) if rnd.random() < 0.7 else None,
                            open_count=rnd.randint(1, 4), created_at=sent))

    # ---- Прочее ----
    import hashlib

    demo_key = "crm_demo_website_key_2026"
    db.add(ApiKey(name="Сайт компании (форма обратной связи)", prefix=demo_key[:12],
                  key_hash=hashlib.sha256(demo_key.encode()).hexdigest(), created_by=users["admin"].id))
    db.add(ReportSchedule(user_id=users["head"].id, report="summary", frequency="weekly", format="pdf",
                          email=users["head"].email))
    db.add(ReportSchedule(user_id=users["head"].id, report="managers", frequency="monthly", format="xlsx",
                          email=users["head"].email))
    for u in managers + [users["head"]]:
        db.add(Notification(user_id=u.id, kind="lead", title="Новый лид", body="Заявка с сайта: ООО «Дельта Фуд»",
                            link="/leads", created_at=now - timedelta(minutes=35)))
        db.add(Notification(user_id=u.id, kind="proposal", title="Клиент открыл КП", body="Предложение просмотрено",
                            link="/proposals", created_at=now - timedelta(hours=3)))
    set_setting(db, "lead_distribution", {"mode": "round_robin", "user_ids": [], "last_index": -1})
    db.flush()
    sync_sequences(db)
    print(f"Демо-данные: {len(companies)} компаний, {len(deals)} сделок ({len(won_deals)} выиграно), "
          f"{lead_counter + 70} лидов")
    print("Пользователи (пароль demo12345): admin@demo.ru, head@demo.ru, petrov@demo.ru, kozlova@demo.ru, "
          "nikitin@demo.ru, orlova@demo.ru, marketer@demo.ru")
    print(f"API-ключ для формы сайта: {demo_key}")


def sync_sequences(db) -> None:
    """Счётчики номеров документов продолжают нумерацию уже существующих КП, счетов и актов."""
    from app.models import NumberSequence

    maxes: dict[str, int] = {}
    for model in (Proposal, Invoice, Act):
        for number in db.scalars(select(model.number)):
            prefix, _, seq = number.rpartition("-")
            if seq.isdigit():
                maxes[prefix] = max(maxes.get(prefix, 0), int(seq))
    for key, value in maxes.items():
        row = db.get(NumberSequence, key)
        if row is None:
            db.add(NumberSequence(key=key, value=value))
        else:
            row.value = max(row.value, value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="загрузить демонстрационные данные")
    parser.add_argument("--reset", action="store_true", help="очистить базу перед загрузкой")
    args = parser.parse_args()
    if args.reset:
        reset_db()
    with SessionLocal() as db:
        seed_reference(db)
        if args.demo:
            if db.scalar(select(Company.id).limit(1)) is not None:
                print("В базе уже есть данные — демо-данные не загружены (используйте --reset)")
            else:
                seed_demo(db)
        else:
            seed_admin(db)
        db.commit()


if __name__ == "__main__":
    main()
