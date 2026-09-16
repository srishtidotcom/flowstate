# OpenClaw → Flowstate inbound bridge

Phase 2A accepts inbound WhatsApp text only. It does not send WhatsApp
messages, reply autonomously, or process media. The inspected local OpenClaw
and `@openclaw/whatsapp` version is `2026.9.4`. The plugin uses the typed
`api.on("message_received", handler, { timeoutMs: 2000 })` API. Do not replace
it with the separate `api.registerHook` internal-hook API.

## Required environment

Set the same non-empty secret for the OpenClaw Gateway process and the Flowstate
API process. Do not add it to a tracked file. `FLOWSTATE_TEAM_ID` and
`FLOWSTATE_INGRESS_URL` are consumed by the plugin.

```bash
export FLOWSTATE_BRIDGE_SECRET="$(openssl rand -hex 32)"
export FLOWSTATE_TEAM_ID='team-demo'
export FLOWSTATE_INGRESS_URL='http://127.0.0.1:8001/integrations/openclaw/events'
```

`FLOWSTATE_INGRESS_URL` is optional and defaults to the value shown. The plugin
rejects non-loopback or non-HTTP endpoints. The Flowstate route also rejects
non-loopback clients.

## OpenClaw configuration change (manual)

Review and merge this exact shape into the existing OpenClaw configuration.
This repository does not rewrite `~/.openclaw/openclaw.json`:

```json
{
  "channels": {
    "whatsapp": {
      "pluginHooks": {
        "messageReceived": true
      }
    }
  },
  "plugins": {
    "entries": {
      "flowstate-bridge": {
        "enabled": true
      }
    }
  }
}
```

Install and inspect the trusted local plugin from the repository root:

```bash
openclaw plugins install --link ./backend/infrastructure/connectors/openclaw/plugin --force
openclaw plugins enable flowstate-bridge
openclaw plugins inspect flowstate-bridge --runtime --json
openclaw gateway restart
openclaw logs --follow
```

Ensure the Gateway service receives the three environment variables above;
an interactive shell export does not automatically modify an already-installed
systemd or launchd service environment.

## Start Flowstate

Keep the API bound to loopback for this local demo:

```bash
docker compose -f docker/docker-compose.yml up -d postgres chromadb redis
.venv/bin/python -m alembic upgrade head
.venv/bin/uvicorn backend.api.main:app --host 127.0.0.1 --port 8001
```

In another terminal with the same database and Redis environment:

```bash
.venv/bin/python -m backend.worker
```

## Smoke test and live WhatsApp test

The local fixture sender signs the timestamp plus the exact compact JSON body:

```bash
.venv/bin/python scripts/smoke_openclaw_ingress.py
```

It prints `event_id`, `job_id`, `status`, and `duplicate`. Sending it again
returns the original identifiers with `duplicate: true`.

For the live path, send one text message from an allowed WhatsApp sender to the
connected OpenClaw account, then watch `openclaw logs --follow`. The plugin logs
only delivery status, message ID, and the returned job ID, never message text or
the secret.

Use the returned job ID (or obtain it from the Flowstate API/logs) to inspect
processing and results:

```bash
curl --get 'http://127.0.0.1:8001/jobs/JOB_ID' --data-urlencode 'team_id=team-demo'
curl --get 'http://127.0.0.1:8001/jobs/JOB_ID/results' --data-urlencode 'team_id=team-demo'
```

The results endpoint returns the canonical Event, Commitment, Tasks, and graph
edges after the worker marks the job completed.
