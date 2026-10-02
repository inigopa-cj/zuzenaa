"""Symmetric encryption for stored GitHub tokens (Fernet)."""

import base64
import hashlib

from cryptography.fernet import Fernet

from zuzenaa.config import settings


class TokenCipher:
    def __init__(self, secret: str) -> None:
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        self._fernet = Fernet(key)

    def encrypt(self, token: str) -> str:
        return self._fernet.encrypt(token.encode()).decode()

    def decrypt(self, blob: str) -> str:
        return self._fernet.decrypt(blob.encode()).decode()


cipher = TokenCipher(settings.secret_key.get_secret_value())
