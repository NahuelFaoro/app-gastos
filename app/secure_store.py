from __future__ import annotations

"""Persistencia de secretos del sistema separada de clientes HTTP.

Importar/leer credenciales no debe cargar ``requests`` ni inicializar el cliente
de Mercado Pago durante el arranque de la interfaz.
"""

import keyring

SERVICE_NAME = "AppGastos-MercadoPago"
TOKEN_USER = "access_token"


def save_token(token: str) -> None:
    token = (token or "").strip()
    if not token:
        raise ValueError("El Access Token está vacío.")
    keyring.set_password(SERVICE_NAME, TOKEN_USER, token)


def get_token() -> str | None:
    try:
        return keyring.get_password(SERVICE_NAME, TOKEN_USER)
    except Exception:
        return None


def delete_token() -> None:
    try:
        keyring.delete_password(SERVICE_NAME, TOKEN_USER)
    except Exception:
        pass
