/** Price-history chart on TradingView lightweight-charts (financial-native). */

import { AreaSeries, ColorType, createChart } from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { Snapshot } from "../types";

const css = (name: string) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim();

export function PriceChart({ snapshots }: { snapshots: Snapshot[] }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || snapshots.length === 0) return;

    const ink = css("--color-ink") || "#eee";
    const rule = css("--color-rule") || "#333";
    const accent = css("--color-accent") || "#e8a33d";

    const chart = createChart(el, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: ink,
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 11,
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: rule, style: 1 },
        horzLines: { color: rule, style: 1 },
      },
      rightPriceScale: { borderColor: rule },
      timeScale: { borderColor: rule, timeVisible: true, secondsVisible: false },
      crosshair: { mode: 0 },
    });

    const series = chart.addSeries(AreaSeries, {
      lineColor: accent,
      lineWidth: 2,
      topColor: `${accentToRgba(accent, 0.25)}`,
      bottomColor: "transparent",
      priceFormat: { type: "custom", formatter: (p: number) => `$${p.toFixed(2)}` },
    });

    const data = snapshots
      .filter((s) => s.min_price_cents !== null)
      .map((s) => ({
        time: Math.floor(new Date(s.ts).getTime() / 1000) as never,
        value: (s.min_price_cents as number) / 100,
      }))
      // lightweight-charts requires strictly ascending unique timestamps
      .filter((point, i, arr) => i === 0 || point.time > arr[i - 1].time);

    series.setData(data);
    chart.timeScale().fitContent();

    return () => chart.remove();
  }, [snapshots]);

  if (snapshots.length === 0) return null;
  return <div ref={ref} className="chart-box" />;
}

/** lightweight-charts needs rgba for gradient stops; approximate from any CSS color. */
function accentToRgba(color: string, alpha: number): string {
  const probe = document.createElement("span");
  probe.style.color = color;
  document.body.appendChild(probe);
  const rgb = getComputedStyle(probe).color;
  probe.remove();
  const m = rgb.match(/(\d+(?:\.\d+)?)/g);
  if (!m) return `rgba(232, 163, 61, ${alpha})`;
  return `rgba(${m[0]}, ${m[1]}, ${m[2]}, ${alpha})`;
}
