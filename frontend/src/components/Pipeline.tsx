import * as React from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Check, CircleSlash, Columns2, FlaskConical, HelpCircle, Loader2, ShieldCheck, X } from "lucide-react";
import { api, type CodingTests, type OptimizeResult, type Target, type TokenCount } from "@/lib/api";
import { useStore } from "@/lib/store";
import { CATEGORY, CATEGORY_SHORT, ISSUE, STAGE, TARGET, ruleInfo } from "@/lib/labels";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { InfoTip, Tooltip } from "@/components/ui/tooltip";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { CopyButton, ErrorBox, StageMark } from "@/components/Feedback";
import { Diff } from "@/components/Diff";
import { cn } from "@/lib/utils";

type StageKey = "A" | "B" | "C" | "R";
const LINE = { A: "bg-a", B: "bg-b", C: "bg-c", R: "bg-ink" } as const;

/** One stop on the rail: the stage dot, the line to the next stop, and the card. */
function Stop({ stage, title, status, last, children, index, skipped, testid }: {
  stage: StageKey; title: React.ReactNode; status?: React.ReactNode; last?: boolean; children: React.ReactNode;
  index: number; skipped?: boolean; testid?: string;
}) {
  return (
    <li
      style={{ animationDelay: `${index * 120}ms` }}
      className="rise relative grid grid-cols-[2rem_1fr] gap-x-3 sm:grid-cols-[2.25rem_1fr] sm:gap-x-4"
      data-testid={testid}
    >
      <div className="relative flex justify-center">
        <StageMark stage={stage} className={cn("relative z-10 mt-4", skipped && "bg-surface text-muted ring-2 ring-rule-strong dark:text-muted")} />
        {!last && (
          <span
            aria-hidden
            style={{ animationDelay: `${index * 120 + 150}ms` }}
            className={cn("grow-y absolute top-11 bottom-[-1rem] w-[3px] origin-top rounded-full", skipped ? "bg-rule-strong" : LINE[stage])}
          />
        )}
      </div>
      <section className={cn("mb-4 min-w-0 rounded-xl border bg-surface shadow-card", skipped ? "border-dashed border-rule-strong" : "border-rule")}
        aria-labelledby={`stage-${stage}`}>
        <header className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 pt-3.5 pb-2 sm:px-5">
          <span className="eyebrow" style={{ color: `var(--${STAGE[stage].color})` }}>
            {stage === "R" ? "Render" : `Stage ${stage}`}
          </span>
          <h2 id={`stage-${stage}`} className="font-display text-lg font-semibold">{title}</h2>
          <InfoTip label={`About ${stage === "R" ? "rendering" : `Stage ${stage}`}`}>{STAGE[stage].one}</InfoTip>
          <div className="ml-auto flex flex-wrap items-center gap-1.5">{status}</div>
        </header>
        <div className="px-4 pb-4 sm:px-5">{children}</div>
      </section>
    </li>
  );
}

function Bar({ value, tone, gate }: { value: number; tone: string; gate?: number }) {
  return (
    <div className="relative h-2 w-full overflow-hidden rounded-full bg-sunken">
      <div className={cn("grow-x h-full rounded-full", tone)} style={{ width: `${Math.max(1, value * 100)}%` }} />
      {gate !== undefined && <span aria-hidden className="absolute inset-y-0 w-0.5 bg-ink/60" style={{ left: `${gate * 100}%` }} />}
    </div>
  );
}

function issueChips(r: OptimizeResult) {
  return r.issues.map((i) => {
    const phrases = [...i.issue.matchAll(/'([^']+)'/g)].map((m) => m[1]);
    const label = i.code === "A03" ? i.issue.replace(/^No /, "No ").replace(/ stated$/, "")
      : i.code === "A04" ? `Filler: ${phrases.join(", ")}`
      : i.code === "A05" ? `Unclear: ${phrases.join(", ")}`
      : ISSUE[i.code]?.title ?? i.issue;
    return { ...i, label, phrases, tip: ISSUE[i.code]?.tip ?? i.issue };
  });
}

function sourceBadge(source: string) {
  if (source === "user") return <Badge tone="outline">your choice</Badge>;
  if (source === "stage_c") return <Badge tone="c">Stage C</Badge>;
  if (source === "group") return <Badge tone="b">group fallback</Badge>;
  return <Badge tone="a">detected</Badge>;
}

