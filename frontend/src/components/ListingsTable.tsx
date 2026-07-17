/** Live listings table: floats at full precision, stickers, seller, deal badges. */

import { floatShort, timeAgo, usd } from "../format";
import type { Listing } from "../types";
import { DiscountBadge } from "./Delta";
import { MarketTag } from "./MarketTag";

export function ListingsTable({
  listings,
  showItemColumn = true,
}: {
  listings: Listing[];
  showItemColumn?: boolean;
}) {
  if (listings.length === 0) return null;
  return (
    <div className="table-wrap fade-in">
      <table className="data">
        <thead>
          <tr>
            {showItemColumn && <th>Item</th>}
            <th className="right">
              Price · <MarketTag market="csfloat" small />
            </th>
            <th className="right">Float</th>
            <th>Details</th>
            <th>Seller</th>
            <th className="right">Listed</th>
            <th aria-label="actions" />
          </tr>
        </thead>
        <tbody>
          {listings.map((l) => (
            <tr key={l.id}>
              {showItemColumn && (
                <td>
                  <div className="cell-item">
                    {l.icon_url && (
                      <img
                        src={`https://community.akamai.steamstatic.com/economy/image/${l.icon_url}`}
                        alt=""
                        loading="lazy"
                      />
                    )}
                    <div style={{ minWidth: 0 }}>
                      <div className="name">{l.market_hash_name}</div>
                      {l.collection && <div className="sub">{l.collection}</div>}
                    </div>
                  </div>
                </td>
              )}
              <td className="right">
                <div className="num" style={{ fontWeight: 600 }}>{usd(l.price_cents)}</div>
                <DiscountBadge value={l.discount_pct} />
              </td>
              <td className="right">
                <span className="num" title={l.float_value?.toString() ?? undefined}>
                  {floatShort(l.float_value)}
                </span>
              </td>
              <td>
                <div className="row" style={{ gap: 4 }}>
                  {l.type === "auction" && <span className="badge accent">auction</span>}
                  {l.paint_seed !== null && (
                    <span className="badge num" title="Paint seed">
                      #{l.paint_seed}
                    </span>
                  )}
                  {l.stickers.length > 0 && (
                    <span
                      className="badge"
                      title={l.stickers.map((s) => s.name ?? "?").join("\n")}
                    >
                      {l.stickers.length}× sticker
                    </span>
                  )}
                  {l.watchers !== null && l.watchers > 0 && (
                    <span className="badge" title="Watchers">
                      {l.watchers} watching
                    </span>
                  )}
                </div>
              </td>
              <td>
                <span className="small muted">
                  {l.seller?.username ?? "anonymous"}
                  {l.seller?.total_trades !== null && l.seller?.total_trades !== undefined && (
                    <span className="xsmall"> · {l.seller.total_trades} trades</span>
                  )}
                </span>
              </td>
              <td className="right">
                <span className="xsmall muted num">{timeAgo(l.created_at)}</span>
              </td>
              <td className="right">
                <a
                  className="btn sm ghost"
                  href={l.url}
                  target="_blank"
                  rel="noreferrer"
                  aria-label={`Open ${l.market_hash_name} on CSFloat`}
                >
                  Open ↗
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
