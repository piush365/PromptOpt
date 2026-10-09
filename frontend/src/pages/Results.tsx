import * as React from "react";
import { ChevronDown, FileText } from "lucide-react";
import { api, type Results as R, type Section, type Table } from "@/lib/api";
import { CATEGORY, CATEGORY_SHORT, GLOSSARY } from "@/lib/labels";
import { InfoTip } from "@/components/ui/tooltip";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { ErrorBox, PageHeader, StageMark } from "@/components/Feedback";
import { PairBars, SingleBars } from "@/components/LazyCharts";
import { cn } from "@/lib/utils";

/* Every number on this page comes from evaluation/FINAL_RESULTS.md (and tokens/token_test.md), parsed by
   GET /api/ui/results. Nothing is typed in here: if the report changes, the page changes. */

const TERM_TIPS: [RegExp, string][] = [
  [/^F1$|macro-F1/i, "Balance of precision and recall, 0 to 1. Higher is better."],
  [/precision/i, "Of the times it said yes (or fired), how often it was right."],
  [/recall/i, "Of the times it should have said yes (or fired), how often it did."],
  [/kappa/i, "Agreement beyond chance. Collapses near 0 when almost every answer is “yes” (the kappa paradox)."],
  [/AC1/i, "Gwet's AC1: an agreement measure that doesn't collapse when one answer dominates."],
  [/task intent/i, "How close the final task wording stays to the original instruction (similarity, 0–1)."],
  [/pass@1/i, "Share of coding tasks whose first answer passes every test."],
  [/CLIP/i, "How well the generated image matches the user's own prompt, scored by the CLIP model."],
  [/TP|FP|FN/, "TP: fired when it should. FP: fired when it shouldn't. FN: didn't fire when it should."],
  [/quality/i, "Blind judge score, 0–10, for the answer."],
  [/task success/i, "Share of answers that do what was asked, checked automatically where possible."],
  [/format/i, "Share of prompts that state an output format (checked by Stage A's detector)."],
  [/fallback/i, "How often Stage C's answer failed validation, so Stage B's result was used."],
];

function tipFor(h: string) {
  return TERM_TIPS.find(([re]) => re.test(h))?.[1];
}

const find = (s: Section[], id: string) => s.find((x) => x.id === id);
const col = (t: Table, re: RegExp) => t.headers.findIndex((h) => re.test(h));
const num = (s: string) => {
  const m = s.replace(/,/g, "").match(/-?[0-9.]+/);
  return m ? Number(m[0]) : NaN;
};
const pretty = (s: string) => s.replace(/ -> /g, " → ").replace(/->/g, "→");
const arrow = (s: string) => s.split("->").map((x) => num(x));

