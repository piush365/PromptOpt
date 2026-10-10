import { SpellCheck, Wand2 } from "lucide-react";
import type { Typo } from "@/lib/api";
import { Button } from "@/components/ui/button";

/** Replace typos in `text`. Offsets come from the prompt as it was sent; if the user has edited it since, the word is
 *  looked up again (first occurrence as a whole word), and skipped if it is gone. */
export function applyFixes(text: string, fixes: { typo: Typo; to: string }[]): string {
  const located = fixes.map(({ typo, to }) => {
    if (text.slice(typo.start, typo.end) === typo.word) return { start: typo.start, end: typo.end, to };
    const m = new RegExp(`\\b${typo.word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`).exec(text);
    return m ? { start: m.index, end: m.index + typo.word.length, to } : null;
  }).filter((x): x is { start: number; end: number; to: string } => x !== null);
  return located.sort((a, b) => b.start - a.start)
    .reduce((t, f) => t.slice(0, f.start) + f.to + t.slice(f.end), text);
}

/** "Possible typos": suggestions only. Clicking one fixes that word in the prompt and runs the optimizer again. */
export function SpellingCard({ typos, prompt, onApply }: { typos: Typo[]; prompt: string; onApply: (text: string) => void }) {
  if (!typos.length) return null;
  const fixAll = () => onApply(applyFixes(prompt, typos.map((t) => ({ typo: t, to: t.suggestions[0] }))));
  return (
    <section className="mb-4 rounded-xl border border-c/30 bg-c-soft px-4 py-3" data-testid="spelling" aria-label="Possible typos">
      <div className="flex flex-wrap items-center gap-2">
        <SpellCheck className="size-4 text-c" aria-hidden />
        <p className="font-medium">Possible typos</p>
        <p className="text-sm text-muted">Nothing is changed unless you pick a word. The optimizer keeps your words as typed.</p>
        {typos.length > 1 && (
          <Button size="sm" variant="secondary" className="ml-auto" onClick={fixAll} data-testid="spelling-fix-all">
            <Wand2 aria-hidden /> Fix all
          </Button>
        )}
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-2">
        {typos.map((t) => (
          <li key={`${t.start}-${t.word}`} className="flex flex-wrap items-center gap-1.5 text-sm">
            <span className="font-mono text-del line-through decoration-del/60">{t.word}</span>
            <span aria-hidden className="text-muted">→</span>
            {t.suggestions.map((s) => (
              <button key={s} type="button" onClick={() => onApply(applyFixes(prompt, [{ typo: t, to: s }]))}
                aria-label={`Replace ${t.word} with ${s}`}
                className="rounded-md border border-rule bg-surface px-2 py-0.5 font-mono text-ink transition-colors hover:border-b hover:text-b">
                {s}
              </button>
            ))}
          </li>
        ))}
      </ul>
    </section>
  );
}
