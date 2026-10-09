import * as React from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown, CornerDownLeft, Lightbulb, Loader2, Paperclip, Redo2, Undo2, Wand2 } from "lucide-react";
import { api, type Attachment, type Category, type Target, type TokenCount } from "@/lib/api";
import { useStore } from "@/lib/store";
import { ATTACHMENT, CATEGORY } from "@/lib/labels";
import { Button } from "@/components/ui/button";
import { Segmented } from "@/components/ui/segmented";
import { Select } from "@/components/ui/select";
import { InfoTip, Tooltip } from "@/components/ui/tooltip";
import { Kbd } from "@/components/ui/kbd";
import { Badge } from "@/components/ui/badge";
import { cn, modKey } from "@/lib/utils";

function escapeRe(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** The text with the hovered phrases wrapped in <mark>, drawn behind the transparent textarea. */
function Mirror({ text, phrases }: { text: string; phrases: string[] }) {
  const usable = phrases.filter((p) => p.trim().length > 1);
  if (!usable.length) return <>{text + "\n"}</>;
  const re = new RegExp(`(${usable.map(escapeRe).join("|")})`, "gi");
  return <>{text.split(re).map((part, i) => (i % 2 ? <mark key={i}>{part}</mark> : <span key={i}>{part}</span>))}{"\n"}</>;
}

export function useLiveTokens(text: string) {
  const [counts, setCounts] = React.useState<Record<Target, TokenCount> | null>(null);
  React.useEffect(() => {
    const ctl = new AbortController();
    const t = setTimeout(() => {
      api.tokens(text, ctl.signal).then(setCounts).catch(() => { /* counter is best-effort */ });
    }, 200);
    return () => { clearTimeout(t); ctl.abort(); };
  }, [text]);
  return counts;
}

export const FIELD_LABEL = "mb-1.5 flex items-center gap-1 text-sm font-medium text-ink-2";

export function Composer({ onSubmit, busy, highlight }:
  { onSubmit: () => void; busy: boolean; highlight: string[] }) {
  const { draft, setDraft, undo, redo, canUndo, canRedo, options } = useStore();
  const navigate = useNavigate();
  const [showContext, setShowContext] = React.useState(!!draft.context);
  const area = React.useRef<HTMLTextAreaElement>(null);
  const mirror = React.useRef<HTMLDivElement>(null);
  const fullText = draft.context ? `${draft.prompt}\n\n${draft.context}` : draft.prompt;
  const counts = useLiveTokens(fullText);
  const tk = counts?.[draft.target];

  React.useEffect(() => { if (draft.context) setShowContext(true); }, [draft.context]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    const mod = e.ctrlKey || e.metaKey;
    if (mod && e.key === "Enter") { e.preventDefault(); onSubmit(); }
    else if (mod && !e.shiftKey && e.key.toLowerCase() === "z") { e.preventDefault(); undo(); }
    else if (mod && (e.key.toLowerCase() === "y" || (e.shiftKey && e.key.toLowerCase() === "z"))) { e.preventDefault(); redo(); }
  };

  const syncScroll = () => {
    if (mirror.current && area.current) mirror.current.scrollTop = area.current.scrollTop;
  };

  const categoryOptions: { value: Category; label: string; hint?: string }[] = [
    { value: "auto", label: CATEGORY.auto, hint: "Stage A decides" },
    ...(["closed_qa", "information_extraction", "classification", "summarization", "coding"] as const)
      .map((c) => ({ value: c as Category, label: CATEGORY[c] })),
    { value: "image_generation", label: "Image generation…", hint: "Opens Image mode" },
  ];

  return (
    <form
      className="flex flex-col gap-5"
      onSubmit={(e) => { e.preventDefault(); onSubmit(); }}
      aria-label="Prompt to optimize"
    >
      <div data-tour="prompt">
        <div className="mb-1.5 flex items-end justify-between gap-2">
          <label htmlFor="prompt" className="text-sm font-medium text-ink-2">Your prompt</label>
          <div className="flex items-center gap-1">
            <Tooltip content={`Undo (${modKey}+Z)`}>
              <Button variant="ghost" size="icon" className="size-8" onClick={undo} disabled={!canUndo} aria-label="Undo"><Undo2 /></Button>
            </Tooltip>
            <Tooltip content={`Redo (${modKey}+Shift+Z)`}>
              <Button variant="ghost" size="icon" className="size-8" onClick={redo} disabled={!canRedo} aria-label="Redo"><Redo2 /></Button>
            </Tooltip>
          </div>
        </div>
        <div className="relative rounded-xl border border-rule-strong bg-surface shadow-card focus-within:border-focus focus-within:ring-2 focus-within:ring-focus/25">
          <div className="relative">
          <div
            ref={mirror}
            aria-hidden
            className="mirror proof pointer-events-none absolute inset-0 overflow-hidden px-4 py-3 text-[0.9375rem]"
          >
            <Mirror text={draft.prompt} phrases={highlight} />
          </div>
          <textarea
            ref={area}
            id="prompt"
            value={draft.prompt}
            onChange={(e) => setDraft({ prompt: e.target.value }, { record: false })}
            onKeyDown={onKeyDown}
            onScroll={syncScroll}
            rows={6}
            spellCheck={false}
            placeholder="e.g. write code to get all permutations of a string"
            className="proof relative block min-h-40 w-full resize-y rounded-xl bg-transparent px-4 py-3 text-[0.9375rem] text-ink caret-ink outline-none placeholder:text-muted/80"
            aria-describedby="prompt-hint"
          />
          </div>
          <div className="flex items-center justify-between gap-2 border-t border-rule px-3 py-2 text-sm" id="prompt-hint">
            <span className="flex items-center gap-1.5 text-muted" aria-live="polite" data-testid="live-tokens">
              <span className="tabular font-mono font-medium text-ink">{tk ? (tk.exact ? "" : "≈") + tk.tokens : "–"}</span>
              input tokens for {draft.target === "gpt" ? "GPT" : draft.target === "claude" ? "Claude" : "Gemini"}
              {tk && <Badge tone={tk.exact ? "b" : "outline"}>{tk.exact ? "exact" : "approx."}</Badge>}
              <InfoTip>
                What you'd send without PromptOpt: your prompt{draft.context ? " plus the pasted text" : ""}.
                GPT is counted exactly with OpenAI's tokenizer (o200k_base); Claude and Gemini are estimated as characters ÷ 4.
              </InfoTip>
            </span>
            <span className="hidden items-center gap-1 text-muted sm:flex"><Kbd>{modKey}</Kbd><Kbd>↵</Kbd> optimize</span>
          </div>
        </div>
      </div>

      <div>
        <button
          type="button"
          onClick={() => setShowContext((v) => !v)}
          aria-expanded={showContext}
          aria-controls="context"
          className="flex items-center gap-1.5 text-sm font-medium text-ink-2 hover:text-ink"
        >
          <ChevronDown className={cn("size-4 transition-transform", !showContext && "-rotate-90")} aria-hidden />
          Pasted text <span className="font-normal text-muted">(optional)</span>
        </button>
        {showContext && (
          <textarea
            id="context"
            value={draft.context}
            onChange={(e) => setDraft({ context: e.target.value }, { record: false })}
            onKeyDown={onKeyDown}
            rows={4}
            placeholder="Paste the passage, article or code your prompt is about. It is kept separate from your instruction."
            className="proof mt-2 block w-full resize-y rounded-xl border border-rule-strong bg-surface px-4 py-3 text-[0.8125rem] outline-none focus:border-focus focus:ring-2 focus:ring-focus/25"
          />
        )}
      </div>

      <div data-tour="target">
        <div className={FIELD_LABEL} id="target-label">
          Target LLM
          <InfoTip>The model you'll paste the prompt into. The content is the same for all three; only the layout changes (Claude: XML tags, GPT: ### headings, Gemini: plain labels).</InfoTip>
        </div>
        <Segmented<Target>
          label="Target LLM"
          value={draft.target}
          onChange={(v) => setDraft({ target: v })}
          options={[{ value: "gpt", label: "GPT" }, { value: "gemini", label: "Gemini" }, { value: "claude", label: "Claude" }]}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div data-tour="category">
          <label className={FIELD_LABEL} htmlFor="category">
            Category
            <InfoTip>Leave on auto-detect and Stage A guesses the kind of task. If you pick one, your choice wins and the app shows when Stage A disagreed.</InfoTip>
          </label>
          <Select<Category>
            id="category"
            label="Category"
            value={draft.category}
            onChange={(v) => {
              if (v === "image_generation") navigate("/image");
              else setDraft({ category: v });
            }}
            options={categoryOptions}
          />
        </div>
        <div>
          <label className={FIELD_LABEL} htmlFor="attachment">
            Attachment
            <InfoTip>Will you attach a file when you send the prompt? Pick its type and the prompt will tell the model how to use it. It changes the wording, not the category.</InfoTip>
          </label>
          <Select<Attachment>
            id="attachment"
            label="Attachment type"
            value={draft.attachment}
            onChange={(v) => setDraft({ attachment: v })}
            options={(options?.attachment_types ?? (Object.keys(ATTACHMENT) as Attachment[]))
              .map((a) => ({ value: a, label: ATTACHMENT[a] ?? a }))}
          />
        </div>
      </div>
      {draft.attachment !== "none" && (
        <div>
          <label className={FIELD_LABEL} htmlFor="attachment-name"><Paperclip className="size-3.5" aria-hidden /> File name <span className="font-normal text-muted">(optional)</span></label>
          <input
            id="attachment-name"
            value={draft.attachmentName}
            onChange={(e) => setDraft({ attachmentName: e.target.value }, { record: false })}
            placeholder="e.g. lecture-notes.pdf"
            className="h-10 w-full rounded-lg border border-rule-strong bg-surface px-3 text-[0.9375rem] outline-none focus:border-focus focus:ring-2 focus:ring-focus/25"
          />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" variant="primary" size="lg" disabled={busy || !draft.prompt.trim()} className="min-w-44 flex-1 sm:flex-none" data-testid="optimize">
          {busy ? <Loader2 className="animate-spin" aria-hidden /> : <Wand2 aria-hidden />}
          {busy ? "Optimizing…" : "Optimize"}
          <span className="ml-1 hidden items-center gap-0.5 opacity-70 sm:flex" aria-hidden><CornerDownLeft className="size-3.5" /></span>
        </Button>
        {!draft.prompt.trim() && (
          <span className="flex items-center gap-1.5 text-sm text-muted"><Lightbulb className="size-4" aria-hidden /> Type a prompt, or pick an example.</span>
        )}
      </div>
    </form>
  );
}
