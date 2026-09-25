"""Форматирование сумм и «сумма прописью» для счетов и актов."""
from decimal import ROUND_HALF_UP, Decimal

UNITS = {
    "m": ["", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"],
    "f": ["", "одна", "две", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"],
}
TEENS = ["десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать", "шестнадцать",
         "семнадцать", "восемнадцать", "девятнадцать"]
TENS = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят",
        "девяносто"]
HUNDREDS = ["", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот", "восемьсот",
            "девятьсот"]
ORDERS = [  # (формы, род)
    (("", "", ""), "m"),
    (("тысяча", "тысячи", "тысяч"), "f"),
    (("миллион", "миллиона", "миллионов"), "m"),
    (("миллиард", "миллиарда", "миллиардов"), "m"),
]
CURRENCY_FORMS = {
    "RUB": (("рубль", "рубля", "рублей"), "m", ("копейка", "копейки", "копеек"), "f"),
    "USD": (("доллар США", "доллара США", "долларов США"), "m", ("цент", "цента", "центов"), "m"),
    "EUR": (("евро", "евро", "евро"), "m", ("евроцент", "евроцента", "евроцентов"), "m"),
    "CNY": (("юань", "юаня", "юаней"), "m", ("фэнь", "фэня", "фэней"), "m"),
}
SYMBOLS = {"RUB": "₽", "USD": "$", "EUR": "€", "CNY": "¥"}


def plural(n: int, forms: tuple[str, str, str]) -> str:
    n = abs(n) % 100
    if 11 <= n <= 19:
        return forms[2]
    n %= 10
    if n == 1:
        return forms[0]
    if 2 <= n <= 4:
        return forms[1]
    return forms[2]


def _triad(n: int, gender: str) -> list[str]:
    words = [HUNDREDS[n // 100]]
    rest = n % 100
    if 10 <= rest <= 19:
        words.append(TEENS[rest - 10])
    else:
        words += [TENS[rest // 10], UNITS[gender][rest % 10]]
    return [w for w in words if w]


def number_in_words(n: int, gender: str = "m") -> str:
    if n == 0:
        return "ноль"
    parts: list[str] = []
    order = 0
    while n > 0 and order < len(ORDERS):
        triad = n % 1000
        if triad:
            forms, g = ORDERS[order]
            words = _triad(triad, gender if order == 0 else g)
            if order > 0:
                words.append(plural(triad, forms))
            parts = words + parts
        n //= 1000
        order += 1
    return " ".join(parts)


def amount_in_words(amount: Decimal | float, currency: str = "RUB") -> str:
    amount = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    whole = int(amount)
    cents = int((amount - whole) * 100)
    major, mg, minor, _ = CURRENCY_FORMS.get(currency, CURRENCY_FORMS["RUB"])
    text = f"{number_in_words(whole, mg)} {plural(whole, major)} {cents:02d} {plural(cents, minor)}"
    return text[0].upper() + text[1:]


def fmt_money(value: Decimal | float | None, currency: str | None = "RUB") -> str:
    v = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    s = f"{v:,.2f}".replace(",", " ").replace(".", ",")
    return f"{s} {SYMBOLS.get(currency or '', currency or '')}".strip()


def calc_lines(items: list[dict], vat_rate: int) -> dict:
    """Итоги по строкам документа. Цены указываются с НДС (как принято в B2B-прайсах РФ)."""
    total = Decimal("0")
    lines = []
    for i, it in enumerate(items, 1):
        qty = Decimal(str(it.get("quantity", 1)))
        price = Decimal(str(it.get("price", 0)))
        disc = Decimal(str(it.get("discount_percent", 0)))
        line_total = (qty * price * (1 - disc / 100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total += line_total
        lines.append({**it, "n": i, "total": float(line_total)})
    vat = (total * vat_rate / (100 + vat_rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if vat_rate else Decimal(0)
    return {"lines": lines, "total": total, "vat": vat}
