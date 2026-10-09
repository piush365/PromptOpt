import * as React from "react";
import { Check, ChevronLeft, ChevronRight, FlaskConical, Loader2, Play, X } from "lucide-react";
import { api, type CaseStatus, type SuiteCase, type SuiteGrid } from "@/lib/api";
import { CATEGORY, CATEGORY_SHORT, fmt, pct } from "@/lib/labels";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Segmented } from "@/components/ui/segmented";
import { InfoTip } from "@/components/ui/tooltip";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { EmptyState, ErrorBox, PageHeader } from "@/components/Feedback";
import { PairBars } from "@/components/LazyCharts";
import { cn } from "@/lib/utils";

const STATUS: Record<CaseStatus, { label: string; tip: string; cls: string }> = {
  fixed: { label: "Fixed", tip: "Wrong with the vague prompt, right after optimizing.", cls: "bg-add-bg text-add" },
  hurt: { label: "Hurt", tip: "Right with the vague prompt, wrong after optimizing.", cls: "bg-del-bg text-del" },
  both: { label: "Both correct", tip: "Right either way.", cls: "bg-sunken text-ink-2" },
  neither: { label: "Both wrong", tip: "Wrong either way.", cls: "bg-c-soft text-c" },
};

function Mark({ ok }: { ok: boolean }) {
  return ok
    ? <span className="inline-flex items-center gap-1 text-add"><Check className="size-4" aria-hidden />correct</span>
    : <span className="inline-flex items-center gap-1 text-del"><X className="size-4" aria-hidden />wrong</span>;
}

function Summary({ grid, model }: { grid: SuiteGrid; model: string }) {
  const m = grid.models.find((x) => x.id === model);
  const s = m?.summary;
  const v = grid.verdicts[model] ?? {};
  if (!s) return <ErrorBox message={`No stored results for ${m?.label ?? model}. Run cases live from the case view.`} />;
  const count = (st: CaseStatus) => Object.values(v).filter((x) => x.status === st).length;
  const perCat = grid.categories.map((cat) => {
    const ids = grid.cases.filter((c) => c.category === cat).map((c) => c.id);
    return { name: CATEGORY_SHORT[cat] ?? cat, a: ids.filter((id) => v[id]?.vague).length, b: ids.filter((id) => v[id]?.optimized).length, n: ids.length };
  });
  const vp = Math.round((100 * s.vague) / s.n), op = Math.round((100 * s.optimized) / s.n);
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)_minmax(0,1.3fr)]" data-testid="suite-summary">
      <div className="rounded-xl border border-rule bg-surface p-5 shadow-card">
        <p className="eyebrow flex items-center">Correct answers<InfoTip>Each case has a gold answer checked by a script or a judge. Same model, same settings for both prompts.</InfoTip></p>
        <p className="mt-2 flex items-baseline gap-3 font-display">
          <span className="text-4xl font-semibold text-muted tabular">{vp}%</span>
          <span className="text-2xl text-muted" aria-hidden>→</span>
          <span className="text-5xl font-semibold tabular">{op}%</span>
        </p>
        <p className="mt-1 text-sm text-ink-2">{s.vague}/{s.n} with the vague prompt → {s.optimized}/{s.n} optimized</p>
        <dl className="mt-4 space-y-1.5 text-sm">
          <div className="flex justify-between"><dt className="flex items-center text-ink-2">McNemar p<InfoTip>Is the difference bigger than chance, on the same cases? Below 0.05 is usually called significant; with 50 cases a few flips aren't enough.</InfoTip></dt><dd className="tabular font-mono">{s.mcnemar_p.toFixed(3)}</dd></div>
          <div className="flex justify-between"><dt className="flex items-center text-ink-2">Total tokens per case<InfoTip>Mean change in input + output tokens, optimized vs vague.</InfoTip></dt><dd className="tabular font-mono">{pct(s.mean_reduction === null ? null : -s.mean_reduction)}</dd></div>
        </dl>
      </div>
      <div className="rounded-xl border border-rule bg-surface p-5 shadow-card">
        <p className="eyebrow mb-3 flex items-center">Case by case<InfoTip>Rows: the vague prompt's answer. Columns: the optimized prompt's answer. The two off-diagonal cells are what changed.</InfoTip></p>
        <table className="w-full text-center text-sm" aria-label="Vague versus optimized, 2 by 2">
          <thead><tr><th className="sr-only">Vague</th><th className="pb-2 font-medium text-muted">Optimized ✓</th><th className="pb-2 font-medium text-muted">Optimized ✗</th></tr></thead>
          <tbody>
            <tr><th scope="row" className="pr-2 text-right font-medium text-muted">Vague ✓</th>
              <td className="rounded-tl-lg bg-sunken p-3"><span className="block font-display text-2xl font-semibold">{count("both")}</span>both right</td>
              <td className="rounded-tr-lg bg-del-bg p-3 text-del"><span className="block font-display text-2xl font-semibold">{count("hurt")}</span>hurt</td></tr>
            <tr><th scope="row" className="pr-2 text-right font-medium text-muted">Vague ✗</th>
              <td className="rounded-bl-lg bg-add-bg p-3 text-add"><span className="block font-display text-2xl font-semibold">{count("fixed")}</span>fixed</td>
              <td className="rounded-br-lg bg-c-soft p-3 text-c"><span className="block font-display text-2xl font-semibold">{count("neither")}</span>both wrong</td></tr>
          </tbody>
        </table>
      </div>
      <div className="rounded-xl border border-rule bg-surface p-5 shadow-card">
        <p className="eyebrow mb-2">Correct per category (of {perCat[0]?.n ?? 10})</p>
        <PairBars data={perCat} a={{ label: "Vague", color: "var(--viz-vague)" }} b={{ label: "Optimized", color: "var(--viz-opt)" }} height={220} />
      </div>
    </div>
  );
}

