import * as TG from "@radix-ui/react-toggle-group";
import { cn } from "@/lib/utils";

/** A single-choice segmented control (radio-group semantics via Radix ToggleGroup). */
export function Segmented<T extends string>({ value, onChange, options, label, className, size = "md" }: {
  value: T; onChange: (v: T) => void; label: string; className?: string; size?: "sm" | "md";
  options: { value: T; label: React.ReactNode; hint?: string; disabled?: boolean }[];
}) {
  return (
    <TG.Root
      type="single"
      value={value}
      onValueChange={(v) => v && onChange(v as T)}
      aria-label={label}
      className={cn("grid auto-cols-fr grid-flow-col gap-1 rounded-lg bg-sunken p-1", className)}
    >
      {options.map((o) => (
        <TG.Item
          key={o.value}
          value={o.value}
          disabled={o.disabled}
          title={o.hint}
          className={cn(
            "rounded-md px-3 font-medium text-muted transition-colors hover:text-ink disabled:opacity-40 data-[state=on]:bg-surface data-[state=on]:text-ink data-[state=on]:shadow-card",
            size === "sm" ? "h-8 text-sm" : "h-9 text-[0.9375rem]")}
        >
          {o.label}
        </TG.Item>
      ))}
    </TG.Root>
  );
}
