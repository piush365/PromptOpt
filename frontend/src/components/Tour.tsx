import * as React from "react";
import { createPortal } from "react-dom";
import { useLocation } from "react-router-dom";
import { ArrowLeft, ArrowRight, X } from "lucide-react";
import { safeGet, safeSet, useStore } from "@/lib/store";
import { Button } from "@/components/ui/button";

const STEPS: { target: string; title: string; body: string }[] = [
  { target: "", title: "Welcome to PromptOpt",
    body: "It rewrites a vague prompt into a clear, structured one for GPT, Gemini or Claude, and shows you every change it makes. This tour takes a minute; you can skip it." },
  { target: "prompt", title: "1. Type your prompt",
    body: "Write it the way you normally would. The counter below shows how many tokens it costs to send. Paste the article or code it's about in “Pasted text”." },
  { target: "target", title: "2. Pick your model",
    body: "GPT, Gemini or Claude. The content stays the same; only the layout changes to what each model reads best." },
  { target: "category", title: "3. Category: auto or yours",
    body: "Leave it on auto-detect, or pick the kind of task. If you pick one, your choice wins." },
  { target: "pipeline", title: "4. Watch the pipeline",
    body: "After you press Optimize: Stage A (blue) finds what's missing, Stage B (green) fixes it with rules, Stage C (amber) helps only when the rules can't, and Render writes it out. Hover an issue to see the words it's about." },
  { target: "nav-compare", title: "5. Does it actually help?",
    body: "Compare runs the vague and the optimized prompt on a real model, side by side: answers, tokens, latency, and a blind judge." },
  { target: "nav-suite", title: "6. The evidence",
    body: "Test suite and Results show the measured numbers. How it works explains every term. Press ? any time for keyboard shortcuts." },
];

export function Tour() {
  const { tourOpen, setTourOpen } = useStore();
  const loc = useLocation();
  const [i, setI] = React.useState(0);
  const [rect, setRect] = React.useState<DOMRect | null>(null);
  const card = React.useRef<HTMLDivElement>(null);

  // First visit: open once on the Optimize page.
  React.useEffect(() => {
    if (loc.pathname === "/" && !safeGet("po-tour-seen")) setTourOpen(true);
  }, [loc.pathname, setTourOpen]);

  const close = React.useCallback(() => { safeSet("po-tour-seen", "1"); setTourOpen(false); setI(0); }, [setTourOpen]);

  const step = STEPS[i];
  React.useLayoutEffect(() => {
    if (!tourOpen) return;
    const find = () => {
      const els = step.target ? [...document.querySelectorAll<HTMLElement>(`[data-tour="${step.target}"]`)] : [];
      const el = els.find((e) => e.offsetParent !== null);
      setRect(el ? el.getBoundingClientRect() : null);
      return el;
    };
    const el = find();
    el?.scrollIntoView({ block: "nearest", behavior: "auto" });
    find();
    window.addEventListener("resize", find);
    window.addEventListener("scroll", find, true);
    return () => { window.removeEventListener("resize", find); window.removeEventListener("scroll", find, true); };
  }, [tourOpen, step]);

  React.useEffect(() => {
    if (!tourOpen) return;
    card.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
      else if (e.key === "ArrowRight") setI((x) => Math.min(x + 1, STEPS.length - 1));
      else if (e.key === "ArrowLeft") setI((x) => Math.max(x - 1, 0));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [tourOpen, close]);

  if (!tourOpen) return null;

  const pad = 8;
  const vw = window.innerWidth, vh = window.innerHeight;
  const cardW = Math.min(360, vw - 32);
  let style: React.CSSProperties = { left: (vw - cardW) / 2, top: Math.max(16, vh / 2 - 120), width: cardW };
  if (rect) {
    const below = rect.bottom + pad + 12;
    const roomBelow = vh - below > 220;
    const rightOf = rect.right + pad + 16;
    if (rect.width < 300 && vw - rightOf > cardW + 16) {
      style = { left: rightOf, top: Math.min(Math.max(16, rect.top), vh - 260), width: cardW };
    } else {
      style = { left: Math.min(Math.max(16, rect.left), vw - cardW - 16),
        top: roomBelow ? below : Math.max(16, rect.top - pad - 12 - 230), width: cardW };
    }
  }

  return createPortal(
    <div className="fixed inset-0 z-[60]" data-testid="tour">
      {rect ? (
        <div aria-hidden className="pointer-events-none absolute rounded-xl ring-2 ring-focus transition-all duration-200"
          style={{ left: rect.left - pad, top: rect.top - pad, width: rect.width + pad * 2, height: rect.height + pad * 2,
            boxShadow: "0 0 0 9999px rgb(10 14 22 / 0.55)" }} />
      ) : <div aria-hidden className="absolute inset-0 bg-[rgb(10_14_22/0.55)]" />}
      <div
        ref={card}
        role="dialog"
        aria-modal="true"
        aria-labelledby="tour-title"
        tabIndex={-1}
        className="absolute rounded-2xl border border-rule bg-surface p-5 shadow-card outline-none"
        style={style}
      >
        <div className="flex items-start justify-between gap-3">
          <h2 id="tour-title" className="font-display text-lg font-semibold">{step.title}</h2>
          <button onClick={close} aria-label="Skip the tour" className="grid size-8 shrink-0 place-items-center rounded-lg text-muted hover:bg-sunken hover:text-ink">
            <X className="size-4" />
          </button>
        </div>
        <p className="mt-2 text-sm text-ink-2">{step.body}</p>
        <div className="mt-4 flex items-center gap-2">
          <span className="font-mono text-xs text-muted" aria-label={`Step ${i + 1} of ${STEPS.length}`}>{i + 1} / {STEPS.length}</span>
          <div className="ml-auto flex gap-2">
            {i === 0 ? <Button size="sm" variant="ghost" onClick={close}>Skip</Button>
              : <Button size="sm" variant="ghost" onClick={() => setI(i - 1)}><ArrowLeft /> Back</Button>}
            {i < STEPS.length - 1
              ? <Button size="sm" variant="primary" onClick={() => setI(i + 1)} autoFocus>Next <ArrowRight /></Button>
              : <Button size="sm" variant="primary" onClick={close} autoFocus>Start using it</Button>}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
