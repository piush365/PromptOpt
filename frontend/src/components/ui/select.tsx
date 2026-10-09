import * as S from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export function Select<T extends string>({ value, onChange, options, label, id, className }: {
  value: T; onChange: (v: T) => void; label: string; id?: string; className?: string;
  options: { value: T; label: string; hint?: string; disabled?: boolean; group?: string }[];
}) {
  return (
    <S.Root value={value} onValueChange={(v) => onChange(v as T)}>
      <S.Trigger
        id={id}
        aria-label={label}
        className={cn("flex h-10 w-full items-center justify-between gap-2 rounded-lg border border-rule-strong bg-surface px-3 text-left text-[0.9375rem] hover:border-muted data-[placeholder]:text-muted", className)}
      >
        <span className="truncate"><S.Value /></span>
        <S.Icon><ChevronDown className="size-4 text-muted" /></S.Icon>
      </S.Trigger>
      <S.Portal>
        <S.Content position="popper" sideOffset={6}
          className="z-50 max-h-[min(24rem,var(--radix-select-content-available-height))] min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-xl border border-rule bg-surface shadow-card">
          <S.Viewport className="p-1">
            {options.map((o) => (
              <S.Item key={o.value} value={o.value} disabled={o.disabled}
                className="relative flex cursor-pointer select-none flex-col rounded-md py-2 pl-8 pr-3 text-[0.9375rem] outline-none data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50 data-[highlighted]:bg-sunken">
                <S.ItemIndicator className="absolute left-2 top-2.5"><Check className="size-4" /></S.ItemIndicator>
                <S.ItemText>{o.label}</S.ItemText>
                {o.hint && <span className="text-xs text-muted">{o.hint}</span>}
              </S.Item>
            ))}
          </S.Viewport>
        </S.Content>
      </S.Portal>
    </S.Root>
  );
}
