"use client";
import Link from "next/link";
import { Problem, Skeleton, Spark } from "@/components/bits";
import { pct, tone, type Holding } from "@/lib/api";
import { useLoad } from "@/lib/useLoad";

export default function Portfolio() {
  const { data, error } = useLoad<{ weights_note: string; holdings: Holding[] }>("/portfolio", "portfolio.json");
  const done = useLoad<{ symbol: string; name: string; targets: number }[]>("/researched", "researched.json").data;
  if (error) return <Problem text={error} />;
  if (!data) return <Skeleton text="Loading 18 holdings…" />;
  return (
    <div>
      <h1 className="text-xl font-semibold">Portfolio</h1>
      <p className="mt-1 text-xs text-dim">{data.weights_note} Prices are end of day.</p>
      <ul className="mt-4 divide-y divide-line border-y border-line">
        {data.holdings.map((h) => (
          <li key={h.symbol}>
            <Link href={`/company/${h.symbol}`} className="grid grid-cols-[1fr_72px_84px] items-center gap-3 py-2.5">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="num text-sm font-medium">{h.symbol}</span>
                  {h.critical > 0 && <span className="h-1.5 w-1.5 rounded-full bg-crit" title={`${h.critical} critical this week`} />}
                  <span className="num text-[11px] text-dim">{h.weight.toFixed(0)}%</span>
                </div>
                <div className="truncate text-xs text-dim">
                  {h.pillars_touched.length ? `Pillar touched: ${h.pillars_touched.join(", ").replace(/_/g, " ")}` : h.sector}
                </div>
              </div>
              <Spark values={h.spark} />
              <div className="text-right">
                <div className="num text-sm">{h.close?.toLocaleString("en-IN", { maximumFractionDigits: 1 }) ?? "–"}</div>
                <div className={`num text-xs ${tone(h.day_pct)}`}>
                  {pct(h.day_pct)}{h.volume_x && h.volume_x >= 2 ? <span className="text-crit"> {h.volume_x.toFixed(1)}×</span> : null}
                </div>
              </div>
            </Link>
          </li>
        ))}
      </ul>
      {done && done.length > 0 && (
        <section className="mt-8">
          <h2 className="text-sm text-dim">Research: did management deliver what it promised?</h2>
          <ul className="mt-2 divide-y divide-line border-y border-line">
            {done.map((r) => (
              <li key={r.symbol}>
                <Link href={`/research/${r.symbol}`} className="flex items-baseline gap-3 py-2.5">
                  <span className="num w-28 shrink-0 text-sm font-medium">{r.symbol}</span>
                  <span className="truncate text-sm text-dim">{r.name}</span>
                  <span className="num ml-auto shrink-0 text-xs text-dim">{r.targets} target{r.targets === 1 ? "" : "s"}</span>
                </Link>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[11px] text-dim">Works for any NSE symbol, including ones outside the portfolio. These are the symbols researched so far.</p>
        </section>
      )}
    </div>
  );
}
