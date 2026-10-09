import * as React from "react";
import { AlertTriangle, Check, Copy } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function ErrorBox({ message, onRetry, className }: { message: string; onRetry?: () => void; className?: string }) {
  return (
    <div role="alert" className={cn("flex items-start gap-3 rounded-xl border border-del/30 bg-del-bg px-4 py-3 text-[0.9375rem]", className)}>
      <AlertTriangle className="mt-0.5 size-5 shrink-0 text-del" aria-hidden />
      <p className="min-w-0 flex-1 text-ink">{message}</p>
      {onRetry && <Button size="sm" variant="secondary" onClick={onRetry}>Try again</Button>}
    </div>
  );
}

export function EmptyState({ icon, title, children, action, className }:
  { icon?: React.ReactNode; title: string; children?: React.ReactNode; action?: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-rule-strong px-6 py-12 text-center", className)}>
      {icon && <div className="grid size-12 place-items-center rounded-full bg-sunken text-muted [&_svg]:size-6">{icon}</div>}
      <h2 className="font-display text-lg font-semibold">{title}</h2>
      {children && <div className="max-w-md text-[0.9375rem] text-muted">{children}</div>}
      {action}
    </div>
  );
}

export function CopyButton({ text, label = "Copy", what = "Prompt", size = "sm", variant = "secondary" }:
  { text: string; label?: string; what?: string; size?: "sm" | "md"; variant?: "secondary" | "primary" | "ghost" }) {
  const [done, setDone] = React.useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setDone(true);
      toast.success(`${what} copied`);
      setTimeout(() => setDone(false), 1500);
    } catch {
      toast.error("Couldn't copy. Select the text and press Ctrl+C instead.");
    }
  };
  return (
    <Button size={size} variant={variant} onClick={copy} aria-label={`${label} ${what.toLowerCase()}`} data-copy>
      {done ? <Check aria-hidden /> : <Copy aria-hidden />}
      {done ? "Copied" : label}
    </Button>
  );
}

export function PageHeader({ title, lead, actions }: { title: string; lead?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="font-display text-3xl font-semibold sm:text-[2.5rem]">{title}</h1>
        {lead && <p className="mt-2 max-w-3xl text-[1.0625rem] text-ink-2">{lead}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

export function StageMark({ stage, className }: { stage: "A" | "B" | "C" | "R"; className?: string }) {
  const tone = { A: "bg-a text-white dark:text-paper", B: "bg-b text-white dark:text-paper", C: "bg-c text-white dark:text-paper",
    R: "bg-ink text-paper" }[stage];
  return (
    <span aria-hidden className={cn("grid size-7 shrink-0 place-items-center rounded-full font-mono text-sm font-semibold", tone, className)}>
      {stage}
    </span>
  );
}
