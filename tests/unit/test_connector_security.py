import hmac

import pytest

from backend.infrastructure.connectors.security import (
    IngressAuthenticationError,
    signature_for_body,
    verify_signature,
)


def test_hmac_verification_covers_timestamp_and_exact_body():
    body = b'{"text":"exact bytes"}\n'
    signature = signature_for_body("secret", "1000", body)

    assert verify_signature(body, "1000", signature, "secret", now=lambda: 1001).timestamp == 1000
    with pytest.raises(IngressAuthenticationError, match="Invalid signature"):
        verify_signature(body.rstrip(), "1000", signature, "secret", now=lambda: 1001)


def test_stale_timestamp_is_rejected():
    signature = signature_for_body("secret", "1000", b"{}")
    with pytest.raises(IngressAuthenticationError, match="Stale timestamp"):
        verify_signature(b"{}", "1000", signature, "secret", now=lambda: 1301)


def test_invalid_signature_uses_constant_time_comparison(monkeypatch):
    observed = []
    original = hmac.compare_digest

    def recording_compare(left, right):
        observed.append((left, right))
        return original(left, right)

    monkeypatch.setattr(hmac, "compare_digest", recording_compare)
    with pytest.raises(IngressAuthenticationError, match="Invalid signature"):
        verify_signature(b"{}", "1000", "sha256=bad", "secret", now=lambda: 1000)
    assert len(observed) == 1


@pytest.mark.parametrize("timestamp,signature", [(None, "value"), ("1000", None)])
def test_missing_authentication_headers_are_rejected(timestamp, signature):
    with pytest.raises(IngressAuthenticationError):
        verify_signature(b"{}", timestamp, signature, "secret", now=lambda: 1000)
