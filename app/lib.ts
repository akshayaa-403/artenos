export async function api<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, body === undefined ? { cache: "no-store" } : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = (data as { detail?: unknown }).detail;
    const msg = typeof d === "string" ? d
      : d && typeof d === "object" && "message" in d ? String((d as { message: unknown }).message)
      : Array.isArray(d) ? "Please check the question (3 to 300 characters)."
      : `Request failed (${res.status})`;
    throw new Error(msg);
  }
  return data as T;
}

export const usd = (x: number | null | undefined, digits = 4) =>
  x == null ? "n/a" : `$${x.toFixed(digits)}`;
export const pct = (x: number | null | undefined, digits = 1) =>
  x == null ? "n/a" : `${(x * 100).toFixed(digits)}%`;
export const ms = (x: number | null | undefined) =>
  x == null ? "n/a" : x >= 1000 ? `${(x / 1000).toFixed(1)} s` : `${Math.round(x)} ms`;

export function cell(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return String(v);
}
