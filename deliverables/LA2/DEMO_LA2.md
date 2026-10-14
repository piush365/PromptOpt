# LA-2 live demo plan (Thu 15 Oct 2026)

Laptop: the project laptop (RTX 3050, Fedora). The app runs as the systemd user service `promptopt`
(Stage A + B + C on CUDA, port 8080). Total demo time: about 6 minutes. Piush drives the laptop; Nirzara narrates
steps 1-3, Siddhi narrates steps 4-5.

## 1. Start commands

Normal start (service, Stage C on the GPU):

```bash
systemctl --user restart promptopt
systemctl --user status promptopt --no-pager      # "active (running)"
curl -s http://127.0.0.1:8080/api/options | head -c 300   # "stage_c": {"available": true, ...}
xdg-open http://127.0.0.1:8080/
```

Manual start (if the service will not start):

```bash
cd /mnt/SharedDrive/Projects/PromptOpt/backend
.venv-gpu/bin/uvicorn app.api:app --port 8080      # Stage C on GPU
```

Open the app on the laptop itself (127.0.0.1). `PROMPTOPT_PASSWORD` is set in `backend/.env`, so any other machine
on the LAN is asked for the password; this machine is not.

## 2. Demo prompts, in order

| # | Page | Input | Settings | What to point at |
|---|---|---|---|---|
| 1 | Optimize | Click the gallery example **"write code to get all permutations of a string"** | Target GPT, category Auto, no attachment | Stage A: Coding 1.00, issues A02 (no format) and A03 (no language). Stage B: B07, B05 "Use Python.", B03 "Return only the code, in a single code block" with before/after. Stage C: skipped. Rendering: 9 -> 35 input tokens, exact. Switch the tab to Claude and Gemini: same content, different layout. Validated tests below. |
| 2 | Optimize | `hey can you just summarize this article for me` | GPT, Auto | Stage A finds filler and an ambiguous reference ("this article"); B01 removes the filler, B04 adds "Keep it under 100 words", B03 "Use bullet points". The reference is still unresolved, so the prompt is **routed to Stage C**; Stage C's answer failed validation, so Stage B's result is kept and the page says so. Point out: honest fallback, the user sees why. |
| 3 | Compare | Click **Compare this** on prompt 1, then **Run comparison** | gpt-oss-120b on Groq | -67.7% total tokens (768 -> 248), output -79%, both answers 6/6 sandbox tests, "Who answered" label (stand-in for GPT). Past comparisons table: one case (+17.2%, hackpad) where the optimized prompt costs more: the answer was already one line. |
| 4 | Image mode | `oil painting of a sailboat in a storm` | target Stable Diffusion | The user's words come first and unchanged; missing attributes (lighting, palette, aspect ratio, ...) are clickable suggestions, not inserted. Click one suggestion to show it is added and marked. |
| 5 | History, Test suite, Results | - | - | History: the prompts just run, search, view one, (do not delete live). Test suite: 37/50 -> 42/50, open cqa-01 (gold 80300; vague answered 85300). Results: -39.2% headline with CI, per-category table. |

If time is left: Status page (providers' 24-hour usage, Stage C on CUDA, sandbox = bwrap).

## 3. Fallbacks

| Problem | What to do |
|---|---|
| **No network / Groq down / quota used** | Steps 1, 2, 4, 5 are fully offline. For Compare, switch the model to *gpt-oss-120b on Cerebras*; if both fail, do not run a new comparison: show the **Past comparisons** table on the Compare page and the Compare screenshot on slide 7 (live run from 14 Oct: 768 -> 248 tokens). The permutations prompt was compared before and may be answered from the local Compare cache: test this in the checklist with Wi-Fi off. |
| **GPU / CUDA fails** (Stage C pill says unavailable) | `systemctl --user stop promptopt`, then `cd backend && STAGE_C_DEVICE=cpu .venv-gpu/bin/uvicorn app.api:app --port 8080` (Stage C on CPU, about 5 s per routed prompt). If that also fails: `.venv/bin/uvicorn app.api:app --port 8080` (Stage A + B only; the app says Stage C is not installed, step 2 then shows Stage B's result). |
| **Port 8080 busy** | `--port 8081` and open that port. |
| **App will not start at all** | Present slides 7 and 14 (screenshots) and open `deliverables/LA2/MP1_Report_PromptOpt.pdf`, chapter 7e (all screens). |
| **Browser shows an old page** | Hard reload (Ctrl+Shift+R). |

## 4. Ten-minute pre-demo checklist

1. Laptop on charger, performance power mode, notifications off (Do Not Disturb), screen never sleeps.
2. `systemctl --user status promptopt` is active; restart it if it ran for days.
3. `nvidia-smi` shows the GPU and the uvicorn process using it.
4. Open http://127.0.0.1:8080/ ; the header pill reads "Stage C on · CUDA".
5. Run prompt 1 once (warms up Stage A; the first optimize after a restart is slower).
6. Run prompt 2 once (warms up Stage C).
7. Compare page: model list shows Groq available; run prompt 1 once to check the network and quota.
8. Wi-Fi test (optional, 1 minute): turn Wi-Fi off, re-run Compare for prompt 1, note whether it is served from the cache; turn Wi-Fi back on.
9. Zoom the browser to 110-125% so the panel can read it; close other tabs; open the deck on slide 18 in a second window.
10. Keep `deliverables/LA2/MP1_Report_PromptOpt.pdf` and this file open as backup; test the projector/HDMI mirror mode.

## 5. Numbers to have ready (sources: `evaluation/FINAL_RESULTS.md`, `evaluation/correctness_suite/RESULTS.md`)

- Total tokens -39.2% (95% CI 35.9-42.5%, n = 482); output 682 -> 165, input 226 -> 241; 87 of 482 prompts cost more.
- Output format stated 3.1% -> 95.0%; Stage A accuracy 74.7%; 6.4% routed to Stage C.
- Benchmark: quality 8.2 -> 9.0, task success 67% -> 85%, tokens -57%.
- Stage C: 5.0% vs 98.2% pass validation; median 0.74 s GPU.
- Correctness suite: 37/50 -> 42/50, -29.6% tokens, McNemar p = 0.267 (not significant), Cerebras 43 vs 41.
- Tests (run 14 Oct): pytest 798 passed; Playwright 13/13; freeze check byte-identical.
