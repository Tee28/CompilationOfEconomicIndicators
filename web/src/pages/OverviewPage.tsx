import { Link } from "react-router-dom";
import { vi } from "../i18n/vi";
import { useFile } from "../lib/hooks";
import { fmtNum } from "../lib/format";
import { ConfidenceBadge, Disclaimer, Loading, ProbBar } from "../components/Ui";
import type { Overview } from "../types/overview";

export function OverviewPage() {
  const { data, error } = useFile<Overview>("overview");
  if (!data) return <Loading error={error} />;
  return (
    <>
      <h1>{vi.nav.overview}</h1>
      <h2>{vi.composites}</h2>
      <div className="grid">
        {data.composites.map((c) => (
          <article className="card" key={c.id}>
            <h3>{c.name_vi}</h3>
            <p className="big">{c.label}</p>
            {c.license === "internal" || c.level == null ? (
              <p className="muted">{vi.internalSignal}</p>
            ) : (
              <p className="num">
                {vi.level}: {fmtNum(c.level)}
              </p>
            )}
            <p className="num muted">
              {vi.percentile}: {c.percentile.toFixed(0)}
            </p>
          </article>
        ))}
      </div>
      <h2>{vi.markets}</h2>
      <div className="grid">
        {data.markets.map((m) => (
          <Link className="card link" key={m.id} to={`/${m.id}`}>
            <h3>{m.name_vi}</h3>
            <p className="big">{m.label}</p>
            <ProbBar p={m.p_up_short} label={`${vi.short} ${vi.pUp}`} />
            <ConfidenceBadge level={m.confidence_short} />
            <ProbBar p={m.p_up_medium} label={`${vi.medium} ${vi.pUp}`} />
            <ConfidenceBadge level={m.confidence_medium} />
          </Link>
        ))}
      </div>
      <Disclaimer />
    </>
  );
}
