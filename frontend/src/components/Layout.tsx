import * as React from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import * as D from "@radix-ui/react-dialog";
import {
  BarChart3, BookOpen, Columns2, FlaskConical, History, Image, Keyboard, Menu, Moon, Settings2, Sparkles, Sun,
  Route, X,
} from "lucide-react";
import { useStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export const NAV = [
  { to: "/", label: "Optimize", icon: Sparkles, hint: "Rewrite a prompt and see every step" },
  { to: "/compare", label: "Compare", icon: Columns2, hint: "Run the vague and the optimized prompt on a real model" },
  { to: "/suite", label: "Test suite", icon: FlaskConical, hint: "50 hand-checked cases with gold answers" },
  { to: "/results", label: "Results", icon: BarChart3, hint: "The final evaluation numbers" },
  { to: "/how", label: "How it works", icon: Route, hint: "The pipeline in plain English, and a glossary" },
  { to: "/history", label: "History", icon: History, hint: "Your past optimizations" },
  { to: "/image", label: "Image mode", icon: Image, hint: "Prompts for image generators" },
  { to: "/status", label: "Status", icon: Settings2, hint: "Which models and features are available" },
] as const;

function Wordmark() {
  return (
    <span className="flex items-center gap-2.5">
      <span aria-hidden className="flex items-center gap-[3px] rounded-lg bg-[#141a26] px-1.5 py-2 dark:ring-1 dark:ring-rule-strong">
        <span className="size-2 rounded-full bg-[#5b8def]" />
        <span className="size-2 rounded-full bg-[#2fb383]" />
        <span className="size-2 rounded-full bg-[#e9a23b]" />
      </span>
      <span className="font-display text-xl font-bold tracking-tight">PromptOpt</span>
    </span>
  );
}

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="Main" className="flex flex-col gap-0.5">
      {NAV.map(({ to, label, icon: Icon }, i) => (
        <NavLink
          key={to}
          to={to}
          end={to === "/"}
          onClick={onNavigate}
          data-tour={`nav-${to.slice(1) || "optimize"}`}
          className={({ isActive }) => cn(
            "group flex h-10 items-center gap-3 rounded-lg px-3 text-[0.9375rem] font-medium transition-colors",
            isActive ? "bg-surface text-ink shadow-card" : "text-ink-2 hover:bg-surface/60 hover:text-ink")}
        >
          <Icon className="size-[18px] shrink-0" aria-hidden />
          <span className="flex-1">{label}</span>
          <span className="hidden font-mono text-[0.6875rem] text-muted group-hover:inline" aria-hidden>Alt {i + 1}</span>
        </NavLink>
      ))}
    </nav>
  );
}

function StageCPill() {
  const { options } = useStore();
  if (!options) return null;
  const c = options.stage_c;
  const text = c.available ? `Stage C on · ${c.device?.toUpperCase() ?? ""}` : "Stage C off";
  return (
    <Tooltip content={c.available
      ? `The small model (${c.model}) is loaded on the ${c.device}. It runs only when the rules leave something unresolved.`
      : "The small Stage C model isn't loaded (run the app from .venv-gpu with the adapter installed). Everything else works; prompts that need it show Stage B's result."}>
      <NavLink to="/status" className="hidden items-center gap-2 rounded-full border border-rule bg-surface px-3 py-1 text-sm text-ink-2 hover:text-ink sm:flex">
        <span className={cn("size-2 rounded-full", c.available ? "bg-c" : "bg-rule-strong")} aria-hidden />
        {text}
      </NavLink>
    </Tooltip>
  );
}

