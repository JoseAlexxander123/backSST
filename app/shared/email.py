import smtplib
from email.mime.text import MIMEText
from app.config.settings import settings


def send_email(recipient: str, subject: str, body: str) -> None:
    """Simple SMTP sender; replace config with your provider."""
    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = settings.SMTP_FROM
    message["To"] = recipient

    # boacomment: Ajusta host/puerto/credenciales SMTP a tu proveedor real (p.ej. SES, SendGrid, Mailgun) y aplica TLS/SSL segun requerimientos.
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        if settings.SMTP_USERNAME:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD or "")
        server.sendmail(settings.SMTP_FROM, [recipient], message.as_string())
