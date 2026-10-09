import * as React from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { CheckCircle2, Clock, Columns2, Gavel, Info, Loader2, Play, ShieldAlert, XCircle } from "lucide-react";
import { api, type CompareHistoryItem, type CompareModel, type CompareResult, type Target, type Variant } from "@/lib/api";
import { useStore } from "@/lib/store";
import { CATEGORY, TARGET, fmt, pct } from "@/lib/labels";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import { Segmented } from "@/components/ui/segmented";
import { InfoTip } from "@/components/ui/tooltip";
import { Skeleton } from "@/components/ui/skeleton";
import { CopyButton, EmptyState, ErrorBox, PageHeader } from "@/components/Feedback";
import { TokenStack } from "@/components/LazyCharts";
import { FIELD_LABEL } from "@/components/Composer";
import { cn, modKey } from "@/lib/utils";

function Delta({ value, big, label }: { value: number | null; big?: boolean; label: string }) {
  const good = value !== null && value < 0, bad = value !== null && value > 0;
  return (
    <span className={cn("tabular font-mono font-semibold", good && "text-add", bad && "text-del", !good && !bad && "text-ink",
      big ? "font-display text-5xl tracking-tight sm:text-6xl" : "text-base")}
      aria-label={`${label}: ${value === null ? "no data" : `${value < 0 ? "down" : "up"} ${Math.abs(value)} percent`}`}>
      {pct(value)}
    </span>
  );
}

function Answer({ title, v, tone, tests }: { title: string; v: Variant; tone: "vague" | "opt";
  tests?: { outcome: string; passed: number; total: number } }) {
  return (
    <section className="flex min-w-0 flex-col rounded-xl border border-rule bg-surface shadow-card" aria-label={title}>
      <header className="flex flex-wrap items-center gap-2 border-b border-rule px-4 py-3">
        <span aria-hidden className="size-2.5 rounded-sm" style={{ background: tone === "vague" ? "var(--viz-vague)" : "var(--viz-opt)" }} />
        <h2 className="font-display text-lg font-semibold">{title}</h2>
        {tests && (
          <Badge tone={tests.passed === tests.total ? "b" : "del"}>
            {tests.passed === tests.total ? <CheckCircle2 /> : <XCircle />} {tests.passed}/{tests.total} tests
          </Badge>
        )}
        <span className="ml-auto"><CopyButton text={v.answer} what="Answer" /></span>
      </header>
      <dl className="grid grid-cols-4 gap-2 border-b border-rule px-4 py-2.5 text-center text-sm">
        {[["in", v.input_tokens], ["out", v.output_tokens], ["total", v.total_tokens], ["time", `${(v.latency_ms / 1000).toFixed(1)} s`]].map(([k, val]) => (
          <div key={k as string}><dt className="eyebrow">{k}</dt><dd className="tabular font-mono font-medium">{typeof val === "number" ? fmt(val) : val}</dd></div>
        ))}
      </dl>
      <pre className="proof max-h-[32rem] flex-1 overflow-auto px-4 py-3 text-ink">{v.answer || "(empty answer)"}</pre>
      {v.finish_reason === "length" && <p className="px-4 pb-3 text-sm text-del">Cut off at the token limit.</p>}
      {v.prompt && (
        <details className="border-t border-rule px-4 py-2 text-sm">
          <summary className="cursor-pointer text-muted hover:text-ink">Prompt that was sent</summary>
          <pre className="proof mt-2 max-h-60 overflow-auto rounded-lg bg-sunken p-3 text-xs">{v.prompt}</pre>
        </details>
      )}
    </section>
  );
}

function Running({ judge, started }: { judge: boolean; started: number }) {
  const [now, setNow] = React.useState(Date.now());
  React.useEffect(() => { const t = setInterval(() => setNow(Date.now()), 500); return () => clearInterval(t); }, []);
  const s = Math.round((now - started) / 1000);
  const steps = ["Optimizing the prompt", "Asking the model with your prompt", "Asking the model with the optimized prompt",
    ...(judge ? ["Blind judge scoring both answers"] : [])];
  return (
    <div role="status" aria-live="polite" className="rounded-xl border border-rule bg-surface p-5 shadow-card" data-testid="compare-running">
      <p className="flex items-center gap-2 font-medium"><Loader2 className="size-4 animate-spin" aria-hidden /> Comparing… <span className="tabular font-mono text-sm text-muted">{s}s</span></p>
      <ol className="mt-3 space-y-1.5 text-sm text-ink-2">
        {steps.map((t) => <li key={t} className="flex items-center gap-2"><span className="size-1.5 rounded-full bg-rule-strong" aria-hidden />{t}</li>)}
      </ol>
      <p className="mt-3 text-sm text-muted">Usually 5–60 seconds: Cerebras spaces calls about 25 s apart to stay in its free quota. Answers already asked are reused from a cache.</p>
      <div className="mt-4 grid gap-4 md:grid-cols-2"><Skeleton className="h-40" /><Skeleton className="h-40" /></div>
    </div>
  );
}

