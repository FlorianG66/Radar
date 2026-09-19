"""Email sending with two backends.

- console: prints the email as structured log (dev / tests),
- smtp: real SMTP delivery through the configured server.
"""
from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass

from app.core.config import get_settings

logger = logging.getLogger("radar.mail")


@dataclass
class EmailMessage:
    to: str
    subject: str
    html: str
    text: str


def _render_text(html: str) -> str:
    import re

    return re.sub(r"<[^>]+>", " ", html).replace("&amp;", "&").strip()


class ConsoleBackend:
    def send(self, msg: EmailMessage) -> None:
        logger.info("📧 EMAIL to=%s subject=%s", msg.to, msg.subject, extra={"ctx": {"to": msg.to, "subject": msg.subject}})


class SmtpBackend:
    def send(self, msg: EmailMessage) -> None:
        settings = get_settings()
        payload = (
            f"From: {settings.SMTP_FROM}\r\n"
            f"To: {msg.to}\r\n"
            f"Subject: {msg.subject}\r\n"
            "MIME-Version: 1.0\r\n"
            "Content-Type: text/html; charset=utf-8\r\n"
            f"\r\n{msg.html}"
        ).encode("utf-8")
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, [msg.to], payload)


def get_backend():
    settings = get_settings()
    if settings.SMTP_BACKEND == "smtp":
        return SmtpBackend()
    return ConsoleBackend()


def send_email(to: str, subject: str, html: str, text: str | None = None) -> None:
    msg = EmailMessage(to=to, subject=subject, html=html, text=text or _render_text(html))
    get_backend().send(msg)


# ---------- templates ----------
def _shell(inner_html: str, preheader: str = "Radar — alerte concurrentielle") -> str:
    return f"""<!doctype html><html><body style="margin:0;background:#f4f6f8;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
<div style="max-width:560px;margin:0 auto;padding:24px;">
  <div style="padding:8px 0 20px;color:#0f172a;font-weight:700;font-size:20px;">📡 Radar</div>
  <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:28px;color:#0f172a;">{inner_html}</div>
  <p style="color:#94a3b8;font-size:12px;margin-top:20px;">© Radar · alerte concurrentielle. Gérez vos préférences depuis votre tableau de bord.</p>
</div></body></html>"""


def template_button(text: str, url: str) -> str:
    return f'<p style="margin:24px 0;"><a href="{url}" style="background:#2563eb;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:8px;display:inline-block;">{text}</a></p>'


def html_verify_email(url: str) -> str:
    return _shell(
        "<p>Bonjour,</p>"
        "<p>Bienvenue sur Radar ! Confirmez votre adresse email pour activer votre compte :</p>"
        + template_button("Confirmer mon email", url)
        + "<p>Ce lien expire dans 24 heures. Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail.</p>"
    )


def html_password_reset(url: str) -> str:
    return _shell(
        "<p>Bonjour,</p>"
        "<p>Nous avons reçu une demande de réinitialisation de votre mot de passe :</p>"
        + template_button("Réinitialiser mon mot de passe", url)
        + "<p>Ce lien expire dans 1 heure. Ignorez cet e-mail si vous n'en avez pas fait la demande.</p>"
    )