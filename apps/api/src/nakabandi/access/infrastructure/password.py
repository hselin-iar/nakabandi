"""Argon2PasswordHasher (DOC 2 §2.2: "passwords hashed with argon2"). argon2-cffi is the
standard Python binding for the algorithm DOC 2 names; no library choice was left open here."""

from __future__ import annotations

from argon2 import PasswordHasher as Argon2
from argon2.exceptions import VerifyMismatchError


class Argon2PasswordHasher:
    def __init__(self) -> None:
        self._argon2 = Argon2()

    def hash(self, password: str) -> str:
        return self._argon2.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            return self._argon2.verify(password_hash, password)
        except VerifyMismatchError:
            return False