function ResultView({ c }: { c: CompareResult }) {
  const o = c.original, p = c.optimized;
  const rows = [
    { name: "Your prompt", input: o.input_tokens, output: o.output_tokens - (o.reasoning_tokens ?? 0), reasoning: o.reasoning_tokens ?? 0 },
    { name: "Optimized", input: p.input_tokens, output: p.output_tokens - (p.reasoning_tokens ?? 0), reasoning: p.reasoning_tokens ?? 0 },
  ];
  const total = c.change_pct.total_tokens;
  return (
    <div className="space-y-5" data-testid="compare-result">
      <p className="flex items-start gap-2 rounded-xl border border-rule bg-sunken px-4 py-3 text-[0.9375rem] text-ink-2">
        <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
        <span><b className="text-ink">Who answered:</b> {c.label}. Same model for both, temperature {c.settings.temperature}, at most {c.settings.max_tokens} output tokens{c.settings.reasoning_effort ? `, reasoning effort ${c.settings.reasoning_effort}` : ""}.</span>
      </p>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
        <div className="rounded-xl border border-rule bg-surface p-5 shadow-card">
          <p className="eyebrow flex items-center">Total tokens <InfoTip>Input + output (including hidden reasoning), optimized vs your prompt. Green means the optimized prompt cost less overall.</InfoTip></p>
          <Delta value={total} big label="Total token change" />
          <p className="mt-1 text-sm text-muted">{fmt(o.total_tokens)} → {fmt(p.total_tokens)} tokens</p>
          <dl className="mt-4 space-y-2 text-sm">
            {([["Input", c.change_pct.input_tokens, "The optimized prompt is usually longer: it states the format and constraints."],
               ["Output", c.change_pct.output_tokens, "What the model wrote back, including hidden reasoning. This is where savings come from."],
               ["Latency", c.latency_change_pct, "Time until the full answer arrived."]] as const).map(([k, v, tip]) => (
              <div key={k} className="flex items-center justify-between gap-2">
                <dt className="flex items-center text-ink-2">{k}<InfoTip>{tip}</InfoTip></dt><dd><Delta value={v} label={k} /></dd>
              </div>
            ))}
            <div className="flex items-center justify-between gap-2 border-t border-rule pt-2">
              <dt className="flex items-center text-ink-2">Cost<InfoTip>gpt-oss-120b on the Groq/Cerebras free tier costs nothing. On a paid model, cost follows total tokens.</InfoTip></dt>
              <dd className="text-muted">free tier · follows tokens</dd>
            </div>
          </dl>
        </div>
        <div className="rounded-xl border border-rule bg-surface p-5 shadow-card">
          <p className="mb-3 flex items-center font-medium">Where the tokens go<InfoTip>Each bar is one request. Input is what you send; output is what the model writes; reasoning is hidden thinking you still pay for.</InfoTip></p>
          <TokenStack rows={rows} />
          <table className="sr-only">
            <caption>Tokens per request</caption>
            <thead><tr><th>Prompt</th><th>Input</th><th>Output</th><th>Reasoning</th></tr></thead>
            <tbody>{rows.map((r) => <tr key={r.name}><td>{r.name}</td><td>{r.input}</td><td>{r.output}</td><td>{r.reasoning}</td></tr>)}</tbody>
          </table>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {c.judge ? (
              <div className="rounded-lg bg-sunken p-3 text-sm">
                <p className="flex items-center gap-1.5 font-medium"><Gavel className="size-4" aria-hidden /> Blind judge <span className="font-normal text-muted">({c.judge.model})</span>
                  <InfoTip>Another model scored both answers 0–10 without knowing which prompt produced which.</InfoTip></p>
                <p className="mt-1 tabular font-mono">yours {c.judge.original?.score ?? "–"}/10 · optimized {c.judge.optimized?.score ?? "–"}/10</p>
                {c.judge.optimized?.reason && <p className="mt-1 text-muted">{c.judge.optimized.reason}</p>}
              </div>
            ) : <p className="rounded-lg bg-sunken p-3 text-sm text-muted">No judge this time. Tick “Blind judge” to score both answers.</p>}
            {c.tests ? (
              <div className="rounded-lg bg-sunken p-3 text-sm">
                <p className="flex items-center gap-1.5 font-medium"><ShieldAlert className="size-4" aria-hidden /> Sandbox tests
                  <InfoTip>The code in each answer ran against tests that pass on the dataset's reference solution, in a sandbox with no network.</InfoTip></p>
                {c.tests.validated && c.tests.original && c.tests.optimized ? (
                  <p className="mt-1 tabular font-mono">yours {c.tests.original.passed}/{c.tests.original.total} · optimized {c.tests.optimized.passed}/{c.tests.optimized.total}</p>
                ) : <p className="mt-1 text-muted">{c.tests.note ?? "Not run."}</p>}
              </div>
            ) : <p className="rounded-lg bg-sunken p-3 text-sm text-muted">Sandbox tests run only for coding prompts from the dataset.</p>}
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Answer title="Answer to your prompt" v={o} tone="vague" tests={c.tests?.validated ? c.tests.original : undefined} />
        <Answer title="Answer to the optimized prompt" v={p} tone="opt" tests={c.tests?.validated ? c.tests.optimized : undefined} />
      </div>
    </div>
  );
}

