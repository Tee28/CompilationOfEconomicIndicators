import { useEffect, useRef } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { vi } from "../i18n/vi";
import { CurrencyCtx, useFile, useStoredCurrency } from "../lib/hooks";
import type { Currency } from "../lib/format";
import type { Overview } from "../types/overview";

const CURRENCIES: Currency[] = ["USD", "JPY", "VND"];

export function Layout() {
  const cc = useStoredCurrency();
  const nav = useNavigate();
  const ov = useFile<Overview>("overview");
  const ids = useRef<string[]>([]);
  ids.current = ov.data?.markets.map((m) => m.id) ?? [];

  useEffect(() => {
    let g = false;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (/input|select|textarea/i.test(t.tagName) || e.ctrlKey || e.metaKey || e.altKey) return;
      if (g) {
        g = false;
        if (e.key === "o") nav("/");
        if (e.key === "p") nav("/methodology");
        return;
      }
      if (e.key === "g") {
        g = true;
        return;
      }
      if (e.key === "?") window.alert(vi.help);
      const n = Number(e.key);
      if (n >= 1 && n <= 9 && ids.current[n - 1]) nav(`/${ids.current[n - 1]}`);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [nav]);

  return (
    <CurrencyCtx.Provider value={cc}>
      <a className="skip" href="#main">
        {vi.skipToContent}
      </a>
      <header className="top">
        <Link to="/" className="brand">
          {vi.appName}
        </Link>
        <nav aria-label="Điều hướng">
          <NavLink to="/" end>
            {vi.nav.overview}
          </NavLink>
          <NavLink to="/methodology">{vi.nav.methodology}</NavLink>
        </nav>
        <label className="cur">
          <span>{vi.currency}</span>
          <select value={cc.cur} onChange={(e) => cc.setCur(e.target.value as Currency)} title={vi.currencyNote}>
            {CURRENCIES.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        {ov.data && (
          <span className="asof num">
            {vi.asof}: {ov.data.asof}
          </span>
        )}
      </header>
      <main id="main">
        <Outlet />
      </main>
      <footer>
        <p className="disclaimer">{vi.disclaimer}</p>
        <p>{vi.fredLine}</p>
        <p>{vi.sources}: FRED, EIA.</p>
      </footer>
    </CurrencyCtx.Provider>
  );
}
