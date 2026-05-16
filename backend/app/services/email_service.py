import smtplib
import ssl
from email.message import EmailMessage

from app.core.settings import get_settings


class EmailDeliveryError(RuntimeError):
    pass


def smtp_is_configured() -> bool:
    settings = get_settings()
    return bool(settings.smtp_host and settings.smtp_username and settings.smtp_password)


def send_verification_code(email: str, code: str, expires_minutes: int) -> None:
    settings = get_settings()
    sender = settings.smtp_from or settings.smtp_username
    if not smtp_is_configured() or not sender:
        raise EmailDeliveryError("SMTP is not configured")

    message = EmailMessage()
    message["Subject"] = f"{settings.app_name} verification code"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        "\n".join(
            [
                f"Your {settings.app_name} verification code is:",
                "",
                code,
                "",
                f"This code expires in {expires_minutes} minutes.",
                "If you did not request this code, you can ignore this email.",
            ]
        )
    )

    try:
        if settings.smtp_port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context, timeout=20) as smtp:
                smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
            return

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            smtp.ehlo()
            if settings.smtp_port == 587:
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError("Verification email could not be sent") from exc
