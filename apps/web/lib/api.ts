// Live API first; if it is slow, down or not configured, read the snapshot shipped with the app.
const API = process.env.NEXT_PUBLIC_API_URL;

export type Source = "live" | "snapshot";
export type Loaded<T> = { data: T; source: Source };

export async function load<T>(path: string, snapshotFile: string): Promise<Loaded<T>> {
  if (API) {
    try {
      const ctl = new AbortController();
      const timer = setTimeout(() => ctl.abort(), 4000);   // Render's free tier can take far longer to wake
      const r = await fetch(`${API}${path}`, { signal: ctl.signal });
      clearTimeout(timer);
      if (r.ok) return { data: await r.json(), source: "live" };
    } catch { /* fall through to the snapshot */ }
  }
  const r = await fetch(`/snapshot/${snapshotFile}`);
  if (!r.ok) throw new Error("No data yet. The first ingestion run has not been published.");
  return { data: await r.json(), source: "snapshot" };
}

export type Card = {
  id: string; symbol: string; company: string; subject: string; body: string; filed_at: string;
  category: string; tier: "critical" | "notable" | "routine"; score: number; score_terms: Record<string, number>;
  direction: "positive" | "negative" | "mixed" | "neutral"; pillar_name: string | null; pillar_evidence: string | null;
  revised: boolean; amends: string | null; also_on: string[]; exchange: string; pdf_url: string | null;
  rule_why: string; confidence: "high" | "medium" | "low";
  event_price?: EventPrice | null;
};
export type EventPrice = { before: { d: string; close: number }; t1: Leg | null; t5: Leg | null; volume_x: number | null; label: string };
type Leg = { d: string; close: number; pct: number };
export type AlertItem = { symbol: string; d: string; rule: string; headline: string; value: number | null; threshold: number | null; folded: number };
export type Brief = {
  as_of: string; window_hours: number; headline: string; sample?: boolean;
  needs_attention: { symbol: string; company: string; reasons: string[]; direction: Card["direction"] }[];
  critical: Card[]; notable: Card[]; routine: Card[]; alerts: AlertItem[];
};
export type Holding = {
  symbol: string; name: string; sector: string; weight: number; close: number | null; as_of: string | null;
  day_pct: number | null; volume_x: number | null; critical: number; pillars_touched: string[]; spark: number[];
};
export type Company = {
  symbol: string; name: string; sector: string; pillars: { id: string; name: string }[];
  prices: { d: string; close: number; volume: number }[]; filings: Card[];
};

export const pct = (v: number | null | undefined, digits = 1) =>
  v == null ? "–" : `${v > 0 ? "+" : ""}${v.toFixed(digits)}%`;
export const tone = (v: number | null | undefined) => (v == null || v === 0 ? "text-dim" : v > 0 ? "text-up" : "text-down");
export const when = (iso: string) =>
  new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false });
export const words = (s: string) => s.replace(/_/g, " ").replace(/^m and a$/, "M&A");
