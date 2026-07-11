import type { TimelinePoint } from "../../lib/api";

/** Rounds a raw maximum up to a clean axis ceiling (1/2/2.5/5 × 10^n). */
export function niceCeil(raw: number): number {
  if (raw <= 0) return 1;
  const pow = Math.pow(10, Math.floor(Math.log10(raw)));
  const unit = raw / pow;
  const nice = unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 2.5 ? 2.5 : unit <= 5 ? 5 : 10;
  return nice * pow;
}

/** Evenly spaced clean ticks from 0 to a nice ceiling (inclusive). */
export function cleanTicks(rawMax: number, count = 4): number[] {
  const ceil = niceCeil(rawMax);
  return Array.from({ length: count + 1 }, (_, i) => (ceil / count) * i);
}

export function formatMs(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`;
}

export function formatCount(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}K` : String(n);
}

export interface TimeBucket {
  start: Date;
  label: string;
  fresh: number;
  cached: number;
}

/** Groups timeline points into fixed-width time buckets, sized to the data's span
 * so the chart stays readable whether the log covers an hour or a month. */
export function bucketByTime(points: TimelinePoint[]): TimeBucket[] {
  if (points.length === 0) return [];

  const times = points.map((p) => new Date(p.created_at).getTime());
  const min = Math.min(...times);
  const max = Math.max(...times);
  const spanMs = max - min;

  const HOUR = 3600_000;
  const bucketMs = spanMs <= 3 * HOUR ? HOUR / 4 : spanMs <= 48 * HOUR ? HOUR : 24 * HOUR;

  const startEdge = Math.floor(min / bucketMs) * bucketMs;
  const bucketCount = Math.floor((max - startEdge) / bucketMs) + 1;

  const buckets: TimeBucket[] = Array.from({ length: bucketCount }, (_, i) => {
    const start = new Date(startEdge + i * bucketMs);
    const label =
      bucketMs >= 24 * HOUR
        ? start.toLocaleDateString(undefined, { month: "short", day: "numeric" })
        : start.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
    return { start, label, fresh: 0, cached: 0 };
  });

  for (const p of points) {
    const idx = Math.floor((new Date(p.created_at).getTime() - startEdge) / bucketMs);
    const bucket = buckets[idx];
    if (!bucket) continue;
    if (p.cache_hit) bucket.cached += 1;
    else bucket.fresh += 1;
  }

  return buckets;
}
