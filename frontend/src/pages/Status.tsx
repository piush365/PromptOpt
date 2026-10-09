import * as React from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, Cpu, KeyRound, Moon, RefreshCw, Shield, Sun, XCircle } from "lucide-react";
import { api, type Status as S } from "@/lib/api";
import { useStore } from "@/lib/store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { InfoTip } from "@/components/ui/tooltip";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBox, PageHeader } from "@/components/Feedback";
import { Segmented } from "@/components/ui/segmented";
import { cn } from "@/lib/utils";

function Quota({ used, limit }: { used: number; limit: number }) {
  const share = Math.min(1, used / limit);
  const tone = share > 0.7 ? "bg-del" : share > 0.5 ? "bg-c" : "bg-b";
  return (
    <div>
      <div className="h-2 overflow-hidden rounded-full bg-sunken" role="meter" aria-valuemin={0} aria-valuemax={limit} aria-valuenow={used}
        aria-label="Tokens used in the last 24 hours">
        <div className={cn("h-full rounded-full", tone)} style={{ width: `${Math.max(1, share * 100)}%` }} />
      </div>
      <p className="mt-1 text-xs text-muted tabular">{used.toLocaleString("en-IN")} of {limit.toLocaleString("en-IN")} tokens in 24 h
        {share > 0.7 && " · near the app's 70% cap, use the other provider"}</p>
    </div>
  );
}

export default function Status() {
  const { theme, toggleTheme, setTourOpen } = useStore();
  const navigate = useNavigate();
  const [s, setS] = React.useState<S | null>(null);
  const [err, setErr] = React.useState<string | null>(null);
  const load = React.useCallback(() => { setErr(null); setS(null); api.status().then(setS).catch((e) => setErr(e.message)); }, []);
  React.useEffect(load, [load]);

  return (
    <div>
      <PageHeader title="Status & settings" lead="What this server can do right now, and how to turn on what's missing."
        actions={<Button onClick={load}><RefreshCw /> Refresh</Button>} />
      {err && <ErrorBox message={err} onRetry={load} />}
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <section className="rounded-2xl border border-rule bg-surface p-5 shadow-card sm:p-6" aria-labelledby="prov-h">
          <h2 id="prov-h" className="mb-1 flex items-center font-display text-xl font-semibold">Answering models
            <InfoTip>Used by Compare and the test suite's “Run live”. Keys live in backend/.env and are never sent to the browser.</InfoTip></h2>
          <p className="mb-4 text-sm text-muted">The optimizer itself needs no model or key: everything on Optimize runs on this computer.</p>
          {!s ? !err && <div className="space-y-3">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-[4.25rem]" />)}</div> : (
            <ul className="divide-y divide-rule" data-testid="providers">
              {s.providers.map((p) => (
                <li key={p.id} className="grid gap-2 py-3 sm:grid-cols-[1.5rem_1fr_minmax(0,14rem)] sm:items-center sm:gap-4">
                  {p.available ? <CheckCircle2 className="size-5 text-b" aria-label="available" /> : <XCircle className="size-5 text-muted" aria-label="unavailable" />}
                  <div className="min-w-0">
                    <p className="font-medium">{p.label} <Badge tone="outline" className="ml-1">{p.provider}</Badge></p>
                    <p className="text-sm text-muted">{p.available ? `Stands in for ${p.family === "gpt-oss" ? "GPT, Gemini and Claude" : p.family}.` : p.reason}</p>
                  </div>
                  <div>
                    {p.usage_24h?.limit_tokens ? <Quota used={p.usage_24h.tokens} limit={p.usage_24h.limit_tokens} />
                      : !p.available ? <p className="flex items-center gap-1.5 font-mono text-xs text-muted"><KeyRound className="size-3.5" aria-hidden />{p.key_env}</p>
                      : <p className="text-xs text-muted">The provider's own limit applies.</p>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="space-y-6">
          <section className="rounded-2xl border border-rule bg-surface p-5 shadow-card" aria-labelledby="c-h">
            <h2 id="c-h" className="mb-3 flex items-center gap-2 font-display text-xl font-semibold"><Cpu className="size-5 text-c" aria-hidden /> Stage C</h2>
            {!s ? <Skeleton className="h-44" /> : s.stage_c.available ? (
              <p className="text-[0.9375rem]"><Badge tone="c">on · {s.stage_c.device?.toUpperCase()}</Badge> <span className="ml-1 font-mono text-sm">{s.stage_c.model}</span><br />
                <span className="text-sm text-muted">{s.stage_c.device === "cuda" ? "About 0.7 s per routed prompt." : "On the CPU: about 5 s per routed prompt."}</span></p>
            ) : (
              <div className="text-[0.9375rem]"><Badge tone="outline">off</Badge>
                <p className="mt-2 text-sm text-ink-2">The small model isn't loaded. Prompts that need it show Stage B's result (and you're asked to pick the category when it's unclear). To turn it on, start the server from the GPU environment:</p>
                <pre className="proof mt-2 rounded-lg bg-sunken p-3 text-xs">cd backend{"\n"}source .venv-gpu/bin/activate{"\n"}uvicorn app.api:app</pre></div>
            )}
          </section>
          <section className="rounded-2xl border border-rule bg-surface p-5 shadow-card" aria-labelledby="t-h">
            <h2 id="t-h" className="mb-3 flex items-center gap-2 font-display text-xl font-semibold"><Shield className="size-5 text-muted" aria-hidden /> Code tests & privacy</h2>
            {!s ? <Skeleton className="h-28" /> : (
              <ul className="space-y-2 text-sm text-ink-2">
                <li>Sandbox: <b className="text-ink">{s.coding_tests.sandbox === "bwrap" ? "bubblewrap (no network, read-only system)" : "resource limits only (install bubblewrap for full isolation)"}</b></li>
                <li>Generating tests for new coding prompts: <b className="text-ink">{s.coding_tests.can_generate ? "available" : "needs CEREBRAS_API_KEY"}</b></li>
                <li>History is kept <b className="text-ink">{s.retention_days} days</b>; emails and phone numbers are removed before storing.</li>
              </ul>
            )}
          </section>
          <section className="rounded-2xl border border-rule bg-surface p-5 shadow-card" aria-labelledby="a-h">
            <h2 id="a-h" className="mb-3 font-display text-xl font-semibold">Appearance</h2>
            <Segmented<"light" | "dark"> label="Theme" value={theme} onChange={(v) => { if (v !== theme) toggleTheme(); }}
              options={[{ value: "light", label: <span className="flex items-center justify-center gap-1.5"><Sun className="size-4" />Light</span> },
                { value: "dark", label: <span className="flex items-center justify-center gap-1.5"><Moon className="size-4" />Dark</span> }]} />
            <Button variant="ghost" size="sm" className="mt-3" onClick={() => { navigate("/"); setTourOpen(true); }}>
              Show the welcome tour again
            </Button>
          </section>
        </div>
      </div>
    </div>
  );
}
