import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { createHmac } from "node:crypto";

const DEFAULT_INGRESS_URL = "http://127.0.0.1:8001/integrations/openclaw/events";
const HTTP_TIMEOUT_MS = 1500;

export default definePluginEntry({
  id: "flowstate-bridge",
  name: "Flowstate inbound bridge",
  description: "Forwards accepted inbound WhatsApp text hooks to local Flowstate.",
  register(api) {
    const ingressUrl = process.env.FLOWSTATE_INGRESS_URL || DEFAULT_INGRESS_URL;
    const secret = process.env.FLOWSTATE_BRIDGE_SECRET;
    const teamId = process.env.FLOWSTATE_TEAM_ID;

    if (!secret || !teamId) {
      api.logger.warn(
        "Flowstate bridge disabled: FLOWSTATE_BRIDGE_SECRET and FLOWSTATE_TEAM_ID are required",
      );
      return;
    }

    const parsedUrl = (() => {
      try {
        const candidate = new URL(ingressUrl);
        if (
          candidate.protocol !== "http:" ||
          !["127.0.0.1", "::1", "localhost"].includes(candidate.hostname)
        ) {
          throw new Error("endpoint must use loopback HTTP");
        }
        return candidate;
      } catch {
        api.logger.warn("Flowstate bridge disabled: invalid local ingress URL");
        return null;
      }
    })();
    if (!parsedUrl) {
      return;
    }

    api.on(
      "message_received",
      async (event, ctx) => {
        const metadata = event.metadata || {};
        const fromMe = [
          metadata.fromMe,
          metadata.from_me,
          metadata.isSelf,
          metadata.senderIsSelf,
        ].some((value) => value === true || value === "true");
        if (ctx.channelId !== "whatsapp" || fromMe || !event.content?.trim()) {
          return;
        }

        const messageId =
          event.messageId || event.providerUpdate?.messageId || event.providerUpdate?.id;
        const accountId = ctx.accountId;
        const sender = event.senderId || ctx.senderId || event.from;
        const conversationId = ctx.conversationId || event.from;
        if (!messageId || !accountId || !sender || !conversationId) {
          api.logger.warn(
            `Flowstate bridge skipped inbound WhatsApp hook: required identity missing (messageId=${messageId || "missing"})`,
          );
          return;
        }

        const payload = {
          connector: "openclaw",
          channel: "whatsapp",
          account_id: accountId,
          team_id: teamId,
          sender,
          conversation_id: conversationId,
          timestamp:
            event.timestamp || event.providerUpdate?.messageTimestamp || Date.now(),
          text: event.content,
          message_id: messageId,
          from_me: false,
          metadata: {
            thread_id: event.threadId,
            session_key: event.sessionKey || ctx.sessionKey,
            run_id: event.runId || ctx.runId,
            provider_update: event.providerUpdate,
          },
          openclaw_hook: { event, context: ctx },
        };
        try {
          const body = JSON.stringify(payload);
          const timestamp = Math.floor(Date.now() / 1000).toString();
          const signature = `sha256=${createHmac("sha256", secret)
            .update(`${timestamp}.${body}`, "utf8")
            .digest("hex")}`;
          const response = await fetch(parsedUrl, {
            method: "POST",
            headers: {
              "content-type": "application/json",
              "x-flowstate-timestamp": timestamp,
              "x-flowstate-signature": signature,
            },
            body,
            signal: AbortSignal.timeout(HTTP_TIMEOUT_MS),
          });
          if (!response.ok) {
            api.logger.warn(
              `Flowstate bridge delivery failed (messageId=${messageId}, status=${response.status})`,
            );
            return;
          }
          const receipt = await response.json().catch(() => ({}));
          const jobId = typeof receipt.job_id === "string" ? receipt.job_id : "unknown";
          api.logger.info(
            `Flowstate bridge delivered inbound event (messageId=${messageId}, jobId=${jobId}, status=${response.status})`,
          );
        } catch (error) {
          api.logger.warn(
            `Flowstate bridge delivery failed (messageId=${messageId}, error=${error instanceof Error ? error.name : "unknown"})`,
          );
        }
      },
      { timeoutMs: 2000 },
    );
  },
});