function CaseView({ id, model, ids, onNav }: { id: string; model: string; ids: string[]; onNav: (id: string) => void }) {
  const [d, setD] = React.useState<SuiteCase | null>(null);
  const [err, setErr] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const load = React.useCallback((live: boolean) => {
    setErr(null); if (live) setBusy(true); else setD(null);
    (live ? api.suiteRun(id, model) : api.suiteCase(id, model)).then(setD).catch((e) => setErr(e.message)).finally(() => setBusy(false));
  }, [id, model]);
  React.useEffect(() => load(false), [load]);
  const i = ids.indexOf(id);
  return (
    <DialogContent wide title={d ? d.case.scenario : id}
      description={d ? `${d.case.id} · ${CATEGORY[d.case.category]} · ${d.case.difficulty.join(", ")}` : "Loading…"}>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Button size="sm" variant="ghost" disabled={i <= 0} onClick={() => onNav(ids[i - 1])}><ChevronLeft /> Previous</Button>
        <Button size="sm" variant="ghost" disabled={i >= ids.length - 1} onClick={() => onNav(ids[i + 1])}>Next <ChevronRight /></Button>
        <span className="text-sm text-muted">{i + 1} of {ids.length} shown</span>
        <Button size="sm" className="ml-auto" onClick={() => load(true)} disabled={busy}>
          {busy ? <Loader2 className="animate-spin" /> : <Play />} Run live now
        </Button>
      </div>
      {err && <ErrorBox className="mb-4" message={err} />}
      {!d ? <div className="space-y-3"><Skeleton className="h-24" /><Skeleton className="h-40" /></div> : (
        <div className="space-y-5" data-testid="case-view">
          <section>
            <h3 className="eyebrow mb-1.5">Material given to the model</h3>
            <pre className="proof max-h-56 overflow-auto rounded-lg border border-rule bg-sunken p-3 text-[0.8125rem]">{d.case.material}</pre>
          </section>
          <div className="grid gap-4 md:grid-cols-2">
            <section>
              <h3 className="eyebrow mb-1.5">Vague prompt</h3>
              <pre className="proof rounded-lg border border-rule p-3">{d.case.vague_prompt}</pre>
            </section>
            <section>
              <h3 className="eyebrow mb-1.5 flex items-center">Optimized prompt ({d.prompts.rendered_for.toUpperCase()})
                <InfoTip>{`Stage A: ${CATEGORY[d.pipeline.stage_a.category] ?? d.pipeline.stage_a.category} ${d.pipeline.stage_a.confidence.toFixed(2)}. Rules: ${d.pipeline.rules.map((r) => r.split("_")[0]).join(", ") || "none"}${d.pipeline.routed ? ". Routed to Stage C." : "."}`}</InfoTip></h3>
              <pre className="proof max-h-56 overflow-auto rounded-lg border border-rule p-3">{d.prompts.optimized}</pre>
            </section>
          </div>
          <section className="rounded-lg border border-b/30 bg-b-soft p-3">
            <h3 className="eyebrow mb-1">Gold answer</h3>
            <p className="proof text-ink">{d.gold}</p>
          </section>
          {d.result ? (
            <>
              <div className="grid gap-4 md:grid-cols-2">
                {(["vague", "optimized"] as const).map((k) => {
                  const x = d.result![k];
                  return (
                    <section key={k} className="flex min-w-0 flex-col rounded-xl border border-rule">
                      <header className="flex flex-wrap items-center gap-2 border-b border-rule px-3 py-2">
                        <span aria-hidden className="size-2.5 rounded-sm" style={{ background: k === "vague" ? "var(--viz-vague)" : "var(--viz-opt)" }} />
                        <span className="font-medium">{k === "vague" ? "Answer to the vague prompt" : "Answer to the optimized prompt"}</span>
                        <span className="ml-auto text-sm font-medium"><Mark ok={x.correct} /></span>
                      </header>
                      <pre className="proof max-h-72 flex-1 overflow-auto px-3 py-2 text-[0.8125rem]">{x.answer}</pre>
                      <p className="border-t border-rule px-3 py-2 text-xs text-muted">
                        {fmt(x.input_tokens)} in · {fmt(x.output_tokens)} out · {fmt(x.total_tokens)} total · {(x.latency_ms / 1000).toFixed(1)} s · checked by {x.method}
                        {x.why && <span className="mt-1 block text-del">Why wrong: {x.why}</span>}
                      </p>
                    </section>
                  );
                })}
              </div>
              <p className="text-sm text-ink-2">
                Total tokens {fmt(d.result.vague.total_tokens)} → {fmt(d.result.optimized.total_tokens)}{" "}
                (<span className={cn("font-mono", (d.result.total_reduction_pct ?? 0) > 0 ? "text-add" : "text-del")}>{pct(d.result.total_reduction_pct === null ? null : -d.result.total_reduction_pct)}</span>) on {d.model.label}{d.live ? ", run live just now." : ", from the reported run."}
              </p>
            </>
          ) : <p className="text-sm text-muted">No stored answers for this model. Press “Run live now”.</p>}
          {d.notes && <p className="rounded-lg bg-sunken p-3 text-sm text-ink-2"><b className="text-ink">Note:</b> {d.notes}</p>}
        </div>
      )}
    </DialogContent>
  );
}