export function Layout({ children }: { children: React.ReactNode }) {
  const { theme, toggleTheme, setShortcutsOpen, setTourOpen } = useStore();
  const [menu, setMenu] = React.useState(false);
  const loc = useLocation();
  const navigate = useNavigate();
  const current = NAV.find((n) => (n.to === "/" ? loc.pathname === "/" : loc.pathname.startsWith(n.to)));

  React.useEffect(() => {
    document.title = current && current.to !== "/" ? `${current.label} · PromptOpt` : "PromptOpt";
  }, [current]);

  // Global shortcuts: Alt+1..8 pages, ? help, D theme. Ignored while typing in a field.
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      const typing = el.closest("input, textarea, select, [contenteditable=true]");
      if (e.altKey && !e.ctrlKey && !e.metaKey && /^Digit[1-8]$/.test(e.code)) {
        e.preventDefault();
        navigate(NAV[Number(e.code.slice(5)) - 1].to);
        return;
      }
      if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === "?") { e.preventDefault(); setShortcutsOpen(true); }
      else if (e.key === "d" || e.key === "D") toggleTheme();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate, setShortcutsOpen, toggleTheme]);

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[15rem_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-4 focus:py-2 focus:shadow-card">
        Skip to content
      </a>

      {/* desktop sidebar */}
      <aside className="sticky top-0 hidden h-dvh flex-col gap-6 border-r border-rule px-3 py-5 lg:flex">
        <NavLink to="/" className="px-2" aria-label="PromptOpt home"><Wordmark /></NavLink>
        <NavList />
        <div className="mt-auto space-y-2 px-2 text-sm text-muted">
          <p className="leading-snug">Final-year project, WCE Sangli. Pipeline frozen at <span className="font-mono text-xs">frozen-for-test</span>.</p>
          <a href="/classic" className="inline-block underline decoration-rule-strong underline-offset-4 hover:text-ink">Open the classic UI</a>
        </div>
      </aside>

      <div className="min-w-0">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-rule bg-paper/85 px-4 backdrop-blur sm:px-6">
          <D.Root open={menu} onOpenChange={setMenu}>
            <D.Trigger asChild>
              <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open menu"><Menu className="size-5" /></Button>
            </D.Trigger>
            <D.Portal>
              <D.Overlay className="fixed inset-0 z-40 bg-ink/40 lg:hidden" />
              <D.Content className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col gap-6 bg-paper px-3 py-5 shadow-card lg:hidden">
                <div className="flex items-center justify-between px-2">
                  <D.Title asChild><span><Wordmark /></span></D.Title>
                  <D.Description className="sr-only">Pages</D.Description>
                  <D.Close asChild><Button variant="ghost" size="icon" aria-label="Close menu"><X className="size-5" /></Button></D.Close>
                </div>
                <NavList onNavigate={() => setMenu(false)} />
                <a href="/classic" className="mt-auto px-3 text-sm text-muted underline underline-offset-4">Open the classic UI</a>
              </D.Content>
            </D.Portal>
          </D.Root>
          <NavLink to="/" className="lg:hidden" aria-label="PromptOpt home"><Wordmark /></NavLink>
          <p className="hidden truncate text-sm text-muted lg:block">{current?.hint}</p>
          <div className="ml-auto flex items-center gap-1">
            <StageCPill />
            <Tooltip content="Take the 1-minute tour">
              <Button variant="ghost" size="icon" aria-label="Take the tour" onClick={() => { navigate("/"); setTourOpen(true); }}>
                <BookOpen className="size-[18px]" />
              </Button>
            </Tooltip>
            <Tooltip content="Keyboard shortcuts (?)">
              <Button variant="ghost" size="icon" aria-label="Keyboard shortcuts" onClick={() => setShortcutsOpen(true)}>
                <Keyboard className="size-[18px]" />
              </Button>
            </Tooltip>
            <Tooltip content={theme === "dark" ? "Switch to light theme (D)" : "Switch to dark theme (D)"}>
              <Button variant="ghost" size="icon" onClick={toggleTheme} data-testid="theme-toggle"
                aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}>
                {theme === "dark" ? <Sun className="size-[18px]" /> : <Moon className="size-[18px]" />}
              </Button>
            </Tooltip>
          </div>
        </header>
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[90rem] px-4 py-6 outline-none sm:px-6 lg:px-8 lg:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
