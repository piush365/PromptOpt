import { diffWords } from "@/lib/diff";

/** Inline diff: added words on green, removed words struck through on red. Screen readers hear "added"/"removed". */
export function Diff({ before, after }: { before: string; after: string }) {
  const parts = diffWords(before, after);
  return (
    <div className="proof rounded-lg border border-rule bg-sunken/60 px-3 py-2 text-ink-2">
      {parts.map((p, i) =>
        p.kind === "same" ? <span key={i}>{p.text}</span>
          : p.kind === "add" ? (
            <ins key={i} className="rounded-sm bg-add-bg text-add no-underline decoration-2">
              <span className="sr-only">[added: </span>{p.text}<span className="sr-only">]</span>
            </ins>
          ) : (
            <del key={i} className="mr-0.5 rounded-sm bg-del-bg text-del decoration-del/70">
              <span className="sr-only">[removed: </span>{p.text}<span className="sr-only">]</span>
            </del>
          ))}
    </div>
  );
}
