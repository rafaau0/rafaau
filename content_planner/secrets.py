"""Armazenamento de credenciais no cofre do Windows, com fallback controlado."""
from __future__ import annotations
import os

SERVICE = "NeivaPlanner"

def get_secret(key: str, legacy_value: str = "") -> str:
    if os.getenv(key): return os.environ[key]
    try:
        import keyring
        return keyring.get_password(SERVICE, key) or legacy_value
    except Exception:
        return legacy_value

def set_secret(key: str, value: str) -> None:
    import keyring
    keyring.set_password(SERVICE, key, value)
