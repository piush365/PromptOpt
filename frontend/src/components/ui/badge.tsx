import * as React from "react";
import { cn } from "@/lib/utils";

const tones = {
  neutral: "bg-sunken text-ink-2 border-rule",
  a: "bg-a-soft text-a border-transparent",
  b: "bg-b-soft text-b border-transparent",
  c: "bg-c-soft text-c border-transparent",
  add: "bg-add-bg text-add border-transparent",
  del: "bg-del-bg text-del border-transparent",
  outline: "bg-transparent text-ink-2 border-rule-strong",
} as const;

export function Badge({ tone = "neutral", className, ...p }:
  React.HTMLAttributes<HTMLSpanElement> & { tone?: keyof typeof tones }) {
  return (
    <span
      className={cn("inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 font-mono text-xs font-medium leading-tight whitespace-nowrap [&_svg]:size-3", tones[tone], className)}
      {...p}
    />
  );
}
