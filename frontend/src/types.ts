/** API payload types mirroring the FastAPI backend. */

export interface ItemVariant {
  market_hash_name: string;
  base_name: string;
  item_type: string;
  wear: string | null;
  category: "normal" | "stattrak" | "souvenir";
  def_index: number | null;
  paint_index: number | null;
  rarity: number | null;
  rarity_name?: string | null;
  collections: string[];
  collection_names?: string[];
  min_float: number | null;
  max_float: number | null;
  phase: string | null;
  image: string | null;
  reference_price_cents: number | null;
  reference_volume: number | null;
}

export interface ListingSticker {
  name: string | null;
  slot: number | null;
  wear: number | null;
  icon_url: string | null;
  reference_price_cents: number | null;
}

export interface Listing {
  id: string;
  created_at: string | null;
  type: "buy_now" | "auction";
  price_cents: number;
  price_usd: number;
  market_hash_name: string;
  float_value: number | null;
  paint_seed: number | null;
  wear_name: string | null;
  is_stattrak: boolean;
  is_souvenir: boolean;
  rarity: number | null;
  collection: string | null;
  icon_url: string | null;
  stickers: ListingSticker[];
  seller: { username: string | null; total_trades: number | null } | null;
  watchers: number | null;
  scm_price_cents: number | null;
  reference_price_cents: number | null;
  discount_pct: number | null;
  url: string;
}

export interface ListingsResponse {
  listings: Listing[];
  cursor: string | null;
  summary: {
    min_price_cents: number | null;
    avg_price_cents: number | null;
    median_price_cents: number | null;
    listing_count: number;
    min_float: number | null;
  };
  reference_price_cents: number | null;
  rate: RateBucket | null;
}

export interface RateBucket {
  limit: number | null;
  remaining: number | null;
  resets_in_seconds: number;
  requests_made: number;
}

export interface Snapshot {
  ts: string;
  min_price_cents: number | null;
  avg_price_cents: number | null;
  median_price_cents: number | null;
  listing_count: number | null;
  min_float: number | null;
}

export interface HistoryResponse {
  market_hash_name: string;
  snapshots: Snapshot[];
  summary: {
    lowest_cents: number | null;
    highest_cents: number | null;
    latest_cents: number | null;
    change_pct: number | null;
    trend: "up" | "down" | "stable";
    points: number;
  };
}

export interface TrackedItem {
  id: number;
  market_hash_name: string;
  filters: Record<string, unknown>;
  interval_seconds: number;
  active: number;
  last_run_at: string | null;
}

export interface WatchlistSummary {
  id: number;
  name: string;
  item_count: number;
  total_cents: number;
  prev_total_cents: number;
}

export interface WatchlistItem {
  id: number;
  market_hash_name: string;
  filters: Record<string, unknown>;
  last_price_cents: number | null;
  prev_price_cents: number | null;
  last_checked_at: string | null;
}

export interface WatchlistDetail {
  id: number;
  name: string;
  items: WatchlistItem[];
  errors?: string[];
}

export interface Alert {
  id: number;
  market_hash_name: string;
  rule: {
    max_price_cents?: number;
    min_float?: number;
    max_float?: number;
    category?: string;
    type?: string;
  };
  active: number;
  created_at: string;
  last_triggered_at: string | null;
  trigger_count: number;
}

export interface AlertEvent {
  id: number;
  alert_id: number;
  market_hash_name: string;
  ts: string;
  listing_id: string | null;
  price_cents: number | null;
  float_value: number | null;
  message: string;
}

export interface Deal {
  id: number;
  listing_id: string;
  market_hash_name: string;
  ts: string;
  price_cents: number;
  reference_price_cents: number;
  discount_pct: number;
  float_value: number | null;
  listing_url: string;
}

export interface DealConfig {
  enabled: boolean;
  min_discount_pct: number;
  min_price_cents: number;
  interval_seconds: number;
  max_price_cents: number | null;
}

export interface InventoryRow {
  market_hash_name: string;
  quantity: number;
  wear: string | null;
  item_type: string;
  rarity: number | null;
  rarity_name: string | null;
  image: string | null;
  reference_price_cents: number | null;
  line_value_cents: number | null;
  marketable: boolean;
}

export interface InventoryResponse {
  items: InventoryRow[];
  total_value_cents: number;
  item_count: number;
  priced_count: number;
  unpriced_count: number;
  value_by_type: Record<string, number>;
  context_counts: { tradable: number; trade_protected: number; other: number };
  truncated: boolean;
  pricing_source: string;
}

export interface SteamFetchResponse {
  steam_id: string | null;
  error: string | null;
  inventory: InventoryResponse | null;
}

export interface PortfolioEntry {
  id: number;
  market_hash_name: string;
  buy_price_cents: number;
  quantity: number;
  acquired_at: string | null;
  note: string | null;
  current_price_cents: number | null;
  pnl_cents: number | null;
  roi_pct: number | null;
}

export interface PortfolioResponse {
  entries: PortfolioEntry[];
  total_cost_cents: number;
  total_value_cents: number;
  total_pnl_cents: number | null;
  priced_entries: number;
}

export interface AppStatus {
  version: string;
  api_key_set: boolean;
  api_key_storage: "keychain" | "file";
  itemdb: {
    generated_at: string | null;
    stale: boolean;
    base_items: number;
    market_names: number;
    by_type: Record<string, number>;
  };
  rate: Record<string, RateBucket>;
  ws_clients: number;
}

export type LiveEvent =
  | { type: "alert"; data: { market_hash_name: string; message: string; url: string } }
  | { type: "deal"; data: { market_hash_name: string; price_cents: number; discount_pct: number; url: string } }
  | { type: "snapshot"; data: { market_hash_name: string; min_price_cents: number | null } };
