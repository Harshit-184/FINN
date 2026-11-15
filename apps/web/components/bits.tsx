import Link from "next/link";
import type { Card, EventPrice, Source } from "@/lib/api";
import { pct, tone, when, words } from "@/lib/api";

const DIR = { positive: ["▲", "text-up"], negative: ["▼", "text-down"], mixed: ["◆", "text-crit"], neutral: ["", ""] } as const;

export function Direction({ d }: { d: Card["direction"] }) {
  const [glyph, cls] = DIR[d];
  return glyph ? <span className={`${cls} text-xs`} title={d} aria-label={d}>{glyph}</span> : null;
}

export function Spark({ values, w = 72, h = 24 }: { values: number[]; w?: number; h?: number }) {
  if (values.length < 2) return <span className="inline-block" style={{ width: w, height: h }} />;
  const lo = Math.min(...values), hi = Math.max(...values), span = hi - lo || 1;
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * w},${h - 2 - ((v - lo) / span) * (h - 4)}`).join(" ");
  const up = values[values.length - 1] >= values[0];
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden>
      <polyline points={pts} fill="none" strokeWidth="1.5" className={up ? "stroke-up" : "stroke-down"} />
    </svg>
  );
}

export function Strip({ e }: { e: EventPrice }) {
  const cell = (label: string, v: number | null | undefined) => (
    <div><div className="text-[11px] text-dim">{label}</div><div className={`num text-sm ${tone(v)}`}>{pct(v)}</div></div>
  );
  return (
    <div className="mt-3 border-t border-line pt-2">
      <div className="grid grid-cols-4 gap-2">
        <div><div className="text-[11px] text-dim">Close before</div><div className="num text-sm">{e.before.close.toFixed(1)}</div></div>
        {cell("1 session", e.t1?.pct)}
        {cell("5 sessions", e.t5?.pct)}
        <div><div className="text-[11px] text-dim">Volume</div><div className="num text-sm">{e.volume_x ? `${e.volume_x.toFixed(1)}×` : "–"}</div></div>
      </div>
      <p className="mt-1 text-[11px] text-dim">Price around the filing. Timing association, not cause.</p>
    </div>
  );
}

export function FilingCard({ c, full }: { c: Card; full?: boolean }) {
  const spine = c.tier === "critical" ? "border-l-crit" : c.tier === "notable" ? "border-l-dim" : "border-l-line";
  return (
    <article className={`border-l-2 ${spine} bg-panel px-3 py-3`}>
      <header className="flex items-baseline gap-2 text-xs">
        <Link href={`/company/${c.symbol}`} className="num font-medium text-text">{c.symbol}</Link>
        <span className="text-dim">{words(c.category)}</span>
        <Direction d={c.direction} />
        {c.revised && <span className="rounded-sm border border-crit px-1 text-[11px] text-crit">Revised</span>}
        <time className="num ml-auto text-dim">{when(c.filed_at)}</time>
      </header>
      <h3 className={`mt-1 ${full ? "text-[15px] leading-snug" : "text-sm leading-snug"}`}>{c.headline || c.subject}</h3>
      {full && (
        <>
          {c.pillar_name && (
            <p className="mt-2 text-xs text-dim">
              Touches your thesis pillar <span className="text-text">{c.pillar_name}</span>
              {c.pillar_evidence && <> (filing mentions “{c.pillar_evidence}”)</>}
            </p>
          )}
          {c.event_price && <Strip e={c.event_price} />}
          <footer className="mt-3 flex flex-wrap items-center gap-2 text-xs">
            <span className="ev ev-reported">Reported</span>
            <span className="num text-dim" title={Object.entries(c.score_terms).map(([k, v]) => `${k} ${v}`).join("  ")}>
              priority {c.score.toFixed(0)}
            </span>
            {c.also_on.length > 0 && <span className="text-dim">also on {c.exchange === "NSE" ? "BSE" : "NSE"}</span>}
            {c.pdf_url && <a className="ml-auto underline decoration-line underline-offset-4" href={c.pdf_url} target="_blank" rel="noreferrer">Open filing</a>}
          </footer>
        </>
      )}
    </article>
  );
}

export function Status({ source, asOf, sample }: { source?: Source; asOf?: string; sample?: boolean }) {
  return (
    <p className="text-[11px] text-dim">
      {sample && <span className="mr-2 rounded-sm bg-crit px-1 font-medium text-ink">Sample data for layout only</span>}
      {asOf && <>Data as of <span className="num">{when(asOf)}</span>. </>}
      {source === "snapshot" && "Showing the saved snapshot."}
    </p>
  );
}

export function Skeleton({ text }: { text: string }) {
  return <div className="animate-pulse bg-panel px-3 py-6 text-sm text-dim" role="status">{text}</div>;
}

export function Problem({ text }: { text: string }) {
  return <div className="border-l-2 border-l-down bg-panel px-3 py-4 text-sm">{text}</div>;
}
