import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

/* Chart kit: thin bars, 4px rounded ends, recessive grid, text in ink tokens, legend for every multi-series
   chart, values as direct labels, and a hover tooltip per bar. Colours come from the --viz-* tokens. */

const axis = { fontSize: 12, fill: "var(--muted)", fontFamily: "var(--font-mono)" };

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-2" aria-label="Legend">
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-1.5">
          <span aria-hidden className="size-2.5 rounded-sm" style={{ background: i.color }} />{i.label}
        </li>
      ))}
    </ul>
  );
}

function TipBox({ active, payload, label, unit = "" }: {
  active?: boolean; label?: string; unit?: string;
  payload?: { name: string; value: number; color: string; dataKey: string }[];
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-rule bg-surface px-3 py-2 text-sm shadow-card">
      <p className="mb-1 font-medium text-ink">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} className="flex items-center gap-2 text-ink-2">
          <span aria-hidden className="size-2 rounded-sm" style={{ background: p.color }} />
          {p.name}: <span className="tabular font-mono text-ink">{p.value.toLocaleString("en-IN")}{unit}</span>
        </p>
      ))}
    </div>
  );
}

/** Two bars per row (e.g. vague vs optimized), horizontal so long category names stay readable. */
export function PairBars({ data, a, b, unit = "", height, domain }: {
  data: { name: string; a: number; b: number }[];
  a: { label: string; color: string }; b: { label: string; color: string };
  unit?: string; height?: number; domain?: [number, number];
}) {
  return (
    <div className="space-y-2">
      <Legend items={[a, b]} />
      <div style={{ height: height ?? Math.max(140, data.length * 56 + 30) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 48, bottom: 4, left: 4 }} barGap={2} barCategoryGap="22%">
            <CartesianGrid horizontal={false} stroke="var(--rule)" />
            <XAxis type="number" tick={axis} axisLine={false} tickLine={false} domain={domain ?? [0, "auto"]} unit={unit} />
            <YAxis type="category" dataKey="name" tick={{ ...axis, fill: "var(--ink-2)", fontFamily: "var(--font-sans)", fontSize: 13 }} width={112} axisLine={false} tickLine={false} />
            <Tooltip content={<TipBox unit={unit} />} cursor={{ fill: "var(--sunken)" }} />
            <Bar dataKey="a" name={a.label} fill={a.color} radius={[0, 4, 4, 0]} maxBarSize={14} isAnimationActive={false}>
              <LabelList dataKey="a" position="right" formatter={(v: unknown) => `${v}${unit}`} style={{ fontSize: 11, fill: "var(--ink-2)", fontFamily: "var(--font-mono)" }} />
            </Bar>
            <Bar dataKey="b" name={b.label} fill={b.color} radius={[0, 4, 4, 0]} maxBarSize={14} isAnimationActive={false}>
              <LabelList dataKey="b" position="right" formatter={(v: unknown) => `${v}${unit}`} style={{ fontSize: 11, fill: "var(--ink)", fontFamily: "var(--font-mono)", fontWeight: 600 }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/** One series, horizontal. */
export function SingleBars({ data, color = "var(--viz-opt)", unit = "", domain, label }: {
  data: { name: string; value: number }[]; color?: string; unit?: string; domain?: [number, number]; label: string;
}) {
  return (
    <div style={{ height: Math.max(120, data.length * 36 + 30) }} role="img" aria-label={label}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 48, bottom: 4, left: 4 }} barCategoryGap="28%">
          <CartesianGrid horizontal={false} stroke="var(--rule)" />
          <XAxis type="number" tick={axis} axisLine={false} tickLine={false} domain={domain ?? [0, "auto"]} unit={unit} />
          <YAxis type="category" dataKey="name" tick={{ ...axis, fill: "var(--ink-2)", fontFamily: "var(--font-sans)", fontSize: 13 }} width={112} axisLine={false} tickLine={false} />
          <Tooltip content={<TipBox unit={unit} />} cursor={{ fill: "var(--sunken)" }} />
          <Bar dataKey="value" name={label} fill={color} radius={[0, 4, 4, 0]} maxBarSize={16} isAnimationActive={false}>
            <LabelList dataKey="value" position="right" formatter={(v: unknown) => `${v}${unit}`} style={{ fontSize: 11, fill: "var(--ink)", fontFamily: "var(--font-mono)" }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Stacked token bars: input / visible output / reasoning, one row per prompt. */
export function TokenStack({ rows }: { rows: { name: string; input: number; output: number; reasoning: number }[] }) {
  const series = [
    { key: "input", label: "Input", color: "var(--viz-in)" },
    { key: "output", label: "Output (visible)", color: "var(--viz-out)" },
    { key: "reasoning", label: "Reasoning (hidden)", color: "var(--viz-reason)" },
  ];
  return (
    <div className="space-y-2">
      <Legend items={series} />
      <div style={{ height: rows.length * 52 + 40 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 4 }} barCategoryGap="30%">
            <CartesianGrid horizontal={false} stroke="var(--rule)" />
            <XAxis type="number" tick={axis} axisLine={false} tickLine={false} />
            <YAxis type="category" dataKey="name" tick={{ ...axis, fill: "var(--ink-2)", fontFamily: "var(--font-sans)", fontSize: 13 }} width={96} axisLine={false} tickLine={false} />
            <Tooltip content={<TipBox unit=" tokens" />} cursor={{ fill: "var(--sunken)" }} />
            {series.map((s, i) => (
              <Bar key={s.key} dataKey={s.key} name={s.label} stackId="t" fill={s.color} stroke="var(--surface)" strokeWidth={2}
                radius={i === series.length - 1 ? [0, 4, 4, 0] : 0} maxBarSize={22} isAnimationActive={false} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
