// Dev-only fallback (dynamic import behind import.meta.env.DEV; dropped from production builds).
const mods = import.meta.glob("../../../tests/fixtures/site/*.json", { eager: true, import: "default" });
export function fixture(name: string): unknown {
  const k = Object.keys(mods).find((p) => p.endsWith(`/${name}.json`));
  return k ? mods[k] : undefined;
}
