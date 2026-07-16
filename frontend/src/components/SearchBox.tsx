/** Global item autocomplete: debounced, keyboard-navigable, "/" to focus. */

import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { usd } from "../format";
import type { ItemVariant } from "../types";

export function SearchBox({
  onPick,
  placeholder = "Search 35,000+ CS2 items…",
  autoFocus = false,
}: {
  onPick: (item: ItemVariant) => void;
  placeholder?: string;
  autoFocus?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ItemVariant[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const debounce = useRef<ReturnType<typeof setTimeout>>();

  // "/" focuses search from anywhere (unless typing in another field)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", onClick);
    return () => window.removeEventListener("mousedown", onClick);
  }, []);

  const runSearch = (q: string) => {
    setQuery(q);
    clearTimeout(debounce.current);
    if (q.trim().length < 2) {
      setResults([]);
      setOpen(false);
      return;
    }
    debounce.current = setTimeout(async () => {
      try {
        const { results } = await api.search(q, 10);
        setResults(results);
        setActive(0);
        setOpen(results.length > 0);
      } catch {
        setOpen(false);
      }
    }, 160);
  };

  const pick = (item: ItemVariant) => {
    setOpen(false);
    setQuery("");
    inputRef.current?.blur();
    onPick(item);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (!open) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter" && results[active]) {
      e.preventDefault();
      pick(results[active]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div className="searchbox" ref={boxRef}>
      <span className="glyph" aria-hidden>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
      </span>
      <input
        ref={inputRef}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-label="Search items"
        placeholder={placeholder}
        value={query}
        autoFocus={autoFocus}
        onChange={(e) => runSearch(e.target.value)}
        onKeyDown={onKeyDown}
        onFocus={() => results.length > 0 && setOpen(true)}
      />
      <kbd aria-hidden>/</kbd>
      {open && (
        <div className="ac-panel" role="listbox">
          {results.map((item, i) => (
            <button
              key={item.market_hash_name}
              type="button"
              role="option"
              aria-selected={i === active}
              className={`ac-row ${i === active ? "active" : ""}`}
              onMouseEnter={() => setActive(i)}
              onClick={() => pick(item)}
            >
              {item.image ? <img src={item.image} alt="" loading="lazy" /> : <span style={{ width: 42 }} />}
              <span className="ac-name">{item.market_hash_name}</span>
              <span className="ac-meta num">
                {item.reference_price_cents ? usd(item.reference_price_cents) : item.item_type}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
