import type { Manifest } from "../types/manifest";

const BASE = "data/";

async function getJson<T>(url: string, noStore = false): Promise<T> {
  const r = await fetch(url, noStore ? { cache: "no-store" } : undefined);
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return (await r.json()) as T;
}

let manifestP: Promise<Manifest | null> | null = null;

/** manifest.json is fetched no-store; null means "not published" (dev fixture fallback applies). */
export function loadManifest(): Promise<Manifest | null> {
  manifestP ??= getJson<Manifest>(`${BASE}manifest.json`, true).catch(() => null);
  return manifestP;
}

export async function loadFile<T>(name: string): Promise<T> {
  const m = await loadManifest();
  const entry = m?.files.find((f) => f.name.startsWith(`${name}.`));
  if (entry) return getJson<T>(`${BASE}${entry.name}`);
  if (import.meta.env.DEV) {
    const { fixture } = await import("./fixtures");
    const f = fixture(name);
    if (f) return f as T;
  }
  throw new Error(`missing data file: ${name}`);
}

export const resetLoader = () => { manifestP = null; };
