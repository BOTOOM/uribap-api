import smtplib
from email.message import EmailMessage

from uribap_api.config import Settings
from uribap_api.infrastructure.persistence.household_models import EmailOutboxEntry


def send_outbox_entry(
    settings: Settings, entry: EmailOutboxEntry, *, link: str | None = None
) -> None:
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = entry.recipient_email
    message["Subject"] = "Uribap household invitation"
    body = str(entry.template_data.get("body", "You have a Uribap household invitation."))
    if link:
        body = f"{body}\n\n{link}"
    message.set_content(body)
    with smtplib.SMTP(
        settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds
    ) as client:
        if settings.smtp_use_tls:
            client.starttls()
        if settings.smtp_username and settings.smtp_password:
            client.login(settings.smtp_username, settings.smtp_password)
        client.send_message(message)
