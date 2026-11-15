"use client";
import { when } from "@/lib/api";
import { useLoad } from "@/lib/useLoad";

type Health = { snapshot: string | null; generated_at?: string | null; sources: Record<string, string>; llm?: boolean };
const NAMES: Record<string, string> = { prices: "Prices (Yahoo Finance, end of day)", nse: "NSE announcements", bse: "BSE announcements" };

// Each source reports its own last run, so a stale or blocked source is visible instead of silently missing.
export default function Sources() {
  const { data } = useLoad<Health>("/health", "meta.json");
  if (!data) return null;
  const at = data.snapshot ?? data.generated_at;
  return (
    <details className="text-xs text-dim">
      <summary className="cursor-pointer py-2">Where this data came from</summary>
      <ul className="divide-y divide-line border-y border-line">
        {Object.entries(data.sources).map(([k, v]) => {
          const ok = v.startsWith("ok");
          return (
            <li key={k} className="flex items-baseline gap-2 py-2">
              <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${ok ? "bg-up" : "bg-down"}`} />
              <span className="text-text">{NAMES[k] ?? k}</span>
              <span className="ml-auto max-w-[55%] text-right">{ok ? v.replace(/^ok \(|\)$/g, "") : v.split(":")[0].split(";")[0]}</span>
            </li>
          );
        })}
      </ul>
      {at && <p className="mt-2">Last ingestion run <span className="num">{when(at)}</span>. Brief, Portfolio and Alerts read stored data, so they stay up when a source is down.</p>}
    </details>
  );
}
