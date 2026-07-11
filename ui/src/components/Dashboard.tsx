import { useEffect, useState, useCallback } from "react";
import { getStats, getTimeline, ApiError, type StatsResponse, type TimelinePoint } from "../lib/api";
import QueriesChart from "./charts/QueriesChart";
import LatencyChart from "./charts/LatencyChart";

function StatTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="stat-tile">
      <span className="stat-tile-label">{label}</span>
      <span className="stat-tile-value">{value}</span>
      {sub && <span className="stat-tile-sub">{sub}</span>}
    </div>
  );
}

function LatencyBars({ latency }: { latency: StatsResponse["latency_ms"] }) {
  const max = Math.max(latency.p50, latency.p95, latency.p99, 1);
  const rows: [string, number, string][] = [
    ["p50", latency.p50, "var(--seq-1)"],
    ["p95", latency.p95, "var(--seq-2)"],
    ["p99", latency.p99, "var(--seq-3)"],
  ];
  return (
    <div className="latency-bars">
      {rows.map(([label, value, color]) => (
        <div key={label} className="latency-row">
          <span className="latency-label">{label}</span>
          <div className="latency-track">
            <div className="latency-fill" style={{ width: `${(value / max) * 100}%`, background: color }} />
          </div>
          <span className="latency-value">{(value / 1000).toFixed(1)}s</span>
        </div>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [statsData, timelineData] = await Promise.all([getStats(), getTimeline()]);
      setStats(statsData);
      setTimeline(timelineData.points);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, [load]);

  if (error) return <div className="error-banner">{error}</div>;
  if (!stats) return <div className="loading">Loading stats…</div>;

  const feedbackTotal = stats.feedback.positive + stats.feedback.negative;
  const positivePct = feedbackTotal ? Math.round((stats.feedback.positive / feedbackTotal) * 100) : null;

  return (
    <div className="dashboard">
      <div className="dash-grid">
        <StatTile label="Total queries" value={stats.total_queries.toLocaleString()} />
        <StatTile label="Last 24h" value={stats.queries_last_24h.toLocaleString()} />
        <StatTile label="Cache hit rate" value={`${(stats.cache_hit_rate * 100).toFixed(0)}%`} />
        <StatTile label="Error rate" value={`${(stats.error_rate * 100).toFixed(1)}%`} />
        <StatTile label="Avg chunks used" value={stats.avg_chunks_used.toFixed(1)} />
        <StatTile label="Total tokens" value={stats.total_tokens.toLocaleString()} />
        <StatTile
          label="Est. cost (24h)"
          value={stats.estimated_cost_usd_24h === 0 ? "$0" : `$${stats.estimated_cost_usd_24h.toFixed(4)}`}
        />
        <StatTile
          label="Feedback"
          value={positivePct != null ? `${positivePct}%` : "—"}
          sub={feedbackTotal ? `${stats.feedback.positive} positive · ${stats.feedback.negative} negative` : "no votes yet"}
        />
      </div>

      <div className="dash-charts">
        <div className="dash-panel">
          <h3>Queries over time</h3>
          <QueriesChart points={timeline} />
        </div>
        <div className="dash-panel">
          <h3>Latency per query</h3>
          <LatencyChart points={timeline} />
        </div>
      </div>

      <div className="dash-charts">
        <div className="dash-panel">
          <h3>Latency percentiles</h3>
          <LatencyBars latency={stats.latency_ms} />
        </div>
        <div className="dash-panel">
          <h3>Top queries</h3>
          {stats.top_queries.length === 0 ? (
            <p className="muted">No queries yet.</p>
          ) : (
            <ol className="top-queries">
              {stats.top_queries.map((q) => (
                <li key={q.query}>
                  <span className="top-query-text">{q.query}</span>
                  <span className="top-query-count">{q.count}</span>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </div>
  );
}
