import { Link, useParams } from "react-router-dom";
import { vi } from "../i18n/vi";
import { useCurrency, useFile } from "../lib/hooks";
import { convert, fmtNum, fmtPct, fmtSigned } from "../lib/format";
import { BandChart, ConfidenceBadge, Disclaimer, Loading, ProbBar, SeriesChart, StaleBadge } from "../components/Ui";
import type { HorizonForecast, MarketPage as MP, SiteSeries } from "../types/market";

function Horizon({ h }: { h: HorizonForecast }) {
  const title = h.key === "short" ? vi.short : vi.medium;
  const s = h.skill;
  return (
    <section className="card" aria-label={title}>
      <h3>
        {title} <span className="muted num">({h.window})</span>
      </h3>
      <ProbBar p={h.p_up} label={vi.pUp} />
      <ConfidenceBadge level={h.confidence} />
      <h4>{vi.returnBand}</h4>
      <p className="num">
        p10 {fmtPct(h.return_band.p10, true)} · p50 {fmtPct(h.return_band.p50, true)} · p90 {fmtPct(h.return_band.p90, true)}
      </p>
      <BandChart band={h.return_band} label={`${vi.returnBand}: ${title}`} />
      <p>{h.narrative_vi}</p>
      <h4>{vi.drivers}</h4>
      <ul className="drivers">
        {h.drivers.map((d) => (
          <li key={d.indicator}>
            <span>
              {d.direction === "up" ? "▲" : "▼"} {d.label_vi}
            </span>
            <span className="num">{fmtSigned(d.contribution)}</span>
            <span
              className={`dbar ${d.contribution >= 0 ? "pos" : "neg"}`}
              style={{ width: `${Math.min(100, Math.abs(d.contribution) * 400)}%` }}
              aria-hidden
            />
          </li>
        ))}
      </ul>
      <h4>{vi.trackRecord}</h4>
      <p className={s.beats_baselines ? "ok" : "warnText"}>{s.beats_baselines ? vi.beats : vi.notBeats}</p>
      <p className="num muted">
        {vi.nEff}: {s.n_eff} · {vi.vsRw}: {fmtSigned(s.vs_random_walk)} · {vi.vsClim}: {fmtSigned(s.vs_climatology)}
      </p>
      <Link to="/methodology">{vi.trackRecordLink}</Link>
    </section>
  );
}

function SeriesPanel({ s }: { s: SiteSeries }) {
  const { cur } = useCurrency();
  if (s.license === "internal")
    return (
      <section className="card">
        <h3>{s.name_vi}</h3>
        <p className="muted">{vi.internalSignal}</p>
      </section>
    );
  const c = convert(s.unit, s.values, cur);
  const last = c.values.at(-1);
  return (
    <section className="card">
      <h3>
        {s.name_vi} {s.stale && <StaleBadge />}
      </h3>
      <p className="num">
        {fmtNum(last)} <span className="muted">{c.unit}</span>
      </p>
      <SeriesChart dates={s.dates} values={c.values} unit={c.unit} label={`${vi.history}: ${s.name_vi}`} />
      <p className="muted">
        {vi.sources}: {s.attribution || "-"}
        {c.unit !== s.unit ? ` · ${vi.currencyNote}` : ""}
      </p>
    </section>
  );
}

export function MarketPage() {
  const { id } = useParams();
  const { data, error } = useFile<MP>(id);
  if (!data) return <Loading error={error} />;
  const s = data.horizons.find((h) => h.key === "short");
  const m = data.horizons.find((h) => h.key === "medium");
  return (
    <>
      <Link to="/">{vi.back}</Link>
      <h1>{data.title_vi}</h1>
      <p className="lead">{data.narrative_vi}</p>
      <p className="muted num">
        {vi.asof}: {data.asof}
      </p>
      <div className="grid">
        {s && <Horizon h={s} />}
        {m && <Horizon h={m} />}
      </div>
      <h2>{vi.history}</h2>
      <div className="grid">
        {data.series.map((x) => (
          <SeriesPanel key={x.id} s={x} />
        ))}
      </div>
      <Disclaimer />
    </>
  );
}