export function StageACard({ r, onHighlight, index }: { r: OptimizeResult; onHighlight: (p: string[]) => void; index: number }) {
  const a = r.stage_a, c = r.category;
  const scores = Object.entries(a.scores).sort((x, y) => y[1] - x[1]);
  const chips = issueChips(r);
  const found = [...a.format_evidence, ...a.constraints_present];
  const sure = a.confidence >= 0.6;
  return (
    <Stop stage="A" index={index} title="What kind of task is this?" testid="stage-a"
      status={<Badge tone={sure ? "a" : "c"}>{sure ? "confident" : "unsure"}</Badge>}>
      <div className="grid gap-5 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div>
          <p className="flex flex-wrap items-center gap-2">
            <span className="font-display text-2xl font-semibold">{CATEGORY[c.used] ?? c.used}</span>
            {sourceBadge(c.source)}
            {typeof r.ir.category_group === "string" && r.ir.category_group && <Badge tone="b">answered from the text (B08)</Badge>}
          </p>
          <div className="mt-3">
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className="flex items-center text-ink-2">Confidence
                <InfoTip>How sure Stage A is, 0 to 1. The line marks 0.6: below it, category-specific rules don't run and only safe, shared fixes are applied.</InfoTip>
              </span>
              <span className="tabular font-mono font-medium">{a.confidence.toFixed(2)}</span>
            </div>
            <Bar value={a.confidence} tone={sure ? "bg-a" : "bg-c"} gate={0.6} />
            <p className="mt-1 text-xs text-muted">Stage A: {CATEGORY[a.category] ?? a.category}{c.source === "user" ? "" : " · gate at 0.6"}</p>
          </div>
          {c.disagreement && (
            <p className="mt-3 rounded-lg bg-c-soft px-3 py-2 text-sm text-ink">
              You chose <b>{CATEGORY[c.used]}</b>; Stage A thought <b>{CATEGORY[c.stage_a] ?? c.stage_a}</b>. Your choice was used.
            </p>
          )}
        </div>
        <div>
          <p className="mb-1.5 flex items-center text-sm text-ink-2">All category scores
            <InfoTip>Stage A's score for every category. They add up to 1.</InfoTip></p>
          <ul className="space-y-1.5" aria-label="Category scores">
            {scores.map(([k, v]) => (
              <li key={k} className="grid grid-cols-[5.5rem_1fr_2.75rem] items-center gap-2 text-sm">
                <span className={cn("truncate", k === a.category ? "font-medium text-ink" : "text-muted")} title={CATEGORY[k]}>{CATEGORY_SHORT[k] ?? k}</span>
                <Bar value={v} tone={k === a.category ? "bg-a" : "bg-rule-strong"} />
                <span className="tabular text-right font-mono text-xs text-muted">{(v * 100).toFixed(0)}%</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="mt-4 border-t border-rule pt-3">
        <p className="mb-2 flex items-center text-sm text-ink-2">What's missing or unclear
          <InfoTip>Hover or focus a chip to see the words it's about, highlighted in your prompt.</InfoTip></p>
        {chips.length ? (
          <ul className="flex flex-wrap gap-2" data-testid="issues">
            {chips.map((ch, i) => (
              <li key={i}>
                <Tooltip content={ch.tip}>
                  <button
                    type="button"
                    onMouseEnter={() => onHighlight(ch.phrases)}
                    onMouseLeave={() => onHighlight([])}
                    onFocus={() => onHighlight(ch.phrases)}
                    onBlur={() => onHighlight([])}
                    className="inline-flex items-center gap-1.5 rounded-full border border-a/30 bg-a-soft px-3 py-1 text-sm text-ink transition-colors hover:border-a"
                  >
                    <span className="font-mono text-[0.6875rem] text-a">{ch.code}</span>{ch.label}
                  </button>
                </Tooltip>
              </li>
            ))}
          </ul>
        ) : <p className="text-sm text-muted">Nothing: the prompt already states a format and the constraints it needs.</p>}
        {found.length > 0 && (
          <p className="mt-2 text-sm text-muted">Already stated:{" "}
            {found.map((f) => (
              <button key={f} type="button" onMouseEnter={() => onHighlight([f])} onMouseLeave={() => onHighlight([])}
                onFocus={() => onHighlight([f])} onBlur={() => onHighlight([])}
                className="mr-1.5 rounded-md border border-rule px-1.5 font-mono text-xs text-ink-2">{f}</button>
            ))}
          </p>
        )}
      </div>
    </Stop>
  );
}

export function StageBCard({ r, index }: { r: OptimizeResult; index: number }) {
  return (
    <Stop stage="B" index={index} title="Rules that fired" testid="stage-b"
      status={<Badge tone="b">{r.rules.length} {r.rules.length === 1 ? "change" : "changes"}</Badge>}>
      {r.rules.length ? (
        <ol className="relative space-y-4 border-l-2 border-b/25 pl-4" data-testid="rules">
          {r.rules.map((x, i) => {
            const info = ruleInfo(x.code, x.what);
            return (
              <li key={i} className="relative">
                <span aria-hidden className="absolute -left-[1.4rem] top-1.5 size-2.5 rounded-full border-2 border-surface bg-b" />
                <div className="mb-1 flex flex-wrap items-baseline gap-x-2">
                  <Badge tone="b">{info.short}</Badge>
                  <span className="font-medium">{info.name}</span>
                  <span className="text-sm text-muted">{info.why}</span>
                </div>
                <Diff before={x.before} after={x.after} />
              </li>
            );
          })}
        </ol>
      ) : <p className="text-sm text-muted">No rule changed the prompt: it was already clear.</p>}
      {r.unresolved_after_b.length > 0 && (
        <p className="mt-3 flex flex-wrap items-center gap-1.5 text-sm text-ink-2">
          Left unresolved:
          {r.unresolved_after_b.map((u) => <Badge key={u} tone="c">{u}</Badge>)}
          <InfoTip>What the rules couldn't fix. Only the task category and unclear references are sent to Stage C; the rest is recorded.</InfoTip>
        </p>
      )}
    </Stop>
  );
}

function ConfirmCategory({ r }: { r: OptimizeResult }) {
  const { setDraft, requestRun } = useStore();
  const guess = r.category.guess ?? r.stage_a.category;
  const others = ["closed_qa", "information_extraction", "classification", "summarization", "coding"].filter((c) => c !== guess);
  const pick = (c: string) => { setDraft({ category: c as never }); requestRun(); };
  return (
    <div className="mt-3 rounded-xl border border-c/40 bg-c-soft p-4" data-testid="confirm-category">
      <p className="flex items-center gap-2 font-medium"><HelpCircle className="size-4 text-c" aria-hidden />
        Is this a “{CATEGORY[guess] ?? guess}” task?</p>
      <p className="mt-1 text-sm text-ink-2">
        {r.category.uncertain
          ? `Stage A wasn't sure (${CATEGORY[r.stage_a.category] ?? r.stage_a.category}, ${r.stage_a.confidence.toFixed(2)}). Stage C suggests ${CATEGORY[guess] ?? guess}. Confirm it, or pick the right one, and the prompt is rebuilt with that category's rules.`
          : `Stage A wasn't sure (${r.stage_a.confidence.toFixed(2)}), so only safe, general fixes were applied. Pick the category to get its format and constraints too.`}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" variant="primary" onClick={() => pick(guess)}><Check aria-hidden /> Yes, {CATEGORY[guess] ?? guess}</Button>
        {others.map((c) => <Button key={c} size="sm" variant="secondary" onClick={() => pick(c)}>{CATEGORY[c]}</Button>)}
      </div>
    </div>
  );
}

export function StageCCard({ r, index }: { r: OptimizeResult; index: number }) {
  const s = r.stage_c;
  const forCategory = s.reasons.some((x) => x.startsWith("task category"));
  const askUser = r.category.uncertain || (forCategory && !s.accepted && r.category.source !== "user");
  let status: React.ReactNode, body: React.ReactNode;
  if (!s.routed) {
    status = <Badge tone="outline">not needed</Badge>;
    body = <p className="text-sm text-muted">The rules resolved everything Stage C could fix, so the small model wasn't called. (It runs on about 6% of prompts.)</p>;
  } else {
    const why = (
      <div className="text-sm">
        <p className="text-ink-2">Sent here because the rules left these unresolved:</p>
        <ul className="mt-1.5 flex flex-wrap gap-1.5">{s.reasons.map((x) => <li key={x}><Badge tone="c">{x}</Badge></li>)}</ul>
      </div>
    );
    if (!s.available) {
      status = <Badge tone="c">fallback</Badge>;
      body = (<>{why}
        <p className="mt-3 flex items-start gap-2 rounded-lg bg-sunken px-3 py-2 text-sm text-ink-2">
          <CircleSlash className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />
          Stage C isn't loaded on this server, so Stage B's result is shown. Run the app from <code className="font-mono text-xs">.venv-gpu</code> to turn it on.
        </p></>);
    } else if (s.accepted) {
      status = <Badge tone="c">used · {s.seconds}s</Badge>;
      body = (<>{why}
        <p className="mt-3 text-sm text-ink-2">Filled: {s.fields.map((f) => <Badge key={f} tone="c" className="mr-1">{f}</Badge>)}</p>
        <ul className="mt-2 grid gap-1 text-sm sm:grid-cols-3" aria-label="Validation checks">
          {["Valid JSON", "Exactly the fields asked for", "Passes Stage A's checks"].map((t) => (
            <li key={t} className="flex items-center gap-1.5"><Check className="size-4 text-b" aria-label="passed" />{t}</li>))}
        </ul></>);
    } else {
      status = <Badge tone="del">rejected · fallback</Badge>;
      body = (<>{why}
        <p className="mt-3 text-sm text-ink-2">Stage C answered, but its answer failed validation, so Stage B's result is kept:</p>
        <ul className="mt-1 space-y-1 text-sm">{s.errors.map((e) => (
          <li key={e} className="flex items-start gap-1.5"><X className="mt-0.5 size-4 shrink-0 text-del" aria-label="failed" />{e}</li>))}</ul></>);
    }
  }
  return (
    <Stop stage="C" index={index} title={s.routed ? "Small model" : "Small model: skipped"} status={status} skipped={!s.routed || !s.available} testid="stage-c">
      {body}
      {askUser && <ConfirmCategory r={r} />}
      {s.raw && (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer text-muted hover:text-ink">Stage C's raw answer</summary>
          <pre className="proof mt-2 rounded-lg bg-sunken p-3 text-xs">{s.raw}</pre>
        </details>
      )}
    </Stop>
  );
}

function CodingTestsPanel({ r }: { r: OptimizeResult }) {
  const ct = r.coding_tests!;
  const [gen, setGen] = React.useState<CodingTests | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);
  const t = gen ?? ct.tests;
  const generate = async () => {
    setBusy(true); setErr(null);
    try { setGen(await api.codingTests(r.optimized_plain)); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <div className="mt-4 rounded-xl border border-rule p-4">
      <p className="flex flex-wrap items-center gap-2 font-medium"><FlaskConical className="size-4 text-muted" aria-hidden /> Tests for this task
        {t && (t.validated ? <Badge tone="b"><ShieldCheck /> validated</Badge> : <Badge tone="c">not validated</Badge>)}
        <InfoTip>Validated tests pass on the dataset's reference solution. Compare runs both answers against them in a sandbox.</InfoTip>
      </p>
      {t ? (
        <>
          <pre className="proof mt-2 max-h-48 overflow-auto rounded-lg bg-sunken p-3 text-xs">{t.mode === "stdout"
            ? `# output must equal:\n${t.expected_stdout ?? ""}` : [t.signature ? `# ${t.signature}` : `# function: ${t.function}`, ...t.tests].join("\n")}</pre>
          <p className="mt-1 text-xs text-muted">{t.note}</p>
        </>
      ) : (
        <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-muted">
          <span>{ct.can_generate ? "No validated tests: this prompt isn't from the dataset." : "No validated tests, and generating them needs CEREBRAS_API_KEY in backend/.env."}</span>
          {ct.can_generate && <Button size="sm" onClick={generate} disabled={busy}>{busy && <Loader2 className="animate-spin" />}Generate unvalidated tests</Button>}
        </div>
      )}
      {err && <ErrorBox className="mt-2" message={err} />}
    </div>
  );
}

export function RenderCard({ r, index, originalTokens }: { r: OptimizeResult; index: number; originalTokens?: Record<Target, TokenCount> | null }) {
  const [tab, setTab] = React.useState<Target>(r.target);
  const navigate = useNavigate();
  React.useEffect(() => setTab(r.target), [r]);
  const targets: Target[] = ["gpt", "gemini", "claude"];
  return (
    <Stop stage="R" index={index} title="Your optimized prompt" last testid="render"
      status={<Badge tone="outline">{r.renderings[r.target].split(/\n/).length} lines</Badge>}>
      <Tabs value={tab} onValueChange={(v) => setTab(v as Target)}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <TabsList aria-label="Rendering per model">
            {targets.map((t) => (
              <TabsTrigger key={t} value={t}>
                {TARGET[t]}{t === r.target && <span className="size-1.5 rounded-full bg-b" aria-label="(your target)" />}
              </TabsTrigger>
            ))}
          </TabsList>
          <div className="flex items-center gap-2">
            <CopyButton text={r.renderings[tab]} what={`${TARGET[tab]} prompt`} />
            <Button size="sm" variant="primary" onClick={() => navigate("/compare")} data-testid="compare-this">
              <Columns2 aria-hidden /> Compare this
            </Button>
          </div>
        </div>
        {targets.map((t) => {
          const tk = r.tokens[t], o = originalTokens?.[t];
          return (
            <TabsContent key={t} value={t} className="mt-3 outline-none">
              <pre className="proof max-h-[28rem] overflow-auto rounded-xl border border-rule bg-sunken/70 p-4 text-ink" data-testid={`rendering-${t}`}>{r.renderings[t]}</pre>
              <p className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted">
                <span className="tabular font-mono font-medium text-ink">{tk.exact ? "" : "≈"}{tk.tokens}</span> input tokens
                <Badge tone={tk.exact ? "b" : "outline"}>{tk.exact ? "exact" : "approx."}</Badge>
                {o && <span>· your prompt: {o.exact ? "" : "≈"}{o.tokens}</span>}
                <InfoTip>{tk.method}. The prompt usually gets a little longer; the saving comes from much shorter answers. Compare measures both.</InfoTip>
                <span className="ml-auto hidden items-center gap-1 sm:flex">Same content, laid out for {TARGET[t]} <ArrowRight className="size-3.5" aria-hidden /></span>
              </p>
            </TabsContent>
          );
        })}
      </Tabs>
      {r.coding_tests && <CodingTestsPanel r={r} />}
    </Stop>
  );
}

/** Shown while the request runs: the rail with skeleton cards and the stage being worked on. */
export function PipelineSkeleton() {
  const steps: { s: StageKey; label: string }[] = [
    { s: "A", label: "Detecting the task and what's missing" },
    { s: "B", label: "Applying rules" },
    { s: "C", label: "Checking whether the small model is needed" },
    { s: "R", label: "Writing it out for GPT, Gemini and Claude" },
  ];
  const [active, setActive] = React.useState(0);
  React.useEffect(() => {
    const t = setInterval(() => setActive((a) => Math.min(a + 1, steps.length - 1)), 650);
    return () => clearInterval(t);
  }, [steps.length]);
  return (
    <div role="status" aria-live="polite" aria-label="Optimizing" data-testid="pipeline-loading">
      <ol>
        {steps.map((st, i) => (
          <li key={st.s} className="grid grid-cols-[2rem_1fr] gap-x-3 sm:grid-cols-[2.25rem_1fr] sm:gap-x-4">
            <div className="relative flex justify-center">
              <StageMark stage={st.s} className={cn("mt-4 transition-opacity", i > active && "opacity-30")} />
              {i < steps.length - 1 && <span aria-hidden className={cn("absolute top-11 bottom-[-1rem] w-[3px] rounded-full", i < active ? LINE[st.s] : "bg-rule")} />}
            </div>
            <div className="mb-4 rounded-xl border border-rule bg-surface p-4 shadow-card">
              <p className={cn("flex items-center gap-2 text-sm", i === active ? "text-ink" : "text-muted")}>
                {i === active && <Loader2 className="size-4 animate-spin" aria-hidden />}{st.label}{i === active ? "…" : ""}
              </p>
              <Skeleton className="mt-3 h-3 w-2/3" />
              <Skeleton className="mt-2 h-3 w-1/2" />
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
