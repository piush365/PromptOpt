import * as React from "react";
import * as D from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export const Dialog = D.Root;
export const DialogTrigger = D.Trigger;
export const DialogClose = D.Close;

export function DialogContent({ title, description, children, className, wide }:
  { title: React.ReactNode; description?: React.ReactNode; children: React.ReactNode; className?: string; wide?: boolean }) {
  return (
    <D.Portal>
      <D.Overlay className="fixed inset-0 z-40 bg-ink/40 backdrop-blur-[2px] dark:bg-black/60" />
      <D.Content
        className={cn(
          "fixed left-1/2 top-1/2 z-50 flex max-h-[calc(100dvh-2rem)] w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 flex-col rounded-2xl border border-rule bg-surface shadow-card",
          wide ? "max-w-5xl" : "max-w-lg", className)}
      >
        <div className="flex items-start justify-between gap-4 border-b border-rule px-6 py-4">
          <div className="min-w-0">
            <D.Title className="font-display text-xl font-semibold">{title}</D.Title>
            {description ? <D.Description className="mt-0.5 text-sm text-muted">{description}</D.Description>
              : <D.Description className="sr-only">Details</D.Description>}
          </div>
          <D.Close className="grid size-9 shrink-0 place-items-center rounded-lg text-muted hover:bg-sunken hover:text-ink" aria-label="Close">
            <X className="size-5" />
          </D.Close>
        </div>
        <div className="min-h-0 overflow-y-auto px-6 py-5">{children}</div>
      </D.Content>
    </D.Portal>
  );
}
