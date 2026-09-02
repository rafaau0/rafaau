"""Armazenamento de credenciais no cofre do Windows, com fallback controlado."""
from __future__ import annotations
import os

SERVICE = "NeivaPlanner"


class SecretStorageError(RuntimeError):
    """Erro compreensível ao acessar o cofre de credenciais do sistema."""

def get_secret(key: str, legacy_value: str = "") -> str:
    if os.getenv(key): return os.environ[key]
    try:
        import keyring
        return keyring.get_password(SERVICE, key) or legacy_value
    except Exception:
        return legacy_value

def set_secret(key: str, value: str) -> None:
    try:
        import keyring
        if value:
            keyring.set_password(SERVICE, key, value)
        else:
            try:
                keyring.delete_password(SERVICE, key)
            except keyring.errors.PasswordDeleteError:
                pass
    except Exception as exc:
        raise SecretStorageError(f"Não foi possível salvar {key} no cofre do Windows: {exc}") from exc
