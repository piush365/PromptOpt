import * as React from "react";
import { Link } from "react-router-dom";
import { AnimatePresence, LazyMotion, m } from "framer-motion";
import { ArrowDown, ArrowRight, Search } from "lucide-react";
import { GLOSSARY } from "@/lib/labels";
import { PageHeader, StageMark } from "@/components/Feedback";
import { Diff } from "@/components/Diff";
import { cn } from "@/lib/utils";

type NodeId = "in" | "A" | "B" | "C" | "R" | "out";

const NODES: { id: NodeId; name: string; sub: string; stage?: "A" | "B" | "C" | "R" }[] = [
  { id: "in", name: "Your prompt", sub: "+ target, category, attachment" },
  { id: "A", name: "Detect", sub: "Stage A", stage: "A" },
  { id: "B", name: "Rules", sub: "Stage B", stage: "B" },
  { id: "C", name: "Small model", sub: "Stage C · only if needed", stage: "C" },
  { id: "R", name: "Render", sub: "IR → GPT / Gemini / Claude", stage: "R" },
  { id: "out", name: "Measure", sub: "Compare · test suite" },
];

// Real outputs of the frozen pipeline (captured from /api/optimize).
const EX = "write code to get all permutations of a string";

const DETAIL: Record<NodeId, { title: string; plain: string; points: string[]; example: React.ReactNode }> = {
  in: {
    title: "You write the prompt the way you normally would",
    plain: "Short, vague prompts are normal. The problem: the model has to guess what you want, so it often writes long answers with options you didn't ask for. You pay for all of it.",
    points: ["Pick the model you'll use: GPT, Gemini or Claude.", "Leave the category on auto, or choose it yourself (your choice always wins).",
      "Say if a file will be attached (image, PDF, slides…). This changes the wording, not the category."],
    example: <p className="proof rounded-lg border border-rule bg-sunken p-3">{EX}</p>,
  },
  A: {
    title: "Stage A works out what kind of task it is, and what's missing",
    plain: "A small classifier guesses the category and how sure it is: it finds the most similar labelled training prompts (sentence embeddings, MiniLM) and blends their vote with keyword cues like “summarize” or “write a function”. Detectors written as rules look for what's missing: no output format, no length, no programming language, filler words, or an unclear “this”.",
    points: ["Five categories: question about a text, extraction, classification, summary, coding (plus “other”).",
      "Confidence is 0–1. At 0.6 or above, category-specific rules can run.", "Accuracy on the test split: 74.7%. Most mistakes are between Q&A, extraction and summary."],
    example: (
      <dl className="grid gap-2 text-sm sm:grid-cols-3">
        <div className="rounded-lg bg-a-soft p-3"><dt className="eyebrow">category</dt><dd className="font-medium">Coding</dd></div>
        <div className="rounded-lg bg-a-soft p-3"><dt className="eyebrow">confidence</dt><dd className="font-mono">0.999</dd></div>
        <div className="rounded-lg bg-a-soft p-3"><dt className="eyebrow">missing</dt><dd>output format, language</dd></div>
      </dl>
    ),
  },
  B: {
    title: "Stage B fixes it with small, predictable rules",
    plain: "Each rule does one thing and is tested on its own: remove filler, add an output format, add a length, name the programming language, list the allowed labels, tidy the structure. Every change is logged with before and after, so you can see exactly why the prompt changed.",
    points: ["Same input, same output, every time. No AI guessing in this stage.", "Below 0.6 confidence, only safe shared fixes are applied (B08).",
      "Output format stated: 3.1% of vague prompts → 95.0% after Stage B."],
    example: (
      <div className="space-y-2">
        <p className="text-sm"><b>B05</b> name the language</p>
        <Diff before="Write code to get all permutations of a string." after={"Write code to get all permutations of a string.\n\nUse Python."} />
        <p className="text-sm"><b>B03</b> add an output format</p>
        <Diff before={"Write code to get all permutations of a string.\n\nUse Python."} after={"Write code to get all permutations of a string.\n\nUse Python. Return only the code, in a single code block."} />
      </div>
    ),
  },
  C: {
    title: "Stage C helps only when the rules can't",
    plain: "A small model (Qwen2.5-0.5B, fine-tuned with LoRA) is called only when the rules leave the task category or an unclear reference unresolved: about 6% of prompts. It fills in just those fields, as JSON. Its answer is checked; if it fails, Stage B's result is kept. If it suggests a category, you are asked to confirm it.",
    points: ["Usable answers: 5% for the untrained model vs 98% after fine-tuning.", "On routed prompts, format stated rises from 23% to 90%.",
      "Sending every prompt through it made results worse, so it stays a fallback."],
    example: (
      <div className="space-y-2 text-sm">
        <p className="proof rounded-lg border border-rule bg-sunken p-3">describe what is happening in the picture <span className="text-muted">+ image</span></p>
        <p>Stage A is unsure (coding, 0.37) → routed. Stage C suggests <b>summary</b>; the app asks you to confirm.</p>
      </div>
    ),
  },
  R: {
    title: "Render writes the same content for each model",
    plain: "The result is first stored as fields (the IR: task, context, constraints, output format). Then it's written out in the layout each model reads best. The content is identical; tests parse every version back to check nothing was lost.",
    points: ["Claude: XML tags, context first.", "GPT: ### Task / Context / Constraints / Output format.", "Gemini: plain labels, instruction first.",
      "Tokens: GPT counted exactly; Claude and Gemini estimated (characters ÷ 4) and labelled."],
    example: <pre className="proof rounded-lg border border-rule bg-sunken p-3 text-[0.8125rem]">{"### Task\nWrite code to get all permutations of a string.\n\n### Constraints\n- Use Python.\n\n### Output format\nReturn only the code, in a single code block."}</pre>,
  },
  out: {
    title: "Then we measure whether it actually helped",
    plain: "A longer prompt only pays off if the answer gets shorter or better. Compare sends both prompts to the same model and shows tokens, latency, a blind judge and, for code, sandbox test results. The evaluation did the same on 482 test prompts.",
    points: ["Total tokens −39.2% per prompt (95% CI 35.9–42.5%).", "Input grows a little; output shrinks a lot.",
      "Honest limit: 87 of 482 prompts cost more, mostly where the answer was already short."],
    example: (
      <p className="text-sm">On the permutations prompt: <span className="font-mono">768 → 248</span> total tokens (<b className="text-add">−67.7%</b>), both answers pass 6/6 tests. <Link to="/compare" className="underline underline-offset-4">Try it on Compare</Link>.</p>
    ),
  },
};

