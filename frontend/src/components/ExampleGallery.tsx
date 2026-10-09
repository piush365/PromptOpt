import * as React from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Code2, FileSearch, Image, ListChecks, MessageSquareText, Paperclip, ScrollText } from "lucide-react";
import { api, type Example } from "@/lib/api";
import { useStore } from "@/lib/store";
import { CATEGORY, TARGET, ATTACHMENT } from "@/lib/labels";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBox } from "@/components/Feedback";
import { cn } from "@/lib/utils";

const ICON: Record<string, React.ElementType> = {
  coding: Code2, closed_qa: MessageSquareText, information_extraction: FileSearch, classification: ListChecks,
  summarization: ScrollText, attachment: Paperclip, image_generation: Image,
};

let cache: Example[] | null = null;

export function useExamples() {
  const [items, setItems] = React.useState<Example[] | null>(cache);
  const [error, setError] = React.useState<string | null>(null);
  const load = React.useCallback(() => {
    setError(null);
    api.examples().then((r) => { cache = r.examples; setItems(r.examples); }).catch((e) => setError(e.message));
  }, []);
  React.useEffect(() => { if (!cache) load(); }, [load]);
  return { items, error, reload: load };
}

/** Load an example into Optimize (or Image mode) and run it. */
export function useRunExample() {
  const { setDraft, setImageDraft, requestRun, requestImageRun } = useStore();
  const navigate = useNavigate();
  return (ex: Example) => {
    if (ex.category === "image_generation") {
      setImageDraft({ prompt: ex.prompt, target: ex.target as never, accepted: [] });
      requestImageRun();
      navigate("/image");
      return;
    } else {
      setDraft({
        prompt: ex.prompt, context: ex.context ?? "", target: ex.target as never, category: ex.category,
        attachment: ex.attachment_type ?? "none", attachmentName: "",
      });
      navigate("/");
    }
    requestRun();
  };
}

export function ExampleGallery({ compact, onPicked }: { compact?: boolean; onPicked?: () => void }) {
  const { items, error, reload } = useExamples();
  const run = useRunExample();
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!items) {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
      </div>
    );
  }
  return (
    <ul className={cn("grid gap-3", compact ? "sm:grid-cols-2" : "sm:grid-cols-2 xl:grid-cols-3")} data-testid="example-gallery">
      {items.map((ex) => {
        const Icon = ICON[ex.kind] ?? Paperclip;
        return (
          <li key={ex.id}>
            <button
              onClick={() => { run(ex); onPicked?.(); }}
              data-example={ex.id}
              className="group flex h-full w-full flex-col gap-2 rounded-xl border border-rule bg-surface p-4 text-left shadow-card transition-[border-color,transform] hover:-translate-y-0.5 hover:border-rule-strong"
            >
              <span className="flex items-center gap-2">
                <Icon className="size-4 text-muted" aria-hidden />
                <span className="font-medium">{ex.title}</span>
                {ex.demo && <Badge tone="outline" className="ml-auto">demo</Badge>}
              </span>
              <span className="proof line-clamp-2 text-[0.8125rem] text-ink-2">“{ex.prompt}”</span>
              <span className="text-sm leading-snug text-muted">{ex.why}</span>
              <span className="mt-auto flex flex-wrap items-center gap-1.5 pt-1">
                <Badge>{ex.kind === "attachment" ? ATTACHMENT[ex.attachment_type ?? "other"] + " attached"
                  : CATEGORY[ex.kind] ?? ex.kind}</Badge>
                <Badge tone="outline">{TARGET[ex.target]}</Badge>
                {ex.context && <Badge tone="outline">+ pasted text</Badge>}
                <ArrowRight className="ml-auto size-4 text-muted transition-transform group-hover:translate-x-0.5" aria-hidden />
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
