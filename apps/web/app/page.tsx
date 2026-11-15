"use client";
import Link from "next/link";
import { useState } from "react";
import { Direction, FilingCard, Problem, Skeleton, Status } from "@/components/bits";
import type { Brief } from "@/lib/api";
import { useLoad } from "@/lib/useLoad";

const WINDOWS = [["24h", "24 hours"], ["3d", "3 days"], ["7d", "7 days"]] as const;

export default function BriefPage() {
  const [win, setWin] = useState<(typeof WINDOWS)[number][0]>("24h");
  const [open, setOpen] = useState(false);
  const { data, source, error } = useLoad<Brief>(`/brief?window=${win}`, `brief_${win}.json`);

  return (
    <div className="space-y-5">
      <div className="flex gap-1" role="group" aria-label="Time window">
        {WINDOWS.map(([id, label]) => (
          <button key={id} onClick={() => setWin(id)} aria-pressed={win === id}
            className={`rounded-full px-3 py-1 text-xs ${win === id ? "bg-text text-ink" : "bg-panel text-dim"}`}>{label}</button>
        ))}
      </div>

      {error && <Problem text={error} />}
      {!data && !error && <Skeleton text="Reading the last filings…" />}
      {data && (
        <>
          <header>
            <h1 className="text-[26px] font-semibold leading-[1.15] tracking-tight">{data.headline}</h1>
            <div className="mt-2"><Status source={source} asOf={data.as_of} sample={data.sample} /></div>
            {data.note && <p className="mt-1 text-xs text-dim">{data.note}</p>}
          </header>

          {data.needs_attention.length > 0 && (
            <section aria-labelledby="attn">
              <h2 id="attn" className="mb-2 text-sm text-dim">Needs attention</h2>
              <ul className="divide-y divide-line border-y border-line">
                {data.needs_attention.map((h) => (
                  <li key={h.symbol}>
                    <Link href={`/company/${h.symbol}`} className="flex items-baseline gap-2 py-2">
                      <span className="num w-24 shrink-0 text-sm font-medium">{h.symbol}</span>
                      <Direction d={h.direction} />
                      <span className="truncate text-sm text-dim">{h.reasons.map((r) => r.replace(new RegExp(`^${h.symbol}:? `), "")).join("; ")}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {data.critical.length > 0 && (
            <section aria-labelledby="crit" className="space-y-2">
              <h2 id="crit" className="text-sm text-crit">Critical</h2>
              {data.critical.map((c) => <FilingCard key={c.id} c={c} full />)}
            </section>
          )}

          {data.notable.length > 0 && (
            <section aria-labelledby="note" className="space-y-px">
              <h2 id="note" className="mb-2 text-sm text-dim">Notable</h2>
              {data.notable.map((c) => <FilingCard key={c.id} c={c} />)}
            </section>
          )}

          {data.routine.length > 0 && (
            <section>
              <button onClick={() => setOpen(!open)} aria-expanded={open}
                className="flex w-full items-center justify-between bg-panel px-3 py-3 text-left text-sm text-dim">
                <span><span className="num text-text">{data.routine.length}</span> routine filing{data.routine.length > 1 ? "s" : ""}, nothing to act on</span>
                <span aria-hidden>{open ? "−" : "+"}</span>
              </button>
              {open && (
                <ul className="divide-y divide-line border-b border-line">
                  {data.routine.map((c) => (
                    <li key={c.id} className="flex gap-2 py-2 text-xs text-dim">
                      <span className="num w-24 shrink-0">{c.symbol}</span><span className="truncate">{c.headline || c.subject}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
}
