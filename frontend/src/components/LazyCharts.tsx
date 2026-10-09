import * as React from "react";
import { Skeleton } from "@/components/ui/skeleton";

/* Recharts is large; pages render their text first and the charts arrive a moment later. */
const load = () => import("@/components/Charts");
const PairBarsL = React.lazy(() => load().then((m) => ({ default: m.PairBars })));
const SingleBarsL = React.lazy(() => load().then((m) => ({ default: m.SingleBars })));
const TokenStackL = React.lazy(() => load().then((m) => ({ default: m.TokenStack })));

const fallback = (h: number) => <Skeleton className="w-full" style={{ height: h }} />;

export function PairBars(p: React.ComponentProps<typeof PairBarsL>) {
  return <React.Suspense fallback={fallback(p.height ?? 220)}><PairBarsL {...p} /></React.Suspense>;
}
export function SingleBars(p: React.ComponentProps<typeof SingleBarsL>) {
  return <React.Suspense fallback={fallback(180)}><SingleBarsL {...p} /></React.Suspense>;
}
export function TokenStack(p: React.ComponentProps<typeof TokenStackL>) {
  return <React.Suspense fallback={fallback(150)}><TokenStackL {...p} /></React.Suspense>;
}
