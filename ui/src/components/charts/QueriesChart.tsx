import { useMemo, useState } from "react";
import type { TimelinePoint } from "../../lib/api";
import { useContainerWidth } from "../../lib/useContainerWidth";
import { bucketByTime, cleanTicks, formatCount } from "./chartUtils";

const H = 210;
const PAD = { top: 18, right: 12, bottom: 26, left: 34 };
const BAR_MAX = 24; // mark spec: columns never thicker than 24px
const SEG_GAP = 2; // surface gap between stacked segments

/** Stacked column chart: fresh generations vs cache-served answers per time bucket.
 * Two series -> categorical slots 1 (blue) and 2 (aqua), fixed order, with legend. */
export default function QueriesChart({ points }: { points: TimelinePoint[] }) {
  const [wrapRef, width] = useContainerWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const buckets = useMemo(() => bucketByTime(points), [points]);

  if (points.length === 0) return <p className="muted">No queries yet.</p>;

  const plotW = Math.max(width - PAD.left - PAD.right, 40);
  const plotH = H - PAD.top - PAD.bottom;
  const maxTotal = Math.max(...buckets.map((b) => b.fresh + b.cached), 1);
  const ticks = cleanTicks(maxTotal);
  const yMax = ticks[ticks.length - 1];
  const y = (v: number) => PAD.top + plotH - (v / yMax) * plotH;

  const band = plotW / buckets.length;
  const barW = Math.min(BAR_MAX, band * 0.6);
  const peakIdx = buckets.reduce(
    (best, b, i) => (b.fresh + b.cached > buckets[best].fresh + buckets[best].cached ? i : best),
    0
  );

  const hovered = hover != null ? buckets[hover] : null;
  const hoveredX = hover != null ? PAD.left + hover * band + band / 2 : 0;

  return (
    <div>
      <div className="chart-legend">
        <span className="legend-item"><span className="legend-swatch swatch-series-1" />Generated</span>
        <span className="legend-item"><span className="legend-swatch swatch-series-2" />From cache</span>
      </div>

      <div className="chart-plot" ref={wrapRef}>
        {width > 0 && (
          <svg width={width} height={H} role="img" aria-label="Queries over time, generated vs cached">
            {ticks.map((t) => (
              <g key={t}>
                <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)}
                  stroke="var(--viz-grid)" strokeWidth={1} />
                <text x={PAD.left - 6} y={y(t) + 3.5} textAnchor="end" className="chart-tick">
                  {formatCount(t)}
                </text>
              </g>
            ))}

            {buckets.map((b, i) => {
              const cx = PAD.left + i * band + band / 2;
              const x = cx - barW / 2;
              const total = b.fresh + b.cached;
              const freshTop = y(b.fresh);
              const cachedH = b.cached > 0 ? y(0) - y(b.cached) : 0;
              const cachedTop = freshTop - SEG_GAP - cachedH;
              const r = 4; // rounded data-end; baseline stays square
              return (
                <g key={i} opacity={hover === null || hover === i ? 1 : 0.45}>
                  {b.fresh > 0 && (
                    <path
                      d={
                        b.cached > 0
                          ? `M${x},${y(0)} L${x},${freshTop} H${x + barW} L${x + barW},${y(0)} Z`
                          : `M${x},${y(0)} L${x},${freshTop + r} Q${x},${freshTop} ${x + r},${freshTop} H${x + barW - r} Q${x + barW},${freshTop} ${x + barW},${freshTop + r} L${x + barW},${y(0)} Z`
                      }
                      style={{ fill: "var(--series-1)" }}
                    />
                  )}
                  {b.cached > 0 && (
                    <path
                      d={`M${x},${cachedTop + cachedH} L${x},${cachedTop + r} Q${x},${cachedTop} ${x + r},${cachedTop} H${x + barW - r} Q${x + barW},${cachedTop} ${x + barW},${cachedTop + r} L${x + barW},${cachedTop + cachedH} Z`}
                      style={{ fill: "var(--series-2)" }}
                    />
                  )}
                  {i === peakIdx && total > 0 && (
                    <text x={cx} y={(b.cached > 0 ? cachedTop : freshTop) - 5} textAnchor="middle" className="chart-value-label">
                      {total}
                    </text>
                  )}
                  <rect
                    x={PAD.left + i * band} y={PAD.top} width={band} height={plotH + PAD.bottom}
                    fill="transparent"
                    onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}
                  />
                </g>
              );
            })}

            <line x1={PAD.left} x2={width - PAD.right} y1={y(0)} y2={y(0)} stroke="var(--viz-axis)" strokeWidth={1} />

            {buckets.map((b, i) =>
              i === 0 || i === buckets.length - 1 || (buckets.length > 8 && i === Math.floor(buckets.length / 2)) ? (
                <text key={`x${i}`} x={PAD.left + i * band + band / 2} y={H - 8} textAnchor="middle" className="chart-tick">
                  {b.label}
                </text>
              ) : null
            )}
          </svg>
        )}

        {hovered && (
          <div
            className="chart-tooltip"
            style={{ left: Math.min(Math.max(hoveredX, 70), width - 70), top: 6 }}
          >
            <span className="tooltip-title">{hovered.label}</span>
            <span><span className="legend-swatch swatch-series-1" />Generated · {hovered.fresh}</span>
            <span><span className="legend-swatch swatch-series-2" />From cache · {hovered.cached}</span>
          </div>
        )}
      </div>
    </div>
  );
}
