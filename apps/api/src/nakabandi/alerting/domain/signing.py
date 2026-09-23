"""LC-6 webhook signature: hex(HMAC-SHA256(secret, timestamp + "." + rawBody)). Pure."""

from __future__ import annotations

import hashlib
import hmac

WINDOW_S = 300  # LC-6 "window 300 s"


def sign(secret: str, timestamp: str, raw_body: bytes) -> str:
    message = timestamp.encode() + b"." + raw_body
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify(secret: str, timestamp: str, raw_body: bytes, signature_hex: str) -> bool:
    return hmac.compare_digest(sign(secret, timestamp, raw_body), signature_hex)


def within_window(timestamp_s: float, now_s: float, window_s: float = WINDOW_S) -> bool:
    return abs(now_s - timestamp_s) <= window_s
