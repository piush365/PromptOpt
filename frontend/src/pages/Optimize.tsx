import * as React from "react";
import { toast } from "sonner";
import { api, type OptimizeResult } from "@/lib/api";
import { useStore } from "@/lib/store";
import { Composer, useLiveTokens } from "@/components/Composer";
import { PipelineSkeleton, RenderCard, StageACard, StageBCard, StageCCard } from "@/components/Pipeline";
import { ExampleGallery } from "@/components/ExampleGallery";
import { ErrorBox, StageMark } from "@/components/Feedback";
import { STAGE } from "@/lib/labels";

function Intro() {
  return (
    <div className="space-y-6" data-testid="optimize-empty">
      <div className="rounded-2xl border border-rule bg-surface p-5 shadow-card sm:p-6">
        <p className="eyebrow">What happens when you press Optimize</p>
        <ol className="mt-4 grid gap-4 sm:grid-cols-2">
          {(Object.keys(STAGE) as (keyof typeof STAGE)[]).map((k) => (
            <li key={k} className="flex gap-3">
              <StageMark stage={k} />
              <div>
                <p className="font-medium">{k === "R" ? "Render" : `Stage ${k}`} · {STAGE[k].name}</p>
                <p className="text-sm text-muted">{STAGE[k].one}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
      <div>
        <h2 className="mb-3 font-display text-xl font-semibold">Try an example</h2>
        <ExampleGallery compact />
      </div>
    </div>
  );
}

export default function Optimize() {
  const { draft, result, setResult, pendingRun, clearRun, optionsError } = useStore();
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [highlight, setHighlight] = React.useState<string[]>([]);
  const resultRef = React.useRef<HTMLDivElement>(null);
  const original = useLiveTokens(draft.context ? `${draft.prompt}\n\n${draft.context}` : draft.prompt);

  const run = React.useCallback(async () => {
    if (!draft.prompt.trim()) { toast.message("Type a prompt first, or pick an example."); return; }
    setBusy(true); setError(null); setHighlight([]);
    try {
      const r = await api.optimize({
        prompt: draft.prompt, target: draft.target, category: draft.category, attachment_type: draft.attachment,
        attachment_name: draft.attachmentName || null, context: draft.context || null,
      });
      setResult(r as OptimizeResult);
      if (window.matchMedia("(max-width: 1279px)").matches) {
        requestAnimationFrame(() => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [draft, setResult]);

  // A run requested by another page (example gallery, "pick category", history reopen) after the draft is set.
  React.useEffect(() => {
    if (pendingRun) { clearRun(); run(); }
  }, [pendingRun, run, clearRun]);

  // Ctrl/Cmd+Enter anywhere on the page.
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !(e.target as HTMLElement).closest("textarea")) {
        e.preventDefault(); run();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [run]);

  return (
    <div className="grid gap-8 xl:grid-cols-[minmax(24rem,31rem)_minmax(0,1fr)]">
      <div className="xl:sticky xl:top-20 xl:self-start">
        <h1 className="font-display text-[2rem] font-semibold leading-tight sm:text-[2.5rem]">
          Make a vague prompt <span className="whitespace-nowrap">clear and short.</span>
        </h1>
        <p className="mb-6 mt-2 text-[1.0625rem] text-ink-2">
          Write it the way you normally would. PromptOpt shows what's missing, fixes it step by step, and writes it out for your model.
        </p>
        <Composer onSubmit={run} busy={busy} highlight={highlight} />
        {optionsError && <ErrorBox className="mt-4" message={optionsError} />}
      </div>

      <div ref={resultRef} className="min-w-0 scroll-mt-20" data-tour="pipeline">
        {error && <ErrorBox className="mb-4" message={error} onRetry={run} />}
        {busy ? <PipelineSkeleton /> : result ? (
          <ol aria-label="Pipeline result" key={result.prompt_id}>
            <StageACard r={result} onHighlight={setHighlight} index={0} />
            <StageBCard r={result} index={1} />
            <StageCCard r={result} index={2} />
            <RenderCard r={result} index={3} originalTokens={original} />
          </ol>
        ) : <Intro />}
      </div>
    </div>
  );
}
