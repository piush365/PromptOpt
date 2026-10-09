import { cn } from "@/lib/utils";

export function Kbd({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <kbd className={cn("inline-flex h-5 min-w-5 items-center justify-center rounded border border-rule-strong bg-surface px-1 font-mono text-[0.6875rem] font-medium text-ink-2 shadow-[0_1px_0_var(--rule-strong)]", className)}>
      {children}
    </kbd>
  );
}
