import * as React from "react";
import * as T from "@radix-ui/react-tooltip";
import { Info } from "lucide-react";
import { cn } from "@/lib/utils";

export const TooltipProvider = T.Provider;

export function Tooltip({ content, children, side = "top" }:
  { content: React.ReactNode; children: React.ReactNode; side?: "top" | "bottom" | "left" | "right" }) {
  return (
    <T.Root delayDuration={150}>
      <T.Trigger asChild>{children}</T.Trigger>
      <T.Portal>
        <T.Content
          side={side}
          sideOffset={6}
          collisionPadding={12}
          className="z-50 max-w-72 rounded-lg bg-ink px-3 py-2 text-[0.8125rem] leading-snug text-paper shadow-card data-[state=delayed-open]:animate-in"
        >
          {content}
          <T.Arrow className="fill-ink" />
        </T.Content>
      </T.Portal>
    </T.Root>
  );
}

/** The small (i) next to every metric and technical word. */
export function InfoTip({ children, label = "What does this mean?", className }:
  { children: React.ReactNode; label?: string; className?: string }) {
  return (
    <Tooltip content={children}>
      <button
        type="button"
        aria-label={label}
        className={cn("inline-grid size-5 shrink-0 place-items-center rounded-full text-muted hover:text-ink align-middle", className)}
      >
        <Info className="size-3.5" aria-hidden />
      </button>
    </Tooltip>
  );
}
