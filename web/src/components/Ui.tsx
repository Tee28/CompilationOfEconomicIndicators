import { Suspense, lazy } from "react";
import { vi } from "../i18n/vi";
import { fmtPct } from "../lib/format";

const BandChartLazy = lazy(() => import("./Charts"));
const SeriesChartLazy = lazy(() => import("./Charts").then((m) => ({ default: m.SeriesChart })));
export const BandChart = (p: React.ComponentProps<typeof BandChartLazy>) => (
  <Suspense fallback={<div className="chart" />}>
    <BandChartLazy {...p} />
  </Suspense>
);
export const SeriesChart = (p: React.ComponentProps<typeof SeriesChartLazy>) => (
  <Suspense fallback={<div className="chart" />}>
    <SeriesChartLazy {...p} />
  </Suspense>
);

export function ConfidenceBadge({ level }: { level: string }) {
  return (
    <span className={`badge conf-${level}`} title={vi.confidenceHint}>
      Độ tin cậy: {vi.confidence[level] ?? level}
    </span>
  );
}

export function StaleBadge() {
  return <span className="badge warn">{vi.stale}</span>;
}

/** P(up) bar 0-100% with a 50% neutral tick. Value always printed (not colour only). */
export function ProbBar({ p, label }: { p: number; label: string }) {
  const arrow = p > 0.5 ? "▲" : p < 0.5 ? "▼" : "■";
  return (
    <div className="probbar" role="img" aria-label={`${label}: ${fmtPct(p)}`}>
      <div className="probrow">
        <span>{label}</span>
        <strong className="num">
          {arrow} {fmtPct(p)}
        </strong>
      </div>
      <div className="track">
        <div className="fill" style={{ width: `${p * 100}%` }} />
        <div className="tick" title={vi.pUpNeutral} />
      </div>
    </div>
  );
}

export function Disclaimer() {
  return <p className="disclaimer">{vi.disclaimer}</p>;
}

export function Loading({ error }: { error?: string }) {
  return error ? (
    <p role="alert" className="err">
      {vi.error}: {error}
    </p>
  ) : (
    <p aria-busy="true">{vi.loading}</p>
  );
}
