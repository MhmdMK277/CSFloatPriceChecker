/** Thin typed client over the backend REST API. */

import type {
  Alert,
  AlertEvent,
  AppStatus,
  Deal,
  DealConfig,
  HistoryResponse,
  InventoryResponse,
  ItemVariant,
  ListingsResponse,
  PortfolioResponse,
  SteamFetchResponse,
  TrackedItem,
  WatchlistDetail,
  WatchlistSummary,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!resp.ok) {
    let message = `Request failed (${resp.status})`;
    try {
      const body = await resp.json();
      message = body.error ?? body.detail ?? message;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(message, resp.status);
  }
  return resp.json() as Promise<T>;
}

const qs = (params: Record<string, string | number | boolean | null | undefined>) => {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") search.set(k, String(v));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
};

export const api = {
  status: () => request<AppStatus>("/api/status"),

  search: (q: string, limit = 12, itemType?: string) =>
    request<{ results: ItemVariant[] }>(`/api/search${qs({ q, limit, item_type: itemType })}`),

  itemDetail: (name: string) => request<ItemVariant>(`/api/items/detail${qs({ name })}`),

  listings: (params: Record<string, string | number | null | undefined>) =>
    request<ListingsResponse>(`/api/listings${qs(params)}`),

  history: (name: string, since?: string) =>
    request<HistoryResponse>(`/api/history${qs({ name, since })}`),

  tracked: () => request<{ tracked: TrackedItem[] }>("/api/tracked"),
  track: (name: string, intervalSeconds: number, filters: Record<string, unknown> = {}) =>
    request("/api/tracked", {
      method: "POST",
      body: JSON.stringify({
        market_hash_name: name,
        interval_seconds: intervalSeconds,
        filters,
      }),
    }),
  setTrackedActive: (id: number, active: boolean) =>
    request(`/api/tracked/${id}?active=${active}`, { method: "PATCH" }),
  deleteTracked: (id: number) => request(`/api/tracked/${id}`, { method: "DELETE" }),

  watchlists: () => request<{ watchlists: WatchlistSummary[] }>("/api/watchlists"),
  createWatchlist: (name: string) =>
    request<{ id: number }>("/api/watchlists", { method: "POST", body: JSON.stringify({ name }) }),
  watchlist: (id: number) => request<WatchlistDetail>(`/api/watchlists/${id}`),
  deleteWatchlist: (id: number) => request(`/api/watchlists/${id}`, { method: "DELETE" }),
  addWatchlistItem: (id: number, name: string) =>
    request(`/api/watchlists/${id}/items`, {
      method: "POST",
      body: JSON.stringify({ market_hash_name: name }),
    }),
  removeWatchlistItem: (id: number, itemId: number) =>
    request(`/api/watchlists/${id}/items/${itemId}`, { method: "DELETE" }),
  refreshWatchlist: (id: number) =>
    request<WatchlistDetail>(`/api/watchlists/${id}/refresh`, { method: "POST" }),

  alerts: () => request<{ alerts: Alert[] }>("/api/alerts"),
  createAlert: (name: string, rule: Alert["rule"]) =>
    request("/api/alerts", {
      method: "POST",
      body: JSON.stringify({ market_hash_name: name, rule }),
    }),
  setAlertActive: (id: number, active: boolean) =>
    request(`/api/alerts/${id}?active=${active}`, { method: "PATCH" }),
  deleteAlert: (id: number) => request(`/api/alerts/${id}`, { method: "DELETE" }),
  alertEvents: (limit = 100) =>
    request<{ events: AlertEvent[] }>(`/api/alerts/events?limit=${limit}`),

  deals: () => request<{ deals: Deal[] }>("/api/deals"),
  dealConfig: () => request<DealConfig>("/api/deals/config"),
  setDealConfig: (config: DealConfig) =>
    request<DealConfig>("/api/deals/config", { method: "PUT", body: JSON.stringify(config) }),

  inventoryUpload: (data: unknown) =>
    request<InventoryResponse>("/api/inventory/upload", {
      method: "POST",
      body: JSON.stringify({ data }),
    }),
  inventorySteam: (input: string) =>
    request<SteamFetchResponse>(`/api/inventory/steam${qs({ q: input })}`),
  inventoryManual: (tradable: unknown | null, tradeProtected: unknown | null) =>
    request<InventoryResponse>("/api/inventory/manual", {
      method: "POST",
      body: JSON.stringify({ tradable, trade_protected: tradeProtected }),
    }),

  portfolio: () => request<PortfolioResponse>("/api/portfolio"),
  addPortfolio: (entry: {
    market_hash_name: string;
    buy_price_cents: number;
    quantity: number;
    note?: string;
  }) => request("/api/portfolio", { method: "POST", body: JSON.stringify(entry) }),
  deletePortfolio: (id: number) => request(`/api/portfolio/${id}`, { method: "DELETE" }),

  setApiKey: (key: string) =>
    request<{ ok: boolean; stored_in: string; profile: { username?: string } }>(
      "/api/settings/api-key",
      { method: "POST", body: JSON.stringify({ key }) },
    ),
  deleteApiKey: () => request("/api/settings/api-key", { method: "DELETE" }),
  preferences: () => request<Record<string, unknown>>("/api/settings/preferences"),
  setPreferences: (prefs: Record<string, unknown>) =>
    request("/api/settings/preferences", { method: "PUT", body: JSON.stringify(prefs) }),
  refreshItemDb: () =>
    request<{ base_items: number; market_names: number }>("/api/itemdb/refresh", {
      method: "POST",
    }),
};
