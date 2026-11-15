"use client";
import Link from "next/link";
import { Problem, Skeleton } from "@/components/bits";
import { type AlertItem, words } from "@/lib/api";
import { useLoad } from "@/lib/useLoad";

type Rules = { volume_multiple: number; volume_window: number; price_move_pct: number; material_categories: string[] };

export default function Alerts() {
  const { data, error } = useLoad<AlertItem[]>("/alerts", "alerts.json");
  const rules = useLoad<Rules>("/rules", "rules.json").data;
  if (error) return <Problem text={error} />;
  if (!data) return <Skeleton text="Loading alerts…" />;
  return (
    <div>
      <h1 className="text-xl font-semibold">Alerts</h1>
      {rules && (
        <p className="mt-1 text-xs text-dim">
          Fires on volume above <span className="num text-text">{rules.volume_multiple}×</span> the {rules.volume_window}-day average,
          a close-to-close move beyond <span className="num text-text">±{rules.price_move_pct}%</span>, and{" "}
          {rules.material_categories.map(words).join(", ")} filings. One alert per rule, per stock, per day.
        </p>
      )}
      {data.length === 0 && <p className="mt-6 text-sm text-dim">No alerts in this period. Nothing crossed your thresholds.</p>}
      <ul className="mt-4 divide-y divide-line border-y border-line">
        {data.map((a, i) => (
          <li key={i}>
            <Link href={`/company/${a.symbol}`} className="flex items-baseline gap-3 py-2.5">
              <time className="num w-14 shrink-0 text-xs text-dim">{new Date(a.d).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}</time>
              <span className={`text-sm ${a.rule === "combo" ? "text-crit" : ""}`}>{a.headline}</span>
              {a.folded > 0 && <span className="num ml-auto text-xs text-dim">+{a.folded} more</span>}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
