"""Authentication helpers shared by local connector ingress routes."""

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Callable


DEFAULT_REPLAY_WINDOW_SECONDS = 300


class IngressAuthenticationError(ValueError):
    pass


@dataclass(frozen=True)
class VerifiedSignature:
    timestamp: int


def signature_for_body(secret: str, timestamp: int | str, body: bytes) -> str:
    signed = str(timestamp).encode("ascii") + b"." + body
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(
    body: bytes,
    timestamp_header: str | None,
    signature_header: str | None,
    secret: str,
    *,
    now: Callable[[], float] = time.time,
    replay_window_seconds: int = DEFAULT_REPLAY_WINDOW_SECONDS,
) -> VerifiedSignature:
    if not timestamp_header:
        raise IngressAuthenticationError("Missing timestamp")
    if not signature_header:
        raise IngressAuthenticationError("Missing signature")
    try:
        timestamp = int(timestamp_header)
    except (TypeError, ValueError) as exc:
        raise IngressAuthenticationError("Invalid timestamp") from exc

    expected = signature_for_body(secret, timestamp_header, body)
    if not hmac.compare_digest(expected, signature_header):
        raise IngressAuthenticationError("Invalid signature")
    if abs(int(now()) - timestamp) > replay_window_seconds:
        raise IngressAuthenticationError("Stale timestamp")
    return VerifiedSignature(timestamp=timestamp)