function DataTable({ t, caption }: { t: Table; caption?: string }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-rule">
      <table className="w-full min-w-[32rem] text-left text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead className="bg-sunken text-ink-2">
          <tr>{t.headers.map((h, i) => {
            const tip = tipFor(h);
            return <th key={i} scope="col" className={cn("px-3 py-2 font-medium", i > 0 && "text-right")}>
              <span className="inline-flex items-center">{h}{tip && <InfoTip label={`What is ${h}?`}>{tip}</InfoTip>}</span></th>;
          })}</tr>
        </thead>
        <tbody>
          {t.rows.map((r, i) => (
            <tr key={i} className={cn("border-t border-rule", t.bold[i] && "bg-b-soft/50 font-medium")}>
              {r.map((c, j) => <td key={j} className={cn("px-3 py-2", j > 0 && "tabular text-right font-mono text-[0.8125rem]")}>{pretty(c)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Block({ stage, title, source, children, lead }: { stage?: "A" | "B" | "C" | "R"; title: string; source?: string;
  children: React.ReactNode; lead?: string }) {
  return (
    <section className="min-w-0 rounded-2xl border border-rule bg-surface p-5 shadow-card sm:p-6">
      <header className="mb-4 flex flex-wrap items-center gap-3">
        {stage && <StageMark stage={stage} />}
        <h2 className="font-display text-xl font-semibold">{title}</h2>
        {source && <span className="ml-auto break-all font-mono text-xs text-muted">§ {source}</span>}
      </header>
      {lead && <p className="mb-4 max-w-3xl text-[0.9375rem] text-ink-2">{lead}</p>}
      {children}
    </section>
  );
}

function TokenHero({ t }: { t: NonNullable<R["tokens"]> }) {
  // CI drawn on a 0–60% axis.
  const x = (v: number) => `${(v / 60) * 100}%`;
  return (
    <section className="rounded-2xl border border-rule bg-surface p-6 shadow-card sm:p-8" data-testid="token-hero">
      <p className="eyebrow">Headline · full test split, n = {t.n}</p>
      <div className="mt-3 grid items-end gap-6 lg:grid-cols-[auto_1fr]">
        <div>
          <p className="font-display text-6xl font-semibold tracking-tight text-add sm:text-7xl tabular">−{t.reduction_pct}%</p>
          <p className="mt-1 flex items-center text-lg text-ink-2">total tokens per prompt
            <InfoTip>Input + output (including hidden reasoning), the vague prompt vs the optimized one, on gpt-oss-120b. Mean of the per-prompt changes.</InfoTip></p>
        </div>
        <div className="max-w-xl">
          <div className="relative h-10" role="img" aria-label={`95% confidence interval from ${t.ci_low}% to ${t.ci_high}% reduction`}>
            <div className="absolute inset-x-0 top-1/2 h-px bg-rule-strong" />
            <div className="absolute top-1/2 h-3 -translate-y-1/2 rounded-full bg-add/30" style={{ left: x(t.ci_low), width: `calc(${x(t.ci_high)} - ${x(t.ci_low)})` }} />
            <div className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface bg-add" style={{ left: x(t.reduction_pct) }} />
            {[0, 20, 40, 60].map((v) => <span key={v} className="absolute -bottom-1 -translate-x-1/2 font-mono text-[0.6875rem] text-muted" style={{ left: x(v) }}>{v ? `−${v}` : 0}%</span>)}
          </div>
          <p className="mt-3 flex items-center text-sm text-ink-2">95% CI {t.ci_low}–{t.ci_high}%
            <InfoTip>The true average saving very likely lies in this range, given 482 prompts.</InfoTip></p>
        </div>
      </div>
      {t.input_before !== undefined && (
        <dl className="mt-6 grid gap-4 border-t border-rule pt-5 sm:grid-cols-3">
          <div><dt className="eyebrow">Input tokens</dt><dd className="mt-1 tabular font-mono text-lg">{t.input_before} → <span className="text-del">{t.input_after}</span></dd>
            <dd className="text-sm text-muted">The prompt gets a little longer.</dd></div>
          <div><dt className="eyebrow">Output tokens</dt><dd className="mt-1 tabular font-mono text-lg">{t.output_before} → <span className="text-add">{t.output_after}</span></dd>
            <dd className="text-sm text-muted">Answers get much shorter. That's the saving.</dd></div>
          {t.cost_more !== undefined && (
            <div><dt className="eyebrow">Honest limit</dt><dd className="mt-1 tabular font-mono text-lg">{t.cost_more} of {t.n} cost more</dd>
              <dd className="text-sm text-muted">{t.cost_more_pct}% of prompts, where the answer was already short.</dd></div>
          )}
        </dl>
      )}
    </section>
  );
}

function Headlines({ s }: { s?: Section }) {
  const t = s?.tables[0];
  if (!t) return null;
  return (
    <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-label="Headline numbers">
      {t.rows.map(([what, result], i) => {
        const stage = /Stage A/.test(what) ? "a" : /Stage B/.test(what) ? "b" : /Stage C/.test(what) ? "c" : "ink";
        return (
          <li key={i} className="rounded-xl border border-rule bg-surface p-4 shadow-card">
            <p className="text-sm text-ink-2">{pretty(what)}</p>
            <p className="mt-1 font-display text-xl font-semibold" style={{ color: stage === "ink" ? undefined : `var(--${stage})` }}>{pretty(result)}</p>
          </li>
        );
      })}
    </ul>
  );
}

function AllSections({ sections }: { sections: Section[] }) {
  return (
    <div className="space-y-2">
      {sections.map((s) => (
        <details key={s.id} className="group rounded-xl border border-rule bg-surface">
          <summary className="flex cursor-pointer items-center gap-2 px-4 py-3 font-medium">
            <ChevronDown className="size-4 -rotate-90 transition-transform group-open:rotate-0" aria-hidden />{s.title}
            <span className="ml-auto text-xs text-muted">{s.tables.length ? `${s.tables.length} table${s.tables.length > 1 ? "s" : ""}` : ""}</span>
          </summary>
          <div className="space-y-3 px-4 pb-4 text-[0.9375rem] text-ink-2">
            {s.intro.map((p, i) => <p key={i}>{pretty(p)}</p>)}
            {s.bullets.length > 0 && <ul className="list-disc space-y-1 pl-5">{s.bullets.map((b, i) => <li key={i}>{pretty(b)}</li>)}</ul>}
            {s.tables.map((t, i) => <DataTable key={i} t={t} caption={s.title} />)}
          </div>
        </details>
      ))}
    </div>
  );
}

const LEAD = (source = "evaluation/FINAL_RESULTS.md") =>
  `The final numbers, read live from ${source}. Val was used for tuning; the test split was run once at the end, with Stage A and B frozen.`;

export default function Results() {
  const [d, setD] = React.useState<R | null>(null);
  const [err, setErr] = React.useState<string | null>(null);
  const load = React.useCallback(() => { setErr(null); api.results().then(setD).catch((e) => setErr(e.message)); }, []);
  React.useEffect(load, [load]);

  if (err) return <><PageHeader title="Results" lead={LEAD()} /><ErrorBox message={err} onRetry={load} /></>;
  if (!d) return (
    <div className="space-y-4"><PageHeader title="Results" lead={LEAD()} /><Skeleton className="h-56" />
      <div className="grid gap-3 sm:grid-cols-3"><Skeleton className="h-24" /><Skeleton className="h-24" /><Skeleton className="h-24" /></div></div>
  );

  const S = d.sections;
  const a3 = find(S, "3")?.tables[0];
  const b4 = find(S, "4");
  const rules = find(S, "4.1")?.tables[0];
  const c51 = find(S, "5.1")?.tables[0];
  const c52 = find(S, "5.2")?.tables[0];
  const tok = find(S, "9a")?.tables[0];
  const coding = find(S, "7")?.tables[0];
  const suite = d.suite.models.filter((m) => m.summary);

  const f1 = a3 ? a3.rows.map((r) => ({ name: CATEGORY_SHORT[r[0]] ?? r[0], value: num(r[col(a3, /^F1$/)]) })) : [];
  const fmtCol = b4?.tables[0];
  const fmtData = fmtCol ? fmtCol.rows.filter((r) => !/all/.test(r[0])).map((r) => ({
    name: CATEGORY_SHORT[r[0]] ?? r[0], a: num(r[col(fmtCol, /format: degraded/)]), b: num(r[col(fmtCol, /format: Stage B/)]) })) : [];
  const tokData = tok ? tok.rows.filter((r) => !/all/.test(r[0])).map((r) => {
    const [x, y] = arrow(r[col(tok, /total tokens \(mean\)/)]);
    return { name: CATEGORY_SHORT[r[0]] ?? r[0], a: x, b: y };
  }) : [];
  const ruleData = rules ? rules.rows.filter((r) => /^B0[1-8] /.test(r[0]) && !/change log/.test(r[0]) && r[col(rules, /^F1$/)] !== "-")
    .map((r) => ({ name: r[0].replace(/^(B0\d) /, "$1 "), value: num(r[col(rules, /^F1$/)]) })) : [];

  return (
    <div className="space-y-6">
      <PageHeader title="Results"
        lead={LEAD(d.source)}
        actions={<Badge tone="outline"><FileText /> parsed from the report</Badge>} />

      {d.tokens && <TokenHero t={d.tokens} />}
      <Headlines s={find(S, "1")} />

      <div className="grid gap-6 xl:grid-cols-2">
        {tokData.length > 0 && (
          <Block title="Tokens per category" source="9a" lead="Mean total tokens per prompt. No category costs more on average; the smallest saving is extraction.">
            <PairBars data={tokData} a={{ label: "Vague prompt", color: "var(--viz-vague)" }} b={{ label: "Optimized", color: "var(--viz-opt)" }} />
          </Block>
        )}
        {f1.length > 0 && (
          <Block stage="A" title="Stage A: category detection" source="3"
            lead={`F1 per category on the test split. Accuracy ${find(S, "1")?.tables[0]?.rows.find((r) => /Stage A/.test(r[0]))?.[1] ?? ""}. Most errors are between Q&A, extraction and summary; B08 handles that group.`}>
            <SingleBars data={f1} color="var(--a)" domain={[0, 1]} label="F1 per category" />
          </Block>
        )}
        {fmtData.length > 0 && (
          <Block stage="B" title="Stage B: output format stated" source="4" lead="Share of prompts that state an output format, before and after the rules.">
            <PairBars data={fmtData} unit="%" domain={[0, 100]} a={{ label: "Vague prompt", color: "var(--viz-vague)" }} b={{ label: "After Stage B", color: "var(--viz-opt)" }} />
          </Block>
        )}
        {ruleData.length > 0 && (
          <Block stage="B" title="Per-rule F1 (B01–B08)" source="4.1" lead="Measured against the dataset's LLM-written targets, so 'expected' is the LLM's choice, not a human label. Full table below.">
            <SingleBars data={ruleData} color="var(--b)" domain={[0, 1]} label="F1 per rule" />
          </Block>
        )}
      </div>

      {b4?.tables[1] && (
        <Block stage="B" title="Benchmark with a real model" source="4" lead={b4.intro.find((p) => /benchmark/i.test(p))}>
          <DataTable t={b4.tables[1]} caption="Benchmark" />
        </Block>
      )}
      {rules && <Block stage="B" title="Per-rule accuracy" source="4.1"><DataTable t={rules} caption="Per-rule accuracy" /></Block>}
      {c51 && <Block stage="C" title="Stage C: does the fine-tuned model help?" source="5.1" lead="Zero-shot base model vs the LoRA-trained one: how often its answer is usable."><DataTable t={c51} caption="Zero-shot vs LoRA" /></Block>}
      {c52 && (
        <Block stage="C" title="Ablation: A+B vs A+B+C vs C only" source="5.2"
          lead={pretty(find(S, "5.2")?.bullets.join(" ") ?? "")}>
          <DataTable t={c52} caption="Ablation" />
        </Block>
      )}

      <div className="grid gap-6 xl:grid-cols-2">
        {suite.length > 0 && (
          <Block title="Correctness suite (50 cases)" source="correctness_suite/results.json">
            <ul className="space-y-3">
              {suite.map((m) => (
                <li key={m.id} className="flex flex-wrap items-baseline justify-between gap-2 border-b border-rule pb-3 last:border-0 last:pb-0">
                  <span className="text-ink-2">{m.label}</span>
                  <span className="tabular font-mono text-sm">{m.summary!.vague}/{m.summary!.n} → <b>{m.summary!.optimized}/{m.summary!.n}</b> correct · p {m.summary!.mcnemar_p.toFixed(3)}</span>
                </li>
              ))}
            </ul>
          </Block>
        )}
        {coding && <Block title="Coding: tests in a sandbox" source="7"><DataTable t={coding} caption="Coding pass@1" /></Block>}
      </div>

      <section>
        <h2 className="mb-3 font-display text-xl font-semibold">Everything in the report</h2>
        <AllSections sections={S} />
      </section>
      <p className="text-sm text-muted">Terms: {GLOSSARY.length} explained on <a href="/how#glossary" className="underline underline-offset-4">How it works</a>. Categories: {Object.values(CATEGORY).slice(1, 6).join(", ")}.</p>
    </div>
  );
}
