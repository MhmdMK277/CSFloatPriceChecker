/** Live event stream from the backend WebSocket, with auto-reconnect. */

import { useEffect, useRef } from "react";
import type { LiveEvent } from "./types";

export function useLiveEvents(onEvent: (event: LiveEvent) => void): void {
  const handler = useRef(onEvent);
  handler.current = onEvent;

  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;
    let retry = 1000;
    let pingTimer: ReturnType<typeof setInterval> | undefined;

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/api/ws`);
      ws.onopen = () => {
        retry = 1000;
        pingTimer = setInterval(() => ws?.readyState === 1 && ws.send("ping"), 25000);
      };
      ws.onmessage = (msg) => {
        try {
          handler.current(JSON.parse(msg.data) as LiveEvent);
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        clearInterval(pingTimer);
        if (!closed) {
          setTimeout(connect, retry);
          retry = Math.min(retry * 2, 30000);
        }
      };
    };

    connect();
    return () => {
      closed = true;
      clearInterval(pingTimer);
      ws?.close();
    };
  }, []);
}
