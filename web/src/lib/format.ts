const nf = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
export const fmtNum = (x: number | null | undefined) => (x == null || Number.isNaN(x) ? "-" : nf.format(x));
export const fmtPct = (x: number, signed = false) =>
  `${signed && x > 0 ? "+" : ""}${(x * 100).toFixed(1)}%`;
export const fmtSigned = (x: number) => `${x > 0 ? "+" : ""}${x.toFixed(2)}`;

/** Fixed reference rates (placeholder until FX series are part of the data contract; see T009). */
export type Currency = "USD" | "JPY" | "VND";
export const RATES: Record<Currency, number> = { USD: 1, JPY: 150, VND: 25000 };
export function convert(unit: string, values: (number | null)[], cur: Currency) {
  if (!unit.startsWith("USD") || cur === "USD") return { unit, values };
  return {
    unit: cur + unit.slice(3),
    values: values.map((v) => (v == null ? null : v * RATES[cur])),
  };
}
