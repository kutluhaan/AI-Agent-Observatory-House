"""
Email Service — Resend ile transactional email.

M4'te kullanılan email'ler:
- Email verification linki

M5'te eklenecek:
- Org davet emaili

Resend seçildi çünkü:
- Python SDK basit
- Ücretsiz plan 3000 email/ay
- Delivery rate yüksek
- .env.example'da RESEND_API_KEY zaten tanımlı
"""
import asyncio
from typing import Any

import structlog

from app.core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


async def _send_resend_email(payload: dict[str, Any]) -> None:
    """Resend SDK sync çağrısını thread pool'da çalıştırır — event loop bloklanmaz."""
    import resend

    resend.api_key = settings.resend_api_key
    await asyncio.to_thread(resend.Emails.send, payload)


async def send_verification_email(email: str, raw_token: str) -> bool:
    """
    Email doğrulama linki gönderir.

    Returns:
        True → email gönderildi
        False → hata oluştu (log yazıldı, exception fırlatılmaz)

    Neden exception fırlatmıyor?
    Register veya resend-verification endpoint'leri email gönderimi
    başarısız olsa bile 201/200 döner. Kullanıcı "link gönderildi"
    mesajı görür, tekrar deneyebilir. Email hatası kritik path değil.
    """
    verify_url = f"{settings.frontend_url}/verify-email?token={raw_token}"

    # Dev kolaylığı: Resend test modu (sadece hesap sahibine gönderir) email'i
    # bloklasa bile linki log'dan alabilmek için yaz. Prod'da yazılmaz.
    if settings.is_development:
        logger.info("email.dev_link", kind="verify", to=email, url=verify_url)

    try:
        await _send_resend_email({
            "from": settings.email_from,
            "to": email,
            "subject": "Verify your AI Agent Observatory account",
            "html": _verification_email_html(verify_url),
        })

        logger.info("email.verification_sent", email=email)
        return True

    except Exception as e:
        logger.error("email.send_failed", email=email, error=str(e))
        return False


async def send_invitation_email(
    email: str,
    org_name: str,
    invited_by: str,
    raw_token: str,
    role: str,
) -> bool:
    """Org davet emaili gönderir. Hata olsa da exception fırlatmaz (log + False)."""
    invite_url = f"{settings.frontend_url}/invitations/{raw_token}/accept"

    if settings.is_development:
        logger.info("email.dev_link", kind="invite", to=email, url=invite_url)

    try:
        await _send_resend_email({
            "from": settings.email_from,
            "to": email,
            "subject": f"You've been invited to join {org_name} on AI Agent Observatory",
            "html": _invitation_email_html(invite_url, org_name, invited_by, role),
        })

        logger.info("email.invitation_sent", email=email, org=org_name)
        return True

    except Exception as e:
        logger.error("email.send_failed", email=email, error=str(e))
        return False


async def send_password_reset_email(email: str, raw_token: str) -> bool:
    """
    Şifre sıfırlama linki gönderir.
    M4 kapsamında tanımlandı — forgot-password endpoint'i M4'te yok
    ama altyapı hazır, M4 sonrası eklenebilir.
    """
    reset_url = f"{settings.frontend_url}/reset-password?token={raw_token}"

    if settings.is_development:
        logger.info("email.dev_link", kind="reset", to=email, url=reset_url)

    try:
        await _send_resend_email({
            "from": settings.email_from,
            "to": email,
            "subject": "Reset your AI Agent Observatory password",
            "html": _password_reset_email_html(reset_url),
        })

        logger.info("email.reset_sent", email=email)
        return True

    except Exception as e:
        logger.error("email.send_failed", email=email, error=str(e))
        return False


# ─── Email Templates ──────────────────────────────────────

def _verification_email_html(verify_url: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
             background: #0f172a; color: #e2e8f0; margin: 0; padding: 40px 20px;">
  <div style="max-width: 480px; margin: 0 auto;">
    <h1 style="font-size: 20px; font-weight: 600; color: #f8fafc; margin-bottom: 8px;">
      Verify your email
    </h1>
    <p style="color: #94a3b8; margin-bottom: 32px; line-height: 1.6;">
      Click the button below to verify your AI Agent Observatory account.
      This link expires in 24 hours.
    </p>
    <a href="{verify_url}"
       style="display: inline-block; background: #6366f1; color: #fff;
              padding: 12px 24px; border-radius: 8px; text-decoration: none;
              font-weight: 500; font-size: 14px;">
      Verify Email
    </a>
    <p style="color: #475569; font-size: 12px; margin-top: 32px;">
      If you didn't create an account, you can safely ignore this email.
    </p>
    <p style="color: #334155; font-size: 11px; margin-top: 8px; word-break: break-all;">
      Or copy this link: {verify_url}
    </p>
  </div>
</body>
</html>
"""


def _invitation_email_html(invite_url: str, org_name: str, invited_by: str, role: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
             background: #0f172a; color: #e2e8f0; margin: 0; padding: 40px 20px;">
  <div style="max-width: 480px; margin: 0 auto;">
    <h1 style="font-size: 20px; font-weight: 600; color: #f8fafc; margin-bottom: 8px;">
      You've been invited
    </h1>
    <p style="color: #94a3b8; margin-bottom: 8px; line-height: 1.6;">
      <strong style="color: #e2e8f0;">{invited_by}</strong> has invited you to join
      <strong style="color: #e2e8f0;">{org_name}</strong> as a <strong style="color: #e2e8f0;">{role}</strong>.
    </p>
    <p style="color: #94a3b8; margin-bottom: 32px; line-height: 1.6;">
      This invitation expires in 7 days.
    </p>
    <a href="{invite_url}"
       style="display: inline-block; background: #6366f1; color: #fff;
              padding: 12px 24px; border-radius: 8px; text-decoration: none;
              font-weight: 500; font-size: 14px;">
      Accept Invitation
    </a>
    <p style="color: #475569; font-size: 12px; margin-top: 32px;">
      If you didn't expect this invitation, you can safely ignore this email.
    </p>
    <p style="color: #334155; font-size: 11px; margin-top: 8px; word-break: break-all;">
      Or copy this link: {invite_url}
    </p>
  </div>
</body>
</html>
"""


def _password_reset_email_html(reset_url: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
             background: #0f172a; color: #e2e8f0; margin: 0; padding: 40px 20px;">
  <div style="max-width: 480px; margin: 0 auto;">
    <h1 style="font-size: 20px; font-weight: 600; color: #f8fafc; margin-bottom: 8px;">
      Reset your password
    </h1>
    <p style="color: #94a3b8; margin-bottom: 32px; line-height: 1.6;">
      Click the button below to reset your password.
      This link expires in 30 minutes.
    </p>
    <a href="{reset_url}"
       style="display: inline-block; background: #6366f1; color: #fff;
              padding: 12px 24px; border-radius: 8px; text-decoration: none;
              font-weight: 500; font-size: 14px;">
      Reset Password
    </a>
    <p style="color: #475569; font-size: 12px; margin-top: 32px;">
      If you didn't request a password reset, you can safely ignore this email.
    </p>
    <p style="color: #334155; font-size: 11px; margin-top: 8px; word-break: break-all;">
      Or copy this link: {reset_url}
    </p>
  </div>
</body>
</html>
"""