export default function Suite() {
  const [grid, setGrid] = React.useState<SuiteGrid | null>(null);
  const [err, setErr] = React.useState<string | null>(null);
  const [model, setModel] = React.useState("");
  const [cat, setCat] = React.useState("all");
  const [status, setStatus] = React.useState<"all" | CaseStatus>("all");
  const [open, setOpen] = React.useState<string | null>(null);

  const load = React.useCallback(() => {
    setErr(null);
    api.suiteGrid().then((g) => { setGrid(g); setModel((m) => m || g.models.find((x) => x.has_results)?.id || g.models[0]?.id || ""); })
      .catch((e) => setErr(e.message));
  }, []);
  React.useEffect(load, [load]);

  const v = grid?.verdicts[model] ?? {};
  const shown = (grid?.cases ?? []).filter((c) => (cat === "all" || c.category === cat) && (status === "all" || v[c.id]?.status === status));

  return (
    <div>
      <PageHeader title="Test suite"
        lead="50 realistic cases written with a known right answer: a vague prompt as a student would type it, and the material it's about. Each prompt was answered as is and after optimizing, then checked against the gold answer." />
      {err && <ErrorBox message={err} onRetry={load} />}
      {!grid ? (!err && <div className="grid gap-4 lg:grid-cols-3"><Skeleton className="h-48" /><Skeleton className="h-48" /><Skeleton className="h-48" /></div>) : (
        <div className="space-y-6">
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-full sm:w-72">
              <label className="mb-1.5 block text-sm font-medium text-ink-2" htmlFor="suite-model">Answering model</label>
              <Select id="suite-model" label="Answering model" value={model} onChange={setModel}
                options={grid.models.map((m) => ({ value: m.id, label: m.label, disabled: !m.has_results && !m.available,
                  hint: m.has_results ? "reported run" : m.available ? "no stored run: use Run live" : m.reason ?? "" }))} />
            </div>
            {grid.generated && <p className="pb-2 text-sm text-muted">Reported run: {new Date(grid.generated).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}</p>}
          </div>
          <Summary grid={grid} model={model} />

          <section aria-labelledby="cases-h">
            <div className="mb-3 flex flex-wrap items-center gap-3">
              <h2 id="cases-h" className="font-display text-xl font-semibold">Cases <span className="text-muted">({shown.length})</span></h2>
              <div className="flex flex-wrap gap-2 sm:ml-auto">
                <Segmented size="sm" label="Filter by outcome" value={status} onChange={setStatus} className="overflow-x-auto"
                  options={[{ value: "all", label: "All" }, { value: "fixed", label: "Fixed" }, { value: "hurt", label: "Hurt" },
                    { value: "both", label: "Both ✓" }, { value: "neither", label: "Both ✗" }]} />
                <div className="w-48">
                  <Select label="Filter by category" value={cat} onChange={setCat}
                    options={[{ value: "all", label: "All categories" }, ...grid.categories.map((c) => ({ value: c, label: CATEGORY[c] ?? c }))]} />
                </div>
              </div>
            </div>
            {shown.length ? (
              <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4" data-testid="case-grid">
                {shown.map((c) => {
                  const x = v[c.id];
                  const st = x ? STATUS[x.status] : null;
                  return (
                    <li key={c.id}>
                      <button onClick={() => setOpen(c.id)} data-case={c.id}
                        className="flex h-full w-full flex-col gap-2 rounded-xl border border-rule bg-surface p-4 text-left shadow-card transition-[border-color,transform] hover:-translate-y-0.5 hover:border-rule-strong">
                        <span className="flex items-center gap-2">
                          <span className="font-mono text-xs text-muted">{c.id}</span>
                          <Badge tone="outline">{CATEGORY_SHORT[c.category] ?? c.category}</Badge>
                          {st && <span className={cn("ml-auto rounded-md px-1.5 py-0.5 text-xs font-medium", st.cls)} title={st.tip}>{st.label}</span>}
                        </span>
                        <span className="font-medium leading-snug">{c.scenario}</span>
                        <span className="proof line-clamp-2 text-xs text-muted">“{c.vague_prompt}”</span>
                        {x && (
                          <span className="mt-auto flex items-center gap-3 pt-1 text-xs text-ink-2">
                            <span>vague {x.vague ? "✓" : "✗"}</span><span>optimized {x.optimized ? "✓" : "✗"}</span>
                            <span className="tabular ml-auto font-mono">{fmt(x.tokens.vague)} → {fmt(x.tokens.optimized)} tok</span>
                          </span>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <EmptyState icon={<FlaskConical />} title="No case matches these filters"
                action={<Button size="sm" onClick={() => { setCat("all"); setStatus("all"); }}>Show all cases</Button>}>
                Try another outcome or category.
              </EmptyState>
            )}
          </section>
        </div>
      )}
      <Dialog open={!!open} onOpenChange={(o) => !o && setOpen(null)}>
        {open && <CaseView id={open} model={model} ids={shown.map((c) => c.id)} onNav={setOpen} />}
      </Dialog>
    </div>
  );
}