function Diagram({ sel, onSel }: { sel: NodeId; onSel: (n: NodeId) => void }) {
  return (
    <div role="tablist" aria-label="Pipeline stages" className="flex flex-col items-stretch gap-1 md:flex-row md:items-center md:gap-0" data-testid="diagram">
      {NODES.map((n, i) => (
        <React.Fragment key={n.id}>
          <button
            role="tab"
            id={`tab-${n.id}`}
            aria-selected={sel === n.id}
            aria-controls="stage-detail"
            onClick={() => onSel(n.id)}
            onKeyDown={(e) => {
              const k = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
              if (k) { e.preventDefault(); const nx = NODES[(i + k + NODES.length) % NODES.length].id; onSel(nx); document.getElementById(`tab-${nx}`)?.focus(); }
            }}
            tabIndex={sel === n.id ? 0 : -1}
            className={cn("relative flex min-w-0 flex-1 items-center gap-3 rounded-xl border p-3 text-left transition-[border-color,background,box-shadow] md:flex-col md:items-start md:gap-2",
              sel === n.id ? "border-ink bg-surface shadow-card" : "border-rule bg-surface/60 hover:border-rule-strong",
              n.id === "C" && "border-dashed")}
          >
            {n.stage ? <StageMark stage={n.stage} /> : <span aria-hidden className="grid size-7 place-items-center rounded-full border-2 border-rule-strong font-mono text-xs text-muted">{n.id === "in" ? "in" : "✓"}</span>}
            <span className="min-w-0">
              <span className="block font-medium">{n.name}</span>
              <span className="block text-xs text-muted">{n.sub}</span>
            </span>
            {sel === n.id && <span className="absolute inset-x-3 -bottom-px h-0.5 rounded-full bg-ink" />}
          </button>
          {i < NODES.length - 1 && (
            <span aria-hidden className="flex justify-center text-muted md:px-1">
              <ArrowDown className="size-4 md:hidden" /><ArrowRight className="hidden size-4 md:block" />
            </span>
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

export default function How() {
  const [sel, setSel] = React.useState<NodeId>("A");
  const [q, setQ] = React.useState("");
  const d = DETAIL[sel];
  const terms = GLOSSARY.filter((g) => (g.term + " " + g.plain).toLowerCase().includes(q.toLowerCase()));

  React.useEffect(() => {
    if (window.location.hash === "#glossary") document.getElementById("glossary")?.scrollIntoView();
  }, []);

  return (
    <div className="space-y-10">
      <PageHeader title="How it works"
        lead="Your prompt goes through four steps. Rules do almost all the work; a small model helps only when they can't. Click a step to see what it does, with a real example." />
      <section aria-label="Architecture">
        <Diagram sel={sel} onSel={setSel} />
        <LazyMotion features={() => import("framer-motion").then((r) => r.domAnimation)}>
        <AnimatePresence mode="wait" initial={false}>
        <m.div key={sel} id="stage-detail" role="tabpanel" aria-labelledby={`tab-${sel}`}
          initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.18 }}
          className="mt-5 grid gap-6 rounded-2xl border border-rule bg-surface p-5 shadow-card sm:p-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
          <div>
            <h2 className="font-display text-2xl font-semibold">{d.title}</h2>
            <p className="mt-3 text-[1.0625rem] text-ink-2">{d.plain}</p>
            <ul className="mt-4 space-y-2">
              {d.points.map((p) => <li key={p} className="flex gap-2 text-[0.9375rem]"><span aria-hidden className="mt-2.5 size-1.5 shrink-0 rounded-full bg-ink" />{p}</li>)}
            </ul>
          </div>
          <div>
            <p className="eyebrow mb-2">Real example</p>
            {d.example}
          </div>
        </m.div>
        </AnimatePresence>
        </LazyMotion>
      </section>

      <section id="glossary" aria-labelledby="glossary-h" className="scroll-mt-20">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 id="glossary-h" className="font-display text-2xl font-semibold">Glossary</h2>
            <p className="text-ink-2">Every technical word in the app, in plain language.</p>
          </div>
          <label className="relative w-full sm:w-72">
            <span className="sr-only">Search the glossary</span>
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search terms…"
              className="h-10 w-full rounded-lg border border-rule-strong bg-surface pl-9 pr-3 outline-none focus:border-focus focus:ring-2 focus:ring-focus/25" />
          </label>
        </div>
        {terms.length ? (
          <dl className="grid gap-x-8 gap-y-4 md:grid-cols-2" data-testid="glossary">
            {terms.map((g) => (
              <div key={g.term} className="border-t border-rule pt-3">
                <dt className="font-display text-lg font-semibold">{g.term}</dt>
                <dd className="mt-0.5 text-[0.9375rem] text-ink-2">{g.plain}</dd>
              </div>
            ))}
          </dl>
        ) : <p className="text-muted">No term matches “{q}”.</p>}
      </section>
    </div>
  );
}
