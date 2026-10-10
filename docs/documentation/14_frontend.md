# 14. Frontend (UI v2)

[Back to the index](README.md)

The web UI is a React + TypeScript single-page app in `frontend/`, built into `backend/app/static/ui/` (committed, so
running the app needs no Node). The first plain HTML/JS UI is still served at `/classic`.

---

## 14.1 Stack

React 19 · TypeScript 5.8 (strict, no unused locals/parameters) · Vite 6 · Tailwind CSS 4 · Radix UI primitives
(dialog, popover, select, tabs, toggle group, tooltip) · Recharts (charts) · framer-motion · lucide-react icons ·
sonner (toasts) · react-router 7 · fonts IBM Plex Sans/Mono and Bricolage Grotesque (self-hosted via fontsource).
Exact versions: `frontend/package.json` and `package-lock.json`.

## 14.2 Pages

| path | page | what it does |
|---|---|---|
| `/` | **Optimize** | prompt composer (prompt, pasted text, target, category auto/5, attachment type and name), example gallery, live token counter per target; results as a pipeline: Stage A card (category scores with the 0.6 gate drawn on the bars, issues; hovering an issue highlights its words in the prompt), Stage B card (each rule with a word-level before/after diff), Stage C card (routed?, reasons, validation checks passed/failed, raw output; "confirm category" with Stage C's guess pre-selected), renderings per target with input tokens and a copy button, coding tests panel, "Compare this" |
| `/compare` | **Compare** | choose a model and the optional blind judge; both answers side by side with input/output/total tokens and latency, total-token change, a stacked token chart (input, output, hidden reasoning), sandbox test badges, judge scores, an honest "who answered" label; past comparisons |
| `/suite` | **Test suite** | the 50 correctness cases with filters (category, status fixed/hurt/both/neither per model), a case view (material, both prompts, both answers, gold, verdicts, tokens) and a live re-run |
| `/results` | **Results** | `FINAL_RESULTS.md` parsed into sections, charts (tokens per category, Stage A, format stated, per-rule F1, benchmark, Stage C ablation, coding, correctness suite) and the token headline |
| `/how` | **How it works** | the pipeline in plain English and a glossary |
| `/history` | **History** | past prompts with search and paging, reopen in the composer, view details, export as Markdown, delete (with confirmation); retention notice |
| `/image` | **Image mode** | the image optimizer: target (DALL-E, Nano Banana, Stable Diffusion), stated attributes, clickable suggestion chips, renderings and negative prompt |
| `/status` | **Status & settings** | providers (key present, 24-hour usage vs limit), Stage C (model, device), sandbox kind, test generation, retention |
| `*` | Not found | |

## 14.3 Structure

| file | role |
|---|---|
| `src/lib/api.ts` | typed client for every endpoint; every error becomes an `ApiError` with a message saying what to do (e.g. 429 on Groq → "switch the model to gpt-oss-120b on Cerebras"; network error → "start it with `uvicorn app.api:app`") |
| `src/lib/store.tsx` | app state: options from the server, the current draft (prompt, context, target, category, attachment) with **undo/redo**, image draft, last results, theme (light/dark, remembered), tour and shortcut dialogs |
| `src/lib/diff.ts` | word-level diff for before/after views |
| `src/lib/labels.ts` | display names for categories, targets, attachments, rules; number/percent formatting |
| `src/components/Composer.tsx`, `Pipeline.tsx`, `Diff.tsx`, `ExampleGallery.tsx`, `Charts.tsx` (lazy), `Layout.tsx`, `Tour.tsx`, `Shortcuts.tsx`, `Feedback.tsx` | composer, pipeline cards, diff, examples, charts, navigation, first-visit tour, keyboard shortcuts, empty/error/copy helpers |
| `src/components/ui/*` | small design-system components (button, badge, dialog, select, segmented control, tabs, tooltip, skeleton, kbd) |

**Keyboard shortcuts:** Ctrl/⌘ + Enter optimize; Ctrl/⌘ + Z / Shift + Z undo/redo the input; `?` shortcuts; `D`
theme; Alt + 1…8 go to page; Esc closes dialogs; focus is always visible.

## 14.4 Build and performance

`npm run build` = `tsc -b` (type check) + `vite build` into `../backend/app/static/ui` with base `/static/ui/`. A small
Vite plugin (`vite.config.ts`, `inlineCss`) inlines the single stylesheet into `index.html` (one round trip less before
first paint), sets the body font to `font-display: optional` (no layout shift when a font arrives late), preloads the
body font, and adds a tiny script that **modulepreloads the chunk of the page being opened**. Every page except
Optimize is lazy-loaded; React, React DOM and the router are a separate chunk. Dev server: `npm run dev`, proxying
`/api` to `http://127.0.0.1:8765`.

## 14.5 Testing the UI

| tool | what it checks |
|---|---|
| `npm run e2e` (Playwright, system Chrome, `e2e/app.spec.ts`) | against the real FastAPI app on a throwaway SQLite database (`frontend/.e2e/`): example gallery → optimize shows every stage; hovering an issue highlights words; Ctrl+Enter, undo, live counter; an unsure category asks the user; Compare on a real model (skipped when no API key
is configured); test suite summary, filter and case view; history listed, searchable, viewable, deletable; theme toggle persists; image mode suggestions and renderings; gallery image example; tour and shortcuts; **every page loads without console errors** |
| `node scripts/api-parity.mjs` | runs the demo prompts through the new UI, captures every `/api/optimize` request/response and replays them against a reference server (e.g. the `main` branch); the JSON must be identical (prompt id aside) — proves the new UI changed nothing in the pipeline's answers |
| `node scripts/screenshots.mjs <dir>` | screenshots of every page at 1440 px and 390 px, light and dark |
| `node scripts/overflow.mjs` | reports horizontal overflow at phone width (390 px) for every page |
| `./scripts/lighthouse.sh` | Lighthouse mobile scores (performance, accessibility, best practices) and LCP/TBT for every page |

Type checking passed in this review (`npx tsc -b`, no errors).
