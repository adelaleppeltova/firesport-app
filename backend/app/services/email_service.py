import logging
import os
import smtplib
from email.message import EmailMessage
from urllib.parse import quote


logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USERNAME or "no-reply@example.com")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() == "true"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
RESET_PASSWORD_PATH = os.getenv("RESET_PASSWORD_PATH", "/obnoveni-hesla")


def build_password_reset_url(token: str) -> str:
    return f"{FRONTEND_URL}{RESET_PASSWORD_PATH}?token={quote(token, safe='')}"


def send_password_reset_email(recipient_email: str, reset_token: str) -> bool:
    if not SMTP_HOST:
        logger.warning(
            "SMTP is not configured; password reset email for %s was not sent.",
            recipient_email,
        )
        return False

    reset_url = build_password_reset_url(reset_token)
    message = EmailMessage()
    message["Subject"] = "Obnoveni hesla"
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = recipient_email
    message.set_content(
        "\n".join(
            [
                "Dobry den,",
                "",
                "obdrzeli jsme zadost o obnoveni hesla k vasemu uctu.",
                "Pro nastaveni noveho hesla pouzijte tento odkaz:",
                reset_url,
                "",
                "Pokud jste o obnoveni hesla nezadali, tento email muzete ignorovat.",
            ]
        )
    )

    smtp_class = smtplib.SMTP_SSL if SMTP_USE_SSL else smtplib.SMTP
    with smtp_class(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        if not SMTP_USE_SSL and SMTP_USE_TLS:
            server.starttls()
        if SMTP_USERNAME:
            server.login(SMTP_USERNAME, SMTP_PASSWORD or "")
        server.send_message(message)

    return True
