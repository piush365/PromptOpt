import { useStore } from "@/lib/store";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Kbd } from "@/components/ui/kbd";
import { NAV } from "@/components/Layout";
import { modKey } from "@/lib/utils";

const GROUPS: { title: string; keys: [string[], string][] }[] = [
  { title: "Optimize", keys: [
    [[modKey, "Enter"], "Optimize the prompt"],
    [[modKey, "Z"], "Undo a change to the input"],
    [[modKey, "Shift", "Z"], "Redo"],
  ] },
  { title: "Anywhere", keys: [
    [["?"], "Show these shortcuts"],
    [["D"], "Switch light / dark theme"],
    [["Tab"], "Move between controls (focus is always visible)"],
    [["Esc"], "Close a dialog"],
  ] },
];

export function ShortcutsDialog() {
  const { shortcutsOpen, setShortcutsOpen } = useStore();
  return (
    <Dialog open={shortcutsOpen} onOpenChange={setShortcutsOpen}>
      <DialogContent title="Keyboard shortcuts" description="Single-letter keys work when you're not typing in a field.">
        <div className="grid gap-6 sm:grid-cols-2">
          {[...GROUPS, { title: "Go to page", keys: NAV.map((n, i) => [["Alt", String(i + 1)], n.label] as [string[], string]) }].map((g) => (
            <section key={g.title} className={g.title === "Go to page" ? "sm:col-span-2" : ""}>
              <h3 className="eyebrow mb-2">{g.title}</h3>
              <dl className={g.title === "Go to page" ? "grid gap-x-6 gap-y-2 sm:grid-cols-2" : "space-y-2"}>
                {g.keys.map(([ks, what]) => (
                  <div key={what} className="flex items-center justify-between gap-3 text-[0.9375rem]">
                    <dt className="text-ink-2">{what}</dt>
                    <dd className="flex shrink-0 gap-1">{ks.map((k) => <Kbd key={k}>{k}</Kbd>)}</dd>
                  </div>
                ))}
              </dl>
            </section>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
