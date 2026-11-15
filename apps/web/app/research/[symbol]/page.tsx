"use client";
import { use } from "react";
import { Problem, Skeleton } from "@/components/bits";
import { useLoad } from "@/lib/useLoad";

type Item = { metric: string; kind: "growth" | "margin" | "absolute"; low: number; high: number; period: string; stated_in: string; speaker: string; quote: string; document: string; page: number };
type Verdict = { item: Item; status: string; actual: number | null; actual_basis: string; progress: string; note: string; replaced_by: Item | null };
type Doc = { label: string; period: string; url: string; pages: number; extracted: number; kept: number; error?: string; dropped: { label: string; why: string; quote: string }[] };
type Research = {
  symbol: string; name: string; basis: string; source_page: string; actuals_note: string; latest_quarter: string | null; error?: string;
  documents: Doc[]; scorecard: Verdict[]; facts: { metric: string; value: number; period: string; period_type: string }[];
};

const STATUS: Record<string, [string, string]> = {
  delivered: ["Delivered", "text-up border-up"], partially_delivered: ["Partially delivered", "text-crit border-crit"],
  missed: ["Missed", "text-down border-down"], pending: ["Pending", "text-text border-dim"], revised: ["Revised", "text-crit border-crit"],
  withdrawn: ["Withdrawn", "text-down border-down"], not_verifiable: ["Not verifiable", "text-dim border-line"],
};
const P = (p: string) => p.replace("_", " ");
const METRIC: Record<string, string> = { revenue: "Revenue", ebitda: "EBITDA", pat: "PAT", capex: "Capex", order_inflow: "Order inflow", total_income: "Total income" };

function target(i: Item) {
  const range = i.low === i.high ? `${i.low}` : `${i.low}–${i.high}`;
  const m = METRIC[i.metric] ?? i.metric;
  if (i.kind === "growth") return `${m} growth of ${range}% in ${P(i.period)}`;
  if (i.kind === "margin") return `${m} margin of ${range}% in ${P(i.period)}`;
  return `${m} of ₹${range} cr in ${P(i.period)}`;
}

function Row({ v }: { v: Verdict }) {
  const [label, cls] = STATUS[v.status] ?? [v.status, "text-dim border-line"];
  const unit = v.item.kind === "absolute" ? " cr" : "%";
  return (
    <article className="bg-panel px-3 py-3">
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-sm leading-snug">{target(v.item)}</h3>
        <span className={`shrink-0 rounded-sm border px-1.5 text-[11px] leading-5 ${cls}`}>{label}</span>
      </div>
      <blockquote className="mt-2 border-l border-line pl-2 text-xs leading-relaxed text-dim">
        “{v.item.quote}”
        <footer className="mt-1 flex flex-wrap items-center gap-2 not-italic">
          <span className="ev ev-guidance">Guidance</span>
          <a className="underline decoration-line underline-offset-4" href={`${v.item.document}#page=${v.item.page}`} target="_blank" rel="noreferrer">
            {P(v.item.stated_in)} call, page {v.item.page}
          </a>
          {v.item.speaker && <span>{v.item.speaker}</span>}
        </footer>
      </blockquote>
      {v.actual != null && (
        <p className="mt-2 flex flex-wrap items-center gap-2 text-xs">
          <span className="ev ev-reported">Reported</span>
          <span className="num text-sm text-text">{v.actual.toLocaleString("en-IN")}{unit}</span>
          <span className="text-dim">{v.actual_basis}</span>
        </p>
      )}
      {v.progress && <p className="mt-2 text-xs"><span className="ev ev-reported mr-2">Reported</span><span className="num">{v.progress}</span> <span className="text-dim">so far. Judged only on the full period.</span></p>}
      {v.replaced_by && <p className="mt-2 text-xs text-dim">Changed to <span className="text-text">{target(v.replaced_by)}</span> on the {P(v.replaced_by.stated_in)} call.</p>}
      {v.note && <p className="mt-2 text-xs text-dim">{v.note}</p>}
    </article>
  );
}

