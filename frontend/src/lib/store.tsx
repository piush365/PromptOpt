import * as React from "react";
import { api, type Attachment, type Category, type ImageResult, type ImageTarget, type OptimizeResult,
  type Options, type Target } from "./api";

export interface Draft {
  prompt: string;
  context: string;
  target: Target;
  category: Category;
  attachment: Attachment;
  attachmentName: string;
}

export const EMPTY_DRAFT: Draft = {
  prompt: "", context: "", target: "gpt", category: "auto", attachment: "none", attachmentName: "",
};

export interface ImageDraft { prompt: string; target: ImageTarget; accepted: string[] }

type Theme = "light" | "dark";

interface Store {
  options: Options | null;
  optionsError: string | null;
  draft: Draft;
  setDraft: (patch: Partial<Draft>, opts?: { record?: boolean }) => void;
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  result: OptimizeResult | null;
  setResult: (r: OptimizeResult | null) => void;
  imageDraft: ImageDraft;
  setImageDraft: (patch: Partial<ImageDraft>) => void;
  imageResult: ImageResult | null;
  setImageResult: (r: ImageResult | null) => void;
  /** a request to run right after a page opens (example gallery, history "reopen") */
  pendingRun: number;
  requestRun: () => void;
  clearRun: () => void;
  /** the same for Image mode (kept apart so the page being left can't take the other page's run) */
  pendingImageRun: number;
  requestImageRun: () => void;
  clearImageRun: () => void;
  theme: Theme;
  toggleTheme: () => void;
  shortcutsOpen: boolean;
  setShortcutsOpen: (v: boolean) => void;
  tourOpen: boolean;
  setTourOpen: (v: boolean) => void;
}

const Ctx = React.createContext<Store | null>(null);

function safeGet(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
function safeSet(key: string, v: string) {
  try { localStorage.setItem(key, v); } catch { /* private mode: ignore */ }
}

export function StoreProvider({ children }: { children: React.ReactNode }) {
  const [options, setOptions] = React.useState<Options | null>(null);
  const [optionsError, setOptionsError] = React.useState<string | null>(null);
  const [draft, setDraftState] = React.useState<Draft>(() => {
    try { return { ...EMPTY_DRAFT, ...JSON.parse(safeGet("po-draft") || "{}") }; } catch { return EMPTY_DRAFT; }
  });
  // Undo/redo for the input: snapshots of the whole draft. Typing is grouped (a snapshot per pause).
  const past = React.useRef<Draft[]>([]);
  const future = React.useRef<Draft[]>([]);
  const lastSnap = React.useRef(0);
  const [, force] = React.useReducer((x: number) => x + 1, 0);
  const [result, setResult] = React.useState<OptimizeResult | null>(null);
  const [imageDraft, setImageDraftState] = React.useState<ImageDraft>({ prompt: "", target: "dalle", accepted: [] });
  const [imageResult, setImageResult] = React.useState<ImageResult | null>(null);
  const [pendingRun, setPendingRun] = React.useState(0);
  const [pendingImageRun, setPendingImageRun] = React.useState(0);
  const [theme, setTheme] = React.useState<Theme>(() =>
    document.documentElement.classList.contains("dark") ? "dark" : "light");
  const [shortcutsOpen, setShortcutsOpen] = React.useState(false);
  const [tourOpen, setTourOpen] = React.useState(false);

  React.useEffect(() => {
    api.options().then(setOptions).catch((e) => setOptionsError(e.message));
  }, []);

  React.useEffect(() => { safeSet("po-draft", JSON.stringify(draft)); }, [draft]);

  const draftRef = React.useRef(draft);
  const commit = (next: Draft) => { draftRef.current = next; setDraftState(next); force(); };

  const setDraft = React.useCallback((patch: Partial<Draft>, opts?: { record?: boolean }) => {
    const cur = draftRef.current;
    const now = Date.now();
    const typing = opts?.record === false;
    if (!typing || now - lastSnap.current > 800) {
      past.current.push(cur);
      if (past.current.length > 100) past.current.shift();
      future.current = [];
    }
    lastSnap.current = typing ? now : 0;
    commit({ ...cur, ...patch });
  }, []);

  const undo = React.useCallback(() => {
    const prev = past.current.pop();
    if (!prev) return;
    future.current.push(draftRef.current);
    lastSnap.current = 0;
    commit(prev);
  }, []);

  const redo = React.useCallback(() => {
    const next = future.current.pop();
    if (!next) return;
    past.current.push(draftRef.current);
    lastSnap.current = 0;
    commit(next);
  }, []);

  const toggleTheme = React.useCallback(() => {
    setTheme((t) => {
      const n = t === "dark" ? "light" : "dark";
      document.documentElement.classList.toggle("dark", n === "dark");
      document.querySelector('meta[name="theme-color"]')?.setAttribute("content", n === "dark" ? "#0d1219" : "#f6f7f9");
      safeSet("po-theme", n);
      return n;
    });
  }, []);

  const value: Store = {
    options, optionsError, draft, setDraft, undo, redo,
    canUndo: past.current.length > 0, canRedo: future.current.length > 0,
    result, setResult,
    imageDraft, setImageDraft: (p) => setImageDraftState((c) => ({ ...c, ...p })),
    imageResult, setImageResult,
    pendingRun, requestRun: () => setPendingRun((n) => n + 1), clearRun: () => setPendingRun(0),
    pendingImageRun, requestImageRun: () => setPendingImageRun((n) => n + 1), clearImageRun: () => setPendingImageRun(0),
    theme, toggleTheme, shortcutsOpen, setShortcutsOpen, tourOpen, setTourOpen,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useStore(): Store {
  const s = React.useContext(Ctx);
  if (!s) throw new Error("useStore outside StoreProvider");
  return s;
}

export { safeGet, safeSet };
