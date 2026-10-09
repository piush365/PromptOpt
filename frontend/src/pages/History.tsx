import * as React from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Download, Eye, History as HistoryIcon, Loader2, RotateCcw, Search, ShieldCheck, Trash2 } from "lucide-react";
import { api, type HistoryDetail, type HistoryItem } from "@/lib/api";
import { useStore } from "@/lib/store";
import { CATEGORY, TARGET, ATTACHMENT, ruleInfo } from "@/lib/labels";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip } from "@/components/ui/tooltip";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { EmptyState, ErrorBox, PageHeader, CopyButton } from "@/components/Feedback";
import { Diff } from "@/components/Diff";

const PAGE = 30;

function when(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

function toMarkdown(d: HistoryDetail): string {
  const r = d.results[d.results.length - 1];
  const lines = [`## Prompt #${d.prompt_id}`, "", "**Original**", "", "```", d.original_text, "```", ""];
  if (r) {
    lines.push(`Category: ${r.ir.category ?? r.ir.mode ?? "-"} · Stage C: ${r.used_lora ? "used" : "not used"}`, "");
    if (r.steps.length) {
      lines.push("**Changes**", "");
      r.steps.forEach((s) => lines.push(`${s.step}. ${s.rule ? `${s.rule}` : s.stage}${s.note ? ` (${s.note})` : ""}`));
      lines.push("");
    }
    for (const [t, text] of Object.entries(r.renderings)) lines.push(`**${TARGET[t] ?? t}**`, "", "```", text, "```", "");
  }
  return lines.join("\n");
}

function download(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/markdown" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function Detail({ id }: { id: number }) {
  const [d, setD] = React.useState<HistoryDetail | null>(null);
  const [err, setErr] = React.useState<string | null>(null);
  React.useEffect(() => { api.historyItem(id).then(setD).catch((e) => setErr(e.message)); }, [id]);
  const r = d?.results[d.results.length - 1];
  return (
    <DialogContent wide title={`Prompt #${id}`} description={d ? `Kept until ${new Date(d.expires_at).toLocaleDateString("en-GB")}${d.pii_redactions ? ` · ${d.pii_redactions} personal detail(s) removed` : ""}` : "Loading…"}>
      {err && <ErrorBox message={err} />}
      {!d ? !err && <Skeleton className="h-48" /> : (
        <div className="space-y-5">
          <section><h3 className="eyebrow mb-1.5">Original</h3><pre className="proof rounded-lg border border-rule bg-sunken p-3">{d.original_text}</pre></section>
          {r && r.steps.length > 0 && (
            <section>
              <h3 className="eyebrow mb-2">What changed</h3>
              <ol className="space-y-3">
                {r.steps.filter((s) => s.before !== s.after).map((s) => (
                  <li key={s.step}>
                    <p className="mb-1 text-sm"><Badge tone={s.stage === "C" ? "c" : "b"}>{s.rule ? ruleInfo(s.rule).short : `Stage ${s.stage}`}</Badge>{" "}
                      {s.rule ? ruleInfo(s.rule).name : s.note}</p>
                    <Diff before={s.before} after={s.after} />
                  </li>
                ))}
              </ol>
            </section>
          )}
          {r && Object.entries(r.renderings).map(([t, text]) => (
            <section key={t}>
              <div className="mb-1.5 flex items-center justify-between"><h3 className="eyebrow">{TARGET[t] ?? t}</h3><CopyButton text={text} what={`${TARGET[t] ?? t} prompt`} /></div>
              <pre className="proof max-h-64 overflow-auto rounded-lg border border-rule bg-sunken p-3 text-[0.8125rem]">{text}</pre>
            </section>
          ))}
        </div>
      )}
    </DialogContent>
  );
}

function Row({ h, onDeleted, onView }: { h: HistoryItem; onDeleted: (id: number) => void; onView: (id: number) => void }) {
  const { setDraft, setImageDraft, requestRun, requestImageRun } = useStore();
  const navigate = useNavigate();
  const [confirm, setConfirm] = React.useState(false);
  const [busy, setBusy] = React.useState(false);

  const reopen = () => {
    if (h.mode === "image") {
      setImageDraft({ prompt: h.text, target: (h.target as never) ?? "dalle", accepted: [] });
      requestImageRun();
      navigate("/image");
      return;
    } else {
      setDraft({ prompt: h.text, target: (["gpt", "gemini", "claude"].includes(h.target ?? "") ? h.target : "gpt") as never,
        category: h.category_source === "user" && h.category ? (h.category as never) : "auto",
        attachment: (h.attachment as never) ?? "none" });
      navigate("/");
    }
    requestRun();
  };
  const del = async () => {
    setBusy(true);
    try { await api.deleteHistory(h.prompt_id); onDeleted(h.prompt_id); toast.success("Prompt deleted"); }
    catch (e) { toast.error((e as Error).message); setBusy(false); }
  };
  const exportOne = async () => {
    try { download(`promptopt-${h.prompt_id}.md`, toMarkdown(await api.historyItem(h.prompt_id))); toast.success("Exported as Markdown"); }
    catch (e) { toast.error((e as Error).message); }
  };

  return (
    <li className="rounded-xl border border-rule bg-surface p-4 shadow-card" data-history={h.prompt_id}>
      <div className="flex flex-col gap-3 md:flex-row md:items-start">
        <div className="min-w-0 flex-1">
          <p className="proof line-clamp-3 text-ink">{h.text}</p>
          <p className="mt-2 flex flex-wrap items-center gap-1.5 text-sm text-muted">
            <span>{when(h.created_at)}</span>
            {h.mode === "image" ? <Badge tone="outline">image mode</Badge> : h.category && <Badge>{CATEGORY[h.category] ?? h.category}</Badge>}
            {h.target && <Badge tone="outline">{TARGET[h.target] ?? h.target}</Badge>}
            {h.attachment && h.attachment !== "none" && <Badge tone="outline">{ATTACHMENT[h.attachment]}</Badge>}
            <Badge tone="b">{h.changes} {h.changes === 1 ? "change" : "changes"}</Badge>
            {h.used_stage_c && <Badge tone="c">Stage C</Badge>}
            {h.compares.length > 0 && <Badge tone="outline">compared ×{h.compares.length}</Badge>}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5 md:justify-end">
          <Button size="sm" variant="primary" onClick={reopen}><RotateCcw /> Reopen</Button>
          <Button size="sm" onClick={() => onView(h.prompt_id)}><Eye /> View</Button>
          <Tooltip content="Download this prompt and its renderings as Markdown"><Button size="sm" variant="ghost" onClick={exportOne} aria-label="Export as Markdown"><Download /></Button></Tooltip>
          {confirm ? (
            <span className="flex items-center gap-1">
              <Button size="sm" variant="danger" onClick={del} disabled={busy} className="border border-del/40">{busy ? <Loader2 className="animate-spin" /> : <Trash2 />} Delete for good</Button>
              <Button size="sm" variant="ghost" onClick={() => setConfirm(false)}>Keep</Button>
            </span>
          ) : (
            <Tooltip content="Delete from history"><Button size="sm" variant="ghost" onClick={() => setConfirm(true)} aria-label="Delete"><Trash2 /></Button></Tooltip>
          )}
        </div>
      </div>
    </li>
  );
}

export default function History() {
  const { options } = useStore();
  const navigate = useNavigate();
  const [q, setQ] = React.useState("");
  const [items, setItems] = React.useState<HistoryItem[] | null>(null);
  const [total, setTotal] = React.useState(0);
  const [err, setErr] = React.useState<string | null>(null);
  const [view, setView] = React.useState<number | null>(null);
  const [more, setMore] = React.useState(false);

  const load = React.useCallback((query: string) => {
    setErr(null);
    api.history(query, PAGE, 0).then((r) => { setItems(r.items); setTotal(r.total); }).catch((e) => setErr(e.message));
  }, []);
  React.useEffect(() => { const t = setTimeout(() => load(q), 200); return () => clearTimeout(t); }, [q, load]);

  const loadMore = async () => {
    setMore(true);
    try { const r = await api.history(q, PAGE, items?.length ?? 0); setItems((c) => [...(c ?? []), ...r.items]); }
    catch (e) { toast.error((e as Error).message); } finally { setMore(false); }
  };
  const exportAll = async () => {
    if (!items?.length) return;
    try {
      const details = await Promise.all(items.map((h) => api.historyItem(h.prompt_id)));
      download("promptopt-history.md", `# PromptOpt history\n\n${details.map(toMarkdown).join("\n---\n\n")}`);
      toast.success(`Exported ${details.length} prompts as Markdown`);
    } catch (e) { toast.error((e as Error).message); }
  };

  return (
    <div>
      <PageHeader title="History"
        lead={<span className="flex flex-wrap items-center gap-1.5"><ShieldCheck className="size-4 text-b" aria-hidden />
          Kept for {options?.retention_days ?? 30} days, then deleted. Emails and phone numbers are removed before anything is stored.</span>}
        actions={<Button onClick={exportAll} disabled={!items?.length}><Download /> Export shown as Markdown</Button>} />
      <label className="relative mb-5 block max-w-xl">
        <span className="sr-only">Search history</span>
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search your prompts and their optimized versions…" data-testid="history-search"
          className="h-11 w-full rounded-xl border border-rule-strong bg-surface pl-9 pr-3 outline-none focus:border-focus focus:ring-2 focus:ring-focus/25" />
      </label>
      {err && <ErrorBox message={err} onRetry={() => load(q)} />}
      {!items ? (!err && <div className="space-y-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-24" />)}</div>) : items.length ? (
        <>
          <p className="mb-3 text-sm text-muted" aria-live="polite">{total} {total === 1 ? "prompt" : "prompts"}{q && ` matching “${q}”`}</p>
          <ul className="space-y-3" data-testid="history-list">
            {items.map((h) => <Row key={h.prompt_id} h={h} onView={setView}
              onDeleted={(id) => { setItems((c) => c?.filter((x) => x.prompt_id !== id) ?? null); setTotal((t) => t - 1); }} />)}
          </ul>
          {items.length < total && (
            <div className="mt-4 flex justify-center"><Button onClick={loadMore} disabled={more}>{more && <Loader2 className="animate-spin" />} Show more</Button></div>
          )}
        </>
      ) : q ? (
        <EmptyState icon={<Search />} title={`Nothing matches “${q}”`} action={<Button size="sm" onClick={() => setQ("")}>Clear search</Button>}>
          Search looks in the original prompt and the optimized text.
        </EmptyState>
      ) : (
        <EmptyState icon={<HistoryIcon />} title="No prompts yet" action={<Button variant="primary" onClick={() => navigate("/")}>Optimize a prompt</Button>}>
          Every prompt you optimize is saved here, so you can reopen, compare or export it later.
        </EmptyState>
      )}
      <Dialog open={view !== null} onOpenChange={(o) => !o && setView(null)}>
        {view !== null && <Detail id={view} />}
      </Dialog>
    </div>
  );
}
