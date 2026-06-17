"""
Unit Testler — encryption.py

Fernet ile şifreleme/şifre çözme doğruluğu.
"""
import pytest

from app.core.encryption import decrypt_value, encrypt_value


def test_encrypt_returns_different_string():
    plain = "sk-test-api-key-12345"
    encrypted = encrypt_value(plain)
    assert encrypted != plain


def test_encrypt_decrypt_roundtrip():
    plain = "sk-test-api-key-12345"
    encrypted = encrypt_value(plain)
    decrypted = decrypt_value(encrypted)
    assert decrypted == plain


def test_encrypt_same_input_different_ciphertext():
    """Fernet IV kullanır — aynı input farklı ciphertext üretir."""
    plain = "same-key"
    e1 = encrypt_value(plain)
    e2 = encrypt_value(plain)
    assert e1 != e2
    # Ama her ikisi de doğru decrypt olmalı
    assert decrypt_value(e1) == plain
    assert decrypt_value(e2) == plain


def test_decrypt_invalid_token_raises():
    with pytest.raises(ValueError):
        decrypt_value("not-a-valid-fernet-token")


def test_decrypt_tampered_token_raises():
    plain = "sk-test-key"
    encrypted = encrypt_value(plain)
    tampered = encrypted[:-4] + "XXXX"
    with pytest.raises(ValueError):
        decrypt_value(tampered)


def test_empty_string_roundtrip():
    encrypted = encrypt_value("")
    assert decrypt_value(encrypted) == ""


def test_long_api_key_roundtrip():
    """Gerçek API key formatına yakın uzunluk testi."""
    plain = "sk-ant-api03-" + "a" * 95
    encrypted = encrypt_value(plain)
    assert decrypt_value(encrypted) == plain
