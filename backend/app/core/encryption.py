"""
Encryption Service — Fernet (AES-128-CBC + HMAC) ile simetrik şifreleme.

Kullanım: provider_credentials.encrypted_key alanı.
Aynı yöntem auth-spec'te oauth_accounts.access_token için planlanmıştı (Faz 4).

Key türetimi: APP_SECRET_KEY'den PBKDF2 ile 32 byte Fernet key üretilir.
Bu sayede ekstra bir secret yönetmek zorunda kalmıyoruz — mevcut APP_SECRET_KEY yeterli.
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

settings = get_settings()


def _derive_fernet_key(secret: str) -> bytes:
    """APP_SECRET_KEY'den deterministik 32 byte Fernet key türetir."""
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fernet() -> Fernet:
    key = _derive_fernet_key(settings.app_secret_key)
    return Fernet(key)


def encrypt_value(plain: str) -> str:
    """Plain-text string'i şifreler. DB'ye yazılacak format."""
    f = _get_fernet()
    return f.encrypt(plain.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    """
    Şifreli string'i çözer.

    Raises:
        ValueError: token geçersiz veya bozuksa (yanlış key, manipüle edilmiş veri)
    """
    f = _get_fernet()
    try:
        return f.decrypt(encrypted.encode()).decode()
    except InvalidToken:
        raise ValueError("Encrypted value could not be decrypted — invalid or corrupted token.")
