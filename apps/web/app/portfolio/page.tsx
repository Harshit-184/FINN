"use client";
import Link from "next/link";
import { Problem, Skeleton, Spark } from "@/components/bits";
import { pct, tone, type Holding } from "@/lib/api";
import { useLoad } from "@/lib/useLoad";

export default function Portfolio() {
  const { data, error } = useLoad<{ weights_note: string; holdings: Holding[] }>("/portfolio", "portfolio.json");
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
    </div>
  );
}
