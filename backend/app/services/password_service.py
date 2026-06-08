"""
Password Service — Argon2id hash ve verify.

Argon2id seçildi çünkü:
- OWASP ve NIST tarafından önerilen memory-hard algoritma
- Brute force ve GPU saldırılarına karşı dayanıklı
- Bcrypt'ten daha modern — 2024 industry standard
"""
import re

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

from app.core.responses import AppError

# OWASP önerilen parametreler
_hasher = PasswordHasher(
    time_cost=2,        # iterasyon sayısı
    memory_cost=65536,  # 64MB RAM — GPU parallelizasyonunu zorlaştırır
    parallelism=2,      # thread sayısı
    hash_len=32,
    salt_len=16,
)

_PASSWORD_REGEX = re.compile(r"^(?=.*[A-Z])(?=.*\d).{8,}$")


def hash_password(password: str) -> str:
    """Plain-text şifreyi Argon2id ile hash'ler."""
    validate_password_strength(password)
    return _hasher.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Plain-text şifreyi hash ile karşılaştırır.
    Yanlış şifrede False döner — exception fırlatmaz.
    """
    try:
        return _hasher.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError):
        return False


def validate_password_strength(password: str) -> None:
    """
    Şifre kurallarını kontrol eder.
    Hata varsa AppError fırlatır — endpoint'te catch edilir.
    Kurallar: min 8 karakter, en az 1 büyük harf, 1 rakam.
    """
    if not _PASSWORD_REGEX.match(password):
        raise AppError(
            code="PASSWORD_TOO_WEAK",
            message="Password must be at least 8 characters and contain at least one uppercase letter and one number.",
            status_code=422,
        )
