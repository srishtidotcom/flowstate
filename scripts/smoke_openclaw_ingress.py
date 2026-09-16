"""Send the synthetic OpenClaw fixture with the production HMAC contract."""

import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "openclaw_whatsapp_event.json"
DEFAULT_URL = "http://127.0.0.1:8001/integrations/openclaw/events"


def main() -> int:
    secret = os.getenv("FLOWSTATE_BRIDGE_SECRET")
    if not secret:
        print("FLOWSTATE_BRIDGE_SECRET is required", file=sys.stderr)
        return 2
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if os.getenv("FLOWSTATE_TEAM_ID"):
        payload["team_id"] = os.environ["FLOWSTATE_TEAM_ID"]
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    signed = timestamp.encode("ascii") + b"." + body
    signature = "sha256=" + hmac.new(
        secret.encode("utf-8"), signed, hashlib.sha256
    ).hexdigest()
    request = Request(
        os.getenv("FLOWSTATE_INGRESS_URL", DEFAULT_URL),
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Flowstate-Timestamp": timestamp,
            "X-Flowstate-Signature": signature,
        },
    )
    try:
        with urlopen(request, timeout=3) as response:
            print(response.read().decode("utf-8"))
            return 0
    except HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode('utf-8')}", file=sys.stderr)
    except URLError as exc:
        print(f"Ingress request failed: {exc.reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