function modelName(id: string) {
  const [provider, ...rest] = id.split("/");
  const name = rest[rest.length - 1] ?? id;
  return `${name} · ${provider.charAt(0).toUpperCase()}${provider.slice(1)}`;
}

function PastCompares({ refresh }: { refresh: number }) {
  const [items, setItems] = React.useState<CompareHistoryItem[] | null>(null);
  const [err, setErr] = React.useState<string | null>(null);
  React.useEffect(() => { api.compareHistory().then(setItems).catch((e) => setErr(e.message)); }, [refresh]);
  if (err) return <ErrorBox message={err} />;
  if (!items) return <Skeleton className="h-32" />;
  if (!items.length) return <p className="text-sm text-muted">No comparisons yet. Your runs will be listed here.</p>;
  return (
    <div className="overflow-x-auto rounded-xl border border-rule bg-surface shadow-card">
      <table className="w-full min-w-[34rem] table-fixed text-left text-sm">
        <thead className="border-b border-rule text-muted">
          <tr><th className="px-4 py-2 font-medium">Prompt</th><th className="w-36 px-4 py-2 font-medium">Answered by</th>
            <th className="w-32 px-4 py-2 text-right font-medium">Total tokens</th><th className="w-24 px-4 py-2 text-right font-medium">Change</th></tr>
        </thead>
        <tbody>
          {items.map((h, i) => (
            <tr key={i} className="border-b border-rule last:border-0">
              <td className="px-4 py-2"><span className="block truncate" title={h.text}>{h.text}</span>
                <span className="text-xs text-muted">optimized for {TARGET[h.target] ?? h.target}</span></td>
              <td className="px-4 py-2 text-sm">{modelName(h.model)}</td>
              <td className="tabular whitespace-nowrap px-4 py-2 text-right font-mono">{fmt(h.original.total)} → {fmt(h.optimized.total)}</td>
              <td className="px-4 py-2 text-right"><Delta value={h.change_pct} label="Change" /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Compare() {
  const { draft, setDraft } = useStore();
  const [models, setModels] = React.useState<CompareModel[] | null>(null);
  const [model, setModel] = React.useState<string>("");
  const [judge, setJudge] = React.useState(false);
  const [busy, setBusy] = React.useState<number | null>(null);
  const [result, setResult] = React.useState<CompareResult | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [refresh, setRefresh] = React.useState(0);

  React.useEffect(() => {
    api.compareModels().then((m) => { setModels(m.models); setModel((cur) => cur || m.default || ""); })
      .catch((e) => setError(e.message));
  }, []);

  const run = async () => {
    if (!draft.prompt.trim()) { toast.message("Type a prompt first."); return; }
    setBusy(Date.now()); setError(null); setResult(null);
    try {
      const r = await api.compare({ prompt: draft.prompt, target: draft.target, category: draft.category,
        attachment_type: draft.attachment, attachment_name: draft.attachmentName || null, context: draft.context || null,
        model, judge });
      setResult(r);
      setRefresh((x) => x + 1);
      toast.success("Comparison finished");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const available = models?.filter((m) => m.available) ?? [];
  return (
    <div>
      <PageHeader title="Compare"
        lead="Send your prompt and the optimized one to the same model and see what each costs and returns. This is the real test of whether optimizing helped." />
      <div className="grid gap-6 xl:grid-cols-[minmax(20rem,26rem)_minmax(0,1fr)]">
        <form className="space-y-4 xl:sticky xl:top-20 xl:self-start" onSubmit={(e) => { e.preventDefault(); run(); }}
          onKeyDown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); run(); } }}>
          <div>
            <label htmlFor="cmp-prompt" className={FIELD_LABEL}>Your prompt</label>
            <textarea id="cmp-prompt" rows={4} value={draft.prompt} onChange={(e) => setDraft({ prompt: e.target.value }, { record: false })}
              placeholder="e.g. write code to get all permutations of a string"
              className="proof block w-full resize-y rounded-xl border border-rule-strong bg-surface px-4 py-3 outline-none focus:border-focus focus:ring-2 focus:ring-focus/25" />
            <p className="mt-1 text-sm text-muted">
              {draft.context ? "Pasted text included. " : ""}Category: {CATEGORY[draft.category]}. Edit details on <Link to="/" className="underline underline-offset-4">Optimize</Link>.
            </p>
          </div>
          <div>
            <div className={FIELD_LABEL}>Optimized for<InfoTip>Which layout the optimized prompt uses. The answering model is chosen below.</InfoTip></div>
            <Segmented<Target> label="Optimized for" value={draft.target} onChange={(v) => setDraft({ target: v })}
              options={[{ value: "gpt", label: "GPT" }, { value: "gemini", label: "Gemini" }, { value: "claude", label: "Claude" }]} />
          </div>
          <div>
            <label htmlFor="cmp-model" className={FIELD_LABEL}>Answering model
              <InfoTip>We have no GPT, Claude or Gemini keys yet, so gpt-oss-120b stands in for them. The result always says which model answered.</InfoTip></label>
            {models ? (
              <Select id="cmp-model" label="Answering model" value={model} onChange={setModel}
                options={models.map((m) => ({ value: m.id, label: m.label, disabled: !m.available, hint: m.available ? undefined : m.reason ?? "unavailable" }))} />
            ) : <Skeleton className="h-10" />}
          </div>
          <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-rule bg-surface p-3">
            <input type="checkbox" checked={judge} onChange={(e) => setJudge(e.target.checked)} className="mt-1 size-4 accent-[var(--ink)]" />
            <span className="text-sm"><span className="font-medium">Blind judge</span><br />
              <span className="text-muted">A second model scores both answers 0–10 without knowing which is which. Adds about 10 s.</span></span>
          </label>
          <Button type="submit" variant="primary" size="lg" className="w-full" disabled={!!busy || !model || !draft.prompt.trim()} data-testid="run-compare">
            {busy ? <Loader2 className="animate-spin" /> : <Play />} {busy ? "Comparing…" : "Run comparison"}
            <span className="ml-1 text-xs opacity-70">{modKey}+↵</span>
          </Button>
          {models && !available.length && (
            <ErrorBox message="No answering model is available. Add GROQ_API_KEY or CEREBRAS_API_KEY to backend/.env and restart the server." />
          )}
        </form>

        <div className="min-w-0 space-y-6">
          {error && <ErrorBox message={error} onRetry={run} />}
          {busy ? <Running judge={judge} started={busy} /> : result ? <ResultView c={result} /> : (
            <EmptyState icon={<Columns2 />} title="Nothing compared yet">
              Press <b>Run comparison</b>. Both prompts go to the same model; you'll see both answers, the token change, latency and, for coding, test results.
            </EmptyState>
          )}
          <section>
            <h2 className="mb-3 flex items-center gap-2 font-display text-xl font-semibold"><Clock className="size-5 text-muted" aria-hidden /> Past comparisons</h2>
            <PastCompares refresh={refresh} />
          </section>
        </div>
      </div>
    </div>
  );
}
