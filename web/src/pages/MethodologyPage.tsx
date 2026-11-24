import { vi } from "../i18n/vi";
import { Disclaimer } from "../components/Ui";

export function MethodologyPage() {
  const t = vi.methodology;
  return (
    <>
      <h1>{t.title}</h1>
      <p className="lead">{t.intro}</p>
      {t.sections.map(([h, b]) => (
        <section className="card" key={h}>
          <h3>{h}</h3>
          <p>{b}</p>
        </section>
      ))}
      <section className="card" id="do-chinh-xac">
        <h3>{t.accuracyTitle}</h3>
        <p>{t.accuracyBody}</p>
      </section>
      <Disclaimer />
    </>
  );
}
