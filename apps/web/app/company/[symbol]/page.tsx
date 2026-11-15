"use client";
import Link from "next/link";
import { use } from "react";
import { FilingCard, Problem, Skeleton } from "@/components/bits";
import { type Company, pct, tone } from "@/lib/api";
import { useLoad } from "@/lib/useLoad";

function Chart({ c }: { c: Company }) {
  const W = 560, H = 140, p = c.prices;
  if (p.length < 2) return null;
  const lo = Math.min(...p.map((b) => b.close)), hi = Math.max(...p.map((b) => b.close)), span = hi - lo || 1;
  const x = (i: number) => 6 + (i / (p.length - 1)) * (W - 12), y = (v: number) => H - 8 - ((v - lo) / span) * (H - 16);
  const dots = c.filings.filter((f) => f.tier !== "routine").map((f) => {
    const i = p.findIndex((b) => b.d >= f.filed_at.slice(0, 10));
    return i < 0 ? null : { i, f };
  }).filter(Boolean) as { i: number; f: Company["filings"][number] }[];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`${c.symbol} closing price, last ${p.length} sessions, with filing dates marked`}>
      <polyline fill="none" strokeWidth="1.5" className="stroke-text" points={p.map((b, i) => `${x(i)},${y(b.close)}`).join(" ")} />
      {dots.map(({ i, f }) => (
        <circle key={f.id} cx={x(i)} cy={y(p[i].close)} r="4" className={f.tier === "critical" ? "fill-crit" : "fill-dim"}>
          <title>{f.subject}</title>
        </circle>
      ))}
    </svg>
  );
}

export default function CompanyPage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = use(params);
  const { data: c, error } = useLoad<Company>(`/company/${symbol}`, `company_${symbol}.json`);
  if (error) return <Problem text={error} />;
  if (!c) return <Skeleton text={`Loading ${symbol}…`} />;
  const last = c.prices.at(-1), prev = c.prices.at(-2);
  const day = last && prev ? (100 * (last.close - prev.close)) / prev.close : null;
  const shown = c.filings.filter((f) => f.tier !== "routine"), routine = c.filings.length - shown.length;
  return (
    <div className="space-y-5">
      <header>
        <div className="flex items-baseline justify-between">
          <h1 className="text-xl font-semibold">{c.name}</h1>
          {last && <div className="num text-right text-sm">{last.close.toFixed(1)} <span className={tone(day)}>{pct(day)}</span></div>}
        </div>
        <p className="text-xs text-dim">{c.symbol} · {c.sector}</p>
      </header>
      <Chart c={c} />
      {c.has_research && (
        <Link href={`/research/${c.symbol}`} className="block bg-text px-3 py-2.5 text-center text-sm font-medium text-ink">
          Did management deliver what it promised?
        </Link>
      )}
      {c.pillars.length > 0 && (
        <section>
          <h2 className="mb-1 text-sm text-dim">Your thesis pillars</h2>
          <ul className="text-sm">{c.pillars.map((p) => <li key={p.id}>{p.name}</li>)}</ul>
        </section>
      )}
      <section className="space-y-2">
        <h2 className="text-sm text-dim">Filings</h2>
        {shown.length === 0 && <p className="text-sm text-dim">No critical or notable filings in the stored period.</p>}
        {shown.map((f) => <FilingCard key={f.id} c={f} full />)}
        {routine > 0 && <p className="text-xs text-dim"><span className="num">{routine}</span> routine filings not shown.</p>}
      </section>
    </div>
  );
}
