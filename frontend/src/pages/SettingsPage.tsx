/** Settings: API key, item database, notifications, tracked items. */

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import { useToasts } from "../components/Toasts";
import { intervalLabel, timeAgo } from "../format";
import type { AppStatus, TrackedItem } from "../types";

export function SettingsPage({ onStatusChange }: { onStatusChange: () => void }) {
  const { push } = useToasts();
  const [status, setStatus] = useState<AppStatus | null>(null);
  const [key, setKey] = useState("");
  const [webhook, setWebhook] = useState("");
  const [tracked, setTracked] = useState<TrackedItem[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [s, prefs, t] = await Promise.all([
      api.status(),
      api.preferences(),
      api.tracked(),
    ]);
    setStatus(s);
    setWebhook((prefs.discord_webhook_url as string) ?? "");
    setTracked(t.tracked);
  }, []);

  useEffect(() => {
    load().catch(() => {});
  }, [load]);

  const saveKey = async () => {
    setBusy("key");
    try {
      const resp = await api.setApiKey(key.trim());
      push({
        kind: "info",
        title: "API key",
        body: `Validated as ${resp.profile?.username ?? "CSFloat user"} — stored in ${resp.stored_in === "keychain" ? "the OS keychain" : "a local file"}.`,
      });
      setKey("");
      await load();
      onStatusChange();
    } catch (err) {
      push({
        kind: "error",
        title: "API key",
        body: err instanceof ApiError ? err.message : "Validation failed.",
      });
    } finally {
      setBusy(null);
    }
  };

  const refreshDb = async () => {
    setBusy("db");
    try {
      const stats = await api.refreshItemDb();
      push({
        kind: "info",
        title: "Item database",
        body: `Refreshed: ${stats.market_names.toLocaleString()} market names from ${stats.base_items.toLocaleString()} base items.`,
      });
      await load();
      onStatusChange();
    } catch (err) {
      push({
        kind: "error",
        title: "Item database",
        body: err instanceof ApiError ? err.message : "Refresh failed.",
      });
    } finally {
      setBusy(null);
    }
  };

  const saveWebhook = async () => {
    setBusy("webhook");
    try {
      await api.setPreferences({ discord_webhook_url: webhook.trim() || null });
      push({ kind: "info", title: "Notifications", body: webhook ? "Discord webhook saved." : "Discord webhook cleared." });
    } catch {
      push({ kind: "error", title: "Notifications", body: "Could not save the webhook." });
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="stack fade-in">
      <div className="page-head">
        <div>
          <h1>Settings</h1>
          <p>Key, catalog, notifications and background tracking.</p>
        </div>
      </div>

      <div className="grid-2">
        <section className="panel stack" aria-labelledby="s-key">
          <h2 id="s-key">CSFloat API key</h2>
          <p className="small muted">
            Get one at <strong>csfloat.com → Profile → Developer</strong>. The key is validated
            against CSFloat before being stored in{" "}
            {status?.api_key_storage === "keychain" ? "your OS keychain" : "a local file"} — it
            never leaves this machine.
          </p>
          <div className="row">
            <input
              type="password"
              placeholder={status?.api_key_set ? "Key is set — paste to replace" : "Paste your API key"}
              value={key}
              onChange={(e) => setKey(e.target.value)}
              style={{ flex: 1 }}
              autoComplete="off"
            />
            <button
              className="btn primary"
              onClick={saveKey}
              disabled={key.trim().length < 8 || busy === "key"}
              data-state={busy === "key" ? "loading" : undefined}
            >
              {busy === "key" ? "Validating…" : "Save key"}
            </button>
          </div>
          {status?.api_key_set && (
            <button
              className="btn ghost danger sm"
              style={{ alignSelf: "start" }}
              onClick={async () => {
                await api.deleteApiKey();
                await load();
                onStatusChange();
              }}
            >
              Remove stored key
            </button>
          )}
        </section>

        <section className="panel stack" aria-labelledby="s-db">
          <h2 id="s-db">Item database</h2>
          {status && (
            <p className="small muted">
              <span className="num">{status.itemdb.market_names.toLocaleString()}</span> market
              names from <span className="num">{status.itemdb.base_items.toLocaleString()}</span>{" "}
              base items · updated{" "}
              {status.itemdb.generated_at ? timeAgo(status.itemdb.generated_at) : "never"}
              {status.itemdb.stale && (
                <span className="badge down" style={{ marginLeft: 8 }}>
                  stale
                </span>
              )}
            </p>
          )}
          <p className="small muted">
            Rebuilt from CSFloat’s public schema — new skins, cases and charms appear after a
            refresh. Auto-refreshes when older than 7 days.
          </p>
          <button
            className="btn"
            style={{ alignSelf: "start" }}
            onClick={refreshDb}
            disabled={busy === "db"}
            data-state={busy === "db" ? "loading" : undefined}
          >
            {busy === "db" ? "Refreshing…" : "Refresh item database"}
          </button>
        </section>

        <section className="panel stack" aria-labelledby="s-notif">
          <h2 id="s-notif">Discord notifications</h2>
          <p className="small muted">
            Alerts and deals post to this webhook. Leave blank for in-app toasts only.
          </p>
          <div className="row">
            <input
              type="url"
              placeholder="https://discord.com/api/webhooks/…"
              value={webhook}
              onChange={(e) => setWebhook(e.target.value)}
              style={{ flex: 1 }}
            />
            <button
              className="btn"
              onClick={saveWebhook}
              disabled={busy === "webhook"}
              data-state={busy === "webhook" ? "loading" : undefined}
            >
              Save
            </button>
          </div>
        </section>

        <section className="panel stack" aria-labelledby="s-tracked">
          <h2 id="s-tracked">Background tracking</h2>
          {tracked.length === 0 ? (
            <p className="small muted">
              Nothing tracked yet — open any item page and hit “Track price”.
            </p>
          ) : (
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Item</th>
                    <th className="right">Every</th>
                    <th className="right">Last run</th>
                    <th aria-label="actions" />
                  </tr>
                </thead>
                <tbody>
                  {tracked.map((t) => (
                    <tr key={t.id}>
                      <td style={{ overflowWrap: "anywhere" }}>{t.market_hash_name}</td>
                      <td className="right num">{intervalLabel(t.interval_seconds)}</td>
                      <td className="right xsmall muted num">{timeAgo(t.last_run_at)}</td>
                      <td className="right">
                        <div className="row" style={{ justifyContent: "flex-end", gap: 4 }}>
                          <button
                            className="btn sm ghost"
                            onClick={async () => {
                              await api.setTrackedActive(t.id, !t.active);
                              await load();
                            }}
                          >
                            {t.active ? "Pause" : "Resume"}
                          </button>
                          <button
                            className="btn sm ghost danger"
                            onClick={async () => {
                              await api.deleteTracked(t.id);
                              await load();
                            }}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