function Trend({ r }: { r: Research }) {
  const qs = [...new Set(r.facts.filter((f) => f.period_type === "quarterly").map((f) => f.period))]
    .sort((a, b) => (a.slice(-2) + a[1]).localeCompare(b.slice(-2) + b[1])).slice(-5);
  const rows = ["revenue", "total_income", "ebitda", "pat"].filter((m) => r.facts.some((f) => f.metric === m && qs.includes(f.period)));
  if (!qs.length) return null;
  const val = (m: string, q: string) => r.facts.find((f) => f.metric === m && f.period === q)?.value;
  return (
    <section>
      <h2 className="mb-2 text-sm text-dim">Last {qs.length} quarters, ₹ crore, {r.basis}</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-right text-xs">
          <thead><tr className="text-dim"><th className="text-left font-normal" />{qs.map((q) => <th key={q} className="num px-1 py-1 font-normal">{P(q)}</th>)}</tr></thead>
          <tbody className="divide-y divide-line border-y border-line">
            {rows.map((m) => (
              <tr key={m}><th className="py-1.5 text-left font-normal">{METRIC[m]}</th>
                {qs.map((q) => <td key={q} className="num px-1">{val(m, q)?.toLocaleString("en-IN") ?? "–"}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[11px] text-dim">{r.actuals_note} <a className="underline" href={r.source_page} target="_blank" rel="noreferrer">Source table</a></p>
    </section>
  );
}

export default function ResearchPage({ params }: { params: Promise<{ symbol: string }> }) {
  const symbol = use(params).symbol.toUpperCase();
  const { data: r, error } = useLoad<Research>(`/research/${symbol}`, `research_${symbol}.json`);
  if (error) return <Problem text={`No stored research for ${symbol} yet. Research is produced by the ingestion run for a ticker.`} />;
  if (!r) return <Skeleton text={`Reading ${symbol} transcripts…`} />;
  if (r.error) return <Problem text={r.error} />;
  const order = ["missed", "partially_delivered", "revised", "withdrawn", "delivered", "pending", "not_verifiable"];
  const cards = [...r.scorecard].sort((a, b) => order.indexOf(a.status) - order.indexOf(b.status));
  const read = r.documents.filter((d) => !d.error);
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold">{r.name}</h1>
        <p className="text-xs text-dim">{r.symbol} · research from {read.length} earnings-call transcript{read.length === 1 ? "" : "s"} and filed financials</p>
      </header>
      <section className="space-y-2">
        <h2 className="text-sm text-dim">Promised vs delivered</h2>
        {cards.length === 0 && (
          <p className="bg-panel px-3 py-4 text-sm text-dim">
            No quantified targets were found in the transcripts read. FINN does not infer targets that management did not state.
          </p>
        )}
        {cards.map((v, i) => <Row key={i} v={v} />)}
      </section>
      <Trend r={r} />
      <section>
        <h2 className="mb-2 text-sm text-dim">What was read</h2>
        <ul className="divide-y divide-line border-y border-line text-xs">
          {r.documents.map((d) => (
            <li key={d.url} className="flex items-baseline gap-2 py-2">
              <a className="underline decoration-line underline-offset-4" href={d.url} target="_blank" rel="noreferrer">{P(d.period)} call ({d.label})</a>
              <span className="ml-auto text-right text-dim">
                {d.error ?? <><span className="num">{d.pages}</span> pages, <span className="num">{d.kept}</span> target{d.kept === 1 ? "" : "s"} kept{d.dropped.length > 0 && <>, <span className="num">{d.dropped.length}</span> dropped</>}</>}
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-[11px] text-dim">A target is kept only if its quote is found in the transcript and it has a metric FINN can check against filed numbers.</p>
      </section>
    </div>
  );
}
