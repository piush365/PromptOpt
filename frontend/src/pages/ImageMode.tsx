import * as React from "react";
import { Ban, Check, Image as ImageIcon, Loader2, Plus, Wand2, X } from "lucide-react";
import { api, type ImageResult, type ImageTarget } from "@/lib/api";
import { useStore } from "@/lib/store";
import { IMAGE_ATTR, TARGET, ruleInfo } from "@/lib/labels";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Segmented } from "@/components/ui/segmented";
import { InfoTip } from "@/components/ui/tooltip";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { CopyButton, EmptyState, ErrorBox, PageHeader } from "@/components/Feedback";
import { FIELD_LABEL } from "@/components/Composer";
import { modKey } from "@/lib/utils";

const TARGETS: ImageTarget[] = ["dalle", "nano_banana", "stable_diffusion"];
const EXAMPLES = ["oil painting of a sailboat in a storm", "a cozy reading nook, phone wallpaper, no people", "logo of a fox made of origami"];

export default function ImageMode() {
  const { imageDraft: d, setImageDraft, imageResult: r, setImageResult, pendingImageRun, clearImageRun } = useStore();
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);
  const [tab, setTab] = React.useState<ImageTarget>(d.target);

  const run = React.useCallback(async (accepted = d.accepted) => {
    if (!d.prompt.trim()) return;
    setBusy(true); setErr(null);
    try {
      const res = await api.optimize({ prompt: d.prompt, target: d.target, category: "image_generation", attachment_type: "none",
        accepted_suggestions: accepted }) as ImageResult;
      setImageResult(res); setTab(d.target);
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }, [d, setImageResult]);

  React.useEffect(() => { if (pendingImageRun) { clearImageRun(); run(); } }, [pendingImageRun, run, clearImageRun]);

  const toggle = (item: string) => {
    const accepted = d.accepted.includes(item) ? d.accepted.filter((x) => x !== item) : [...d.accepted, item];
    setImageDraft({ accepted });
    run(accepted);
  };

  return (
    <div>
      <PageHeader title="Image mode"
        lead="For image generators. Your words stay first and nothing is added that could change your picture; missing details become suggestions you can click." />
      <div className="grid gap-8 xl:grid-cols-[minmax(22rem,28rem)_minmax(0,1fr)]">
        <form className="space-y-5 xl:sticky xl:top-20 xl:self-start" onSubmit={(e) => { e.preventDefault(); run(); }}>
          <div>
            <label htmlFor="img-prompt" className={FIELD_LABEL}>Describe the image</label>
            <textarea id="img-prompt" rows={4} value={d.prompt}
              onChange={(e) => setImageDraft({ prompt: e.target.value, accepted: [] })}
              onKeyDown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); run(); } }}
              placeholder="e.g. oil painting of a sailboat in a storm"
              className="proof block w-full resize-y rounded-xl border border-rule-strong bg-surface px-4 py-3 text-[0.9375rem] shadow-card outline-none focus:border-focus focus:ring-2 focus:ring-focus/25" />
            <p className="mt-2 flex flex-wrap gap-1.5 text-sm text-muted">Try:
              {EXAMPLES.map((x) => <button key={x} type="button" onClick={() => setImageDraft({ prompt: x, accepted: [] })}
                className="rounded-md border border-rule px-1.5 text-ink-2 hover:border-rule-strong hover:text-ink">{x}</button>)}</p>
          </div>
          <div>
            <div className={FIELD_LABEL}>Image model<InfoTip>Stable Diffusion gets the style first and a separate negative prompt; DALL·E and Nano Banana get a sentence.</InfoTip></div>
            <Segmented<ImageTarget> label="Image model" value={d.target} onChange={(v) => setImageDraft({ target: v })}
              options={TARGETS.map((t) => ({ value: t, label: t === "stable_diffusion" ? "Stable Diff." : TARGET[t] }))} />
          </div>
          <Button type="submit" variant="primary" size="lg" disabled={busy || !d.prompt.trim()} className="w-full sm:w-auto" data-testid="optimize-image">
            {busy ? <Loader2 className="animate-spin" /> : <Wand2 />} Optimize for images <span className="text-xs opacity-70">{modKey}+↵</span>
          </Button>
          <p className="text-sm text-muted">Measured on Stable Diffusion 1.5 with CLIP: this version keeps images as close to your request as the original prompt (held-out set, 12/12 styles kept). DALL·E and Nano Banana prompts are untested without API keys.</p>
        </form>

        <div className="min-w-0 space-y-5">
          {err && <ErrorBox message={err} onRetry={() => run()} />}
          {busy && !r ? <Skeleton className="h-80" /> : !r ? (
            <EmptyState icon={<ImageIcon />} title="Describe an image to start">Type what you want to see, pick the model, and press Optimize for images.</EmptyState>
          ) : (
            <div className={busy ? "opacity-60 transition-opacity" : ""} data-testid="image-result">
              <div className="grid gap-4 md:grid-cols-2">
                <section className="rounded-xl border border-rule bg-surface p-4 shadow-card">
                  <h2 className="mb-2 flex items-center font-medium">What you said<InfoTip>Attributes found in your words. They are kept exactly as you wrote them.</InfoTip></h2>
                  {Object.keys(r.stated).length ? (
                    <ul className="flex flex-wrap gap-1.5">{Object.entries(r.stated).map(([a, v]) => (
                      <li key={a}><Badge tone="b"><Check /> {IMAGE_ATTR[a] ?? a}: {v.join(", ")}</Badge></li>))}</ul>
                  ) : <p className="text-sm text-muted">Only the subject.</p>}
                  {r.avoid_user.length > 0 && <p className="mt-3 flex flex-wrap items-center gap-1.5 text-sm"><Ban className="size-4 text-del" aria-hidden /> Avoid: {r.avoid_user.map((x) => <Badge key={x} tone="del">{x}</Badge>)}</p>}
                </section>
                <section className="rounded-xl border border-rule bg-surface p-4 shadow-card">
                  <h2 className="mb-2 flex items-center font-medium">Added automatically<InfoTip>Only things that can't conflict with your request.</InfoTip></h2>
                  {r.auto_added.length ? <ul className="space-y-1 text-sm">{r.auto_added.map((x) => <li key={x.what}><b>{x.what}:</b> <span className="text-ink-2">{x.value}</span></li>)}</ul>
                    : <p className="text-sm text-muted">Nothing.</p>}
                </section>
              </div>

              <section className="mt-4 rounded-xl border border-rule bg-surface p-4 shadow-card">
                <h2 className="mb-1 flex items-center font-medium">Suggestions<InfoTip>Missing details you might want. Nothing is added unless you click it; click again to remove.</InfoTip></h2>
                <p className="mb-3 text-sm text-muted">Click to add. Earlier tests showed that filling every gap automatically pulled images away from what people asked for.</p>
                {r.accepted.length > 0 && (
                  <div className="mb-3 flex flex-wrap gap-1.5" aria-label="Added suggestions">
                    {r.accepted.map((a) => { const [k, v] = a.split(/:(.*)/s); return (
                      <button key={a} onClick={() => toggle(a)} disabled={busy} aria-label={`Remove ${v}`}
                        className="inline-flex items-center gap-1 rounded-full bg-ink px-3 py-1 text-sm text-paper hover:opacity-90">
                        {IMAGE_ATTR[k] ?? k}: {v} <X className="size-3.5" aria-hidden /></button>); })}
                  </div>
                )}
                {r.suggestions.length ? (
                  <dl className="space-y-2.5" data-testid="suggestions">
                    {r.suggestions.map((s) => (
                      <div key={s.attribute} className="grid gap-1 sm:grid-cols-[11rem_1fr] sm:items-baseline">
                        <dt className="text-sm text-ink-2">{IMAGE_ATTR[s.attribute] ?? s.attribute}{s.hint && <span className="block text-xs leading-snug text-muted">{s.hint}</span>}</dt>
                        <dd className="flex flex-wrap gap-1.5">
                          {!s.options.length && <span className="text-sm text-muted">Add it in your own words, in the box on the left.</span>}
                          {s.options.map((o) => {
                            const key = `${s.attribute}:${o}`;
                            return (
                              <button key={o} onClick={() => toggle(key)} disabled={busy} aria-pressed={d.accepted.includes(key)}
                                className="inline-flex items-center gap-1 rounded-full border border-rule-strong px-2.5 py-0.5 text-sm text-ink-2 hover:border-ink hover:text-ink aria-pressed:bg-ink aria-pressed:text-paper">
                                <Plus className="size-3" aria-hidden />{o}</button>
                            );
                          })}
                        </dd>
                      </div>
                    ))}
                  </dl>
                ) : <p className="text-sm text-muted">None: your prompt covers every attribute.</p>}
              </section>

              <section className="mt-4 rounded-xl border border-rule bg-surface p-4 shadow-card">
                <Tabs value={tab} onValueChange={(v) => setTab(v as ImageTarget)}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <TabsList aria-label="Prompt per image model">
                      {TARGETS.map((t) => <TabsTrigger key={t} value={t}>{TARGET[t]}{t === r.target && <span className="size-1.5 rounded-full bg-b" aria-label="(selected)" />}</TabsTrigger>)}
                    </TabsList>
                    <CopyButton what={`${TARGET[tab]} prompt`} text={r.renderings[tab].prompt + (r.renderings[tab].negative_prompt ? `\n\nNegative prompt: ${r.renderings[tab].negative_prompt}` : "")} />
                  </div>
                  {TARGETS.map((t) => {
                    const x = r.renderings[t];
                    const params = Object.entries(x.params);
                    return (
                      <TabsContent key={t} value={t} className="mt-3 space-y-3 outline-none">
                        <pre className="proof rounded-xl border border-rule bg-sunken/70 p-4" data-testid={`image-rendering-${t}`}>{x.prompt}</pre>
                        {x.negative_prompt && (
                          <div><p className="eyebrow mb-1 flex items-center">Negative prompt<InfoTip>Stable Diffusion takes a separate list of things to keep out of the image.</InfoTip></p>
                            <pre className="proof rounded-xl border border-del/30 bg-del-bg/60 p-3 text-[0.8125rem]">{x.negative_prompt}</pre></div>
                        )}
                        <p className="text-sm text-muted">{params.length ? `Parameters: ${params.map(([k, v]) => `${k} ${v}`).join(", ")}` : "No parameters"}{r.aspect_ratio ? "" : " (no aspect ratio stated: the model's default size)"}</p>
                      </TabsContent>
                    );
                  })}
                </Tabs>
              </section>

              {r.rules.length > 0 && (
                <section className="mt-4">
                  <h2 className="mb-2 font-medium">Rules applied</h2>
                  <ul className="space-y-1.5 text-sm">{r.rules.map((x, i) => { const info = ruleInfo(x.code, x.what); return (
                    <li key={i} className="flex flex-wrap gap-2"><Badge tone="b">{info.short}</Badge><span className="font-medium">{info.name}</span><span className="text-muted">{info.why}</span></li>); })}</ul>
                </section>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
