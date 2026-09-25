"""Отправка писем через SMTP и разбор входящей почты через IMAP."""
import email
import imaplib
import logging
import smtplib
from email.header import decode_header, make_header
from email.message import EmailMessage as MimeMessage
from email.utils import make_msgid, parseaddr

from app.core.config import settings

log = logging.getLogger(__name__)


def tracking_pixel(token: str) -> str:
    url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/api/v1/t/{token}.gif"
    return f'<img src="{url}" width="1" height="1" alt="" style="display:none">'


def text_to_html(text: str) -> str:
    from html import escape

    return "<br>".join(escape(line) for line in text.splitlines())


def send_email(
    to: str,
    subject: str,
    html: str,
    *,
    text: str | None = None,
    attachments: list[tuple[str, bytes, str]] | None = None,
    reply_to: str | None = None,
) -> str:
    """Возвращает Message-ID отправленного письма."""
    msg = MimeMessage()
    msg["From"] = settings.MAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg_id = make_msgid(domain="crm.local")
    msg["Message-ID"] = msg_id
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text or "Письмо в формате HTML")
    msg.add_alternative(html, subtype="html")
    for name, data, ctype in attachments or []:
        maintype, _, subtype = (ctype or "application/octet-stream").partition("/")
        msg.add_attachment(data, maintype=maintype, subtype=subtype or "octet-stream", filename=name)

    smtp_cls = smtplib.SMTP_SSL if settings.SMTP_SSL else smtplib.SMTP
    with smtp_cls(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
        if settings.SMTP_STARTTLS:
            smtp.starttls()
        if settings.SMTP_USER:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)
    return msg_id


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _body_text(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition")):
                payload = part.get_payload(decode=True) or b""
                return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                import re

                payload = part.get_payload(decode=True) or b""
                html = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                return re.sub(r"<[^>]+>", " ", html)
        return ""
    payload = msg.get_payload(decode=True) or b""
    return payload.decode(msg.get_content_charset() or "utf-8", errors="replace")


def fetch_unseen() -> list[dict]:
    """Забирает непрочитанные письма из почтового ящика (IMAP)."""
    if not settings.IMAP_ENABLED or not settings.IMAP_HOST:
        return []
    result = []
    box = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
    try:
        box.login(settings.IMAP_USER, settings.IMAP_PASSWORD)
        box.select(settings.IMAP_FOLDER)
        _, data = box.search(None, "UNSEEN")
        for num in data[0].split()[:50]:
            _, raw = box.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(raw[0][1])
            name, addr = parseaddr(_decode(msg.get("From")))
            result.append({
                "from_name": name, "from_email": addr.lower(), "subject": _decode(msg.get("Subject")),
                "body": _body_text(msg)[:20000], "message_id": msg.get("Message-ID"),
                "in_reply_to": msg.get("In-Reply-To"),
            })
            box.store(num, "+FLAGS", "\\Seen")
    finally:
        try:
            box.logout()
        except Exception:
            log.exception("IMAP logout failed")
    return result
