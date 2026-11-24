import { createContext, useContext, useEffect, useState } from "react";
import { loadFile } from "./loader";
import type { Currency } from "./format";

export type Async<T> = { data?: T; error?: string };

export function useFile<T>(name: string | undefined): Async<T> {
  const [s, set] = useState<Async<T>>({});
  useEffect(() => {
    if (!name) return;
    let live = true;
    set({});
    loadFile<T>(name).then(
      (data) => live && set({ data }),
      (e) => live && set({ error: String(e?.message ?? e) }),
    );
    return () => { live = false; };
  }, [name]);
  return s;
}

export const CurrencyCtx = createContext<{ cur: Currency; setCur: (c: Currency) => void }>({
  cur: "USD",
  setCur: () => {},
});
export const useCurrency = () => useContext(CurrencyCtx);

export function useStoredCurrency(): { cur: Currency; setCur: (c: Currency) => void } {
  const [cur, set] = useState<Currency>(() => {
    try {
      const v = localStorage.getItem("currency");
      return v === "JPY" || v === "VND" ? v : "USD";
    } catch { return "USD"; }
  });
  const setCur = (c: Currency) => {
    set(c);
    try { localStorage.setItem("currency", c); } catch { /* ignore */ }
  };
  return { cur, setCur };
}
