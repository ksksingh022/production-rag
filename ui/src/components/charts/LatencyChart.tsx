import { useMemo, useState } from "react";
import type { TimelinePoint } from "../../lib/api";
import { useContainerWidth } from "../../lib/useContainerWidth";
import { cleanTicks, formatMs } from "./chartUtils";

const H = 210;
const PAD = { top: 18, right: 16, bottom: 26, left: 44 };

/** Single-series line of per-query end-to-end latency (2px line, 10% area wash,
 * crosshair + tooltip on hover). One series -> no legend box; the title names it. */
export default function LatencyChart({ points }: { points: TimelinePoint[] }) {
  const [wrapRef, width] = useContainerWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);

  const data = useMemo(() => points.slice(-60), [points]);

  if (data.length === 0) return <p className="muted">No queries yet.</p>;

  const plotW = Math.max(width - PAD.left - PAD.right, 40);
  const plotH = H - PAD.top - PAD.bottom;
  const ticks = cleanTicks(Math.max(...data.map((p) => p.total_ms)));
  const yMax = ticks[ticks.length - 1];
  // one unit for the whole axis -- never "0ms" below "12.5s"
  const tickLabel = (t: number) => (yMax >= 1000 ? `${(t / 1000).toFixed(1)}s` : `${Math.round(t)}ms`);

  const x = (i: number) => PAD.left + (data.length === 1 ? plotW / 2 : (i / (data.length - 1)) * plotW);
  const y = (v: number) => PAD.top + plotH - (v / yMax) * plotH;

  const linePath = data.map((p, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(p.total_ms)}`).join(" ");
  const areaPath = `${linePath} L${x(data.length - 1)},${y(0)} L${x(0)},${y(0)} Z`;

  const timeLabel = (p: TimelinePoint) =>
    new Date(p.created_at).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });

  function onMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const idx = Math.round(((px - PAD.left) / plotW) * (data.length - 1));
    setHover(Math.max(0, Math.min(data.length - 1, idx)));
  }

  const hovered = hover != null ? data[hover] : null;
  const endIdx = data.length - 1;

  return (
    <div className="chart-plot" ref={wrapRef}>
      {width > 0 && (
        <svg
          width={width} height={H} role="img" aria-label="Latency per query"
          onMouseMove={onMove} onMouseLeave={() => setHover(null)}
        >
          {ticks.map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} stroke="var(--viz-grid)" strokeWidth={1} />
              <text x={PAD.left - 6} y={y(t) + 3.5} textAnchor="end" className="chart-tick">{tickLabel(t)}</text>
            </g>
          ))}

          <path d={areaPath} style={{ fill: "var(--series-1)" }} fillOpacity={0.1} />
          <path d={linePath} style={{ stroke: "var(--series-1)" }} strokeWidth={2} fill="none"
            strokeLinecap="round" strokeLinejoin="round" />

          {hover != null && (
            <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={y(0)} stroke="var(--viz-axis)" strokeWidth={1} />
          )}

          {/* end marker always; hovered marker on demand -- both with a 2px surface ring */}
          {[endIdx, ...(hover != null && hover !== endIdx ? [hover] : [])].map((i) => (
            <circle key={i} cx={x(i)} cy={y(data[i].total_ms)} r={4}
              style={{ fill: "var(--series-1)", stroke: "var(--viz-surface)" }} strokeWidth={2} />
          ))}

          <line x1={PAD.left} x2={width - PAD.right} y1={y(0)} y2={y(0)} stroke="var(--viz-axis)" strokeWidth={1} />

          <text x={x(0)} y={H - 8} textAnchor="start" className="chart-tick">{timeLabel(data[0])}</text>
          {data.length > 1 && (
            <text x={x(endIdx)} y={H - 8} textAnchor="end" className="chart-tick">{timeLabel(data[endIdx])}</text>
          )}
        </svg>
      )}

      {hovered && hover != null && (
        <div className="chart-tooltip" style={{ left: Math.min(Math.max(x(hover), 80), width - 80), top: 6 }}>
          <span className="tooltip-title">{timeLabel(hovered)}</span>
          <span>{formatMs(hovered.total_ms)}{hovered.cache_hit ? " · cached" : ""}</span>
        </div>
      )}
    </div>
  );
}
