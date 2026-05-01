from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
import keyring
from keyring.errors import KeyringError

from .paths import LOCAL_KEY_FILE


SERVICE_NAME = "VexNuvem Agent"
ACCOUNT_NAME = "master-key"


def _read_local_key(key_file: Path) -> bytes | None:
    if not key_file.exists():
        return None
    return key_file.read_text(encoding="utf-8").strip().encode("utf-8")


def _write_local_key(key_file: Path, key: bytes) -> None:
    key_file.write_text(key.decode("utf-8"), encoding="utf-8")


def get_or_create_master_key() -> bytes:
    try:
        stored = keyring.get_password(SERVICE_NAME, ACCOUNT_NAME)
        if stored:
            return stored.encode("utf-8")
    except KeyringError:
        pass

    local_key = _read_local_key(LOCAL_KEY_FILE)
    if local_key:
        return local_key

    key = Fernet.generate_key()
    try:
        keyring.set_password(SERVICE_NAME, ACCOUNT_NAME, key.decode("utf-8"))
    except KeyringError:
        pass
    _write_local_key(LOCAL_KEY_FILE, key)
    return key


_cipher = Fernet(get_or_create_master_key())


def encrypt_text(value: str) -> str:
    if not value:
        return ""
    return _cipher.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_text(value: str) -> str:
    if not value:
        return ""
    try:
        return _cipher.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return value
