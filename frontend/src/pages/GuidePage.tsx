/** Trader guide: the concepts behind CS2 pricing, in plain language.
 *
 * Written for someone with a $500 inventory who trades a few times a month
 * and has never read a market thread. No jargon without an explanation.
 */

import { useEffect, useState } from "react";
import { api } from "../api";
import { usd } from "../format";
import type { MarketFeeRow } from "../types";

const WEAR_TABLE = [
  ["Factory New (FN)", "0.00 - 0.07", "Cleanest look, biggest price premium"],
  ["Minimal Wear (MW)", "0.07 - 0.15", "Slight scuffs, usually the value sweet spot"],
  ["Field-Tested (FT)", "0.15 - 0.38", "Visible wear, most-traded tier"],
  ["Well-Worn (WW)", "0.38 - 0.45", "Heavy wear, thin supply oddly enough"],
  ["Battle-Scarred (BS)", "0.45 - 1.00", "Cheapest, occasionally iconic (e.g. low-float BS)"],
];

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section className="panel stack" aria-labelledby={id} style={{ maxWidth: "80ch" }}>
      <h2 id={id}>{title}</h2>
      {children}
    </section>
  );
}

export function GuidePage() {
  const [fees, setFees] = useState<MarketFeeRow[]>([]);

  useEffect(() => {
    api.marketFees(10000).then((f) => setFees(f.marketplaces)).catch(() => {});
  }, []);

  return (
    <div className="stack fade-in">
      <div className="page-head">
        <div>
          <h1>Trader’s guide</h1>
          <p>The five concepts that explain 95% of CS2 skin pricing - five minutes, no jargon.</p>
        </div>
      </div>

      <Section id="g-float" title="Floats and wear - why two “identical” skins differ in price">
        <p className="small">
          Every skin has a <strong>float value</strong> between 0 and 1, rolled when it drops
          or gets unboxed and fixed forever. Lower float = less visible wear. The float decides
          the wear tier printed in the item name:
        </p>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr><th>Wear</th><th className="right">Float range</th><th>What it means</th></tr>
            </thead>
            <tbody>
              {WEAR_TABLE.map(([wear, range, note]) => (
                <tr key={wear}>
                  <td>{wear}</td>
                  <td className="right num">{range}</td>
                  <td className="small muted">{note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="small muted">
          Within a tier, floats still matter: a 0.150 Field-Tested looks like Minimal Wear and
          sells above the FT average. That’s why this app shows floats to full precision and why
          the deal finder calls out “top 1% float for FT”. Note that each skin also has its own
          float cap - some can never be Factory New.
        </p>
      </Section>

      <Section id="g-patterns" title="Patterns - the lottery printed on your skin">
        <p className="small">
          The <strong>paint seed / pattern index</strong> (0-1000) controls how the texture is
          placed. For most skins it’s cosmetic trivia. For a few families it’s worth real money:
        </p>
        <ul className="small" style={{ margin: 0, paddingLeft: "1.2em", lineHeight: 1.7 }}>
          <li><strong>Case Hardened “blue gems”</strong> - mostly-blue patterns sell for many multiples of the base price; the famous #661 AK pattern is six figures.</li>
          <li><strong>Doppler phases</strong> - the same “Doppler” name hides Phase 1-4, Ruby, Sapphire and Black Pearl. Rubies and Sapphires cost far more; this app’s reference price for a Doppler uses the cheapest phase, so treat gems separately.</li>
          <li><strong>Fade percentages</strong> - “full fade” (100%) commands a premium over 80% fades.</li>
        </ul>
        <p className="small muted">
          If a listing looks suspiciously cheap for its float, check whether the price is normal
          for its <em>pattern</em> before assuming it’s a steal - and check the pattern before
          selling, so you’re not the one giving away a blue gem.
        </p>
      </Section>

      <Section id="g-locks" title="Trade locks - why timing matters">
        <ul className="small" style={{ margin: 0, paddingLeft: "1.2em", lineHeight: 1.7 }}>
          <li>Items bought on the <strong>Steam Market</strong> are locked from trading for 7 days.</li>
          <li>Since <strong>April 2024</strong>, items received in a trade are <em>trade-protected</em> for 10 days - they sit in a separate inventory section (that’s why this app’s inventory import has a second “trade-protected” paste box) and the original owner can revert the trade during that window.</li>
          <li>Third-party marketplaces inherit these delays: when you buy, expect to wait before you can move the item again.</li>
        </ul>
        <p className="small muted">
          Practical upshot: price swings shorter than a lock window are noise you can’t act on.
          Plan sells a week ahead of when you want the money.
        </p>
      </Section>

      <Section id="g-fees" title="Marketplace fees - where selling actually pays">
        <p className="small">
          The same skin nets a very different payout depending on where you sell it. On a $100
          sale:
        </p>
        {fees.length > 0 && (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Marketplace</th>
                  <th className="right">Seller fee</th>
                  <th className="right">You receive</th>
                  <th>Payout</th>
                  <th>Worth knowing</th>
                </tr>
              </thead>
              <tbody>
                {fees.map((row) => (
                  <tr key={row.key}>
                    <td>{row.name}</td>
                    <td className="right num">{row.seller_fee_pct}%</td>
                    <td className="right num" style={{ fontWeight: 600 }}>{usd(row.net_cents ?? null)}</td>
                    <td className="small muted">{row.payout}</td>
                    <td className="xsmall muted" style={{ maxWidth: 320 }}>{row.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="small muted">
          The Steam Market’s 15% is the headline trap: the bigger catch is that Steam wallet
          money can never be withdrawn. Sell on Steam only if you plan to spend it on Steam.
          Every item page here shows this same breakdown at that item’s price.
        </p>
      </Section>

      <Section id="g-prices" title="How this app prices things">
        <ul className="small" style={{ margin: 0, paddingLeft: "1.2em", lineHeight: 1.7 }}>
          <li><strong>Live listings</strong> come straight from CSFloat’s market API - real asks, right now.</li>
          <li><strong>Reference prices</strong> come from CSFloat’s own per-wear price data, refreshed with the item catalog. They power the deal finder, inventory totals and portfolio P&amp;L without burning API budget. Treat them as “fair value”, not a guaranteed sale price.</li>
          <li><strong>Deals</strong> are listings sitting well below reference - with the reason spelled out (exceptional float, priced under the next wear tier, sticker value riding along).</li>
        </ul>
      </Section>

      <Section id="g-key" title="Getting your CSFloat API key (one minute)">
        <ol className="small" style={{ margin: 0, paddingLeft: "1.2em", lineHeight: 1.8 }}>
          <li>Sign in at <a className="link-accent" href="https://csfloat.com" target="_blank" rel="noreferrer">csfloat.com</a> with Steam.</li>
          <li>Click your avatar → <strong>Developers</strong> (or Profile → Developer tab).</li>
          <li>Create a new API key and paste it into <a className="link-accent" href="/settings">Settings</a> here.</li>
        </ol>
        <p className="small muted">
          The key is free, read-only for market data, and stays on your machine (OS keychain).
          Without one you can still use the catalog, search autocomplete, and inventory
          valuation - live listings, tracking and the deal finder need it.
        </p>
      </Section>
    </div>
  );
}
