import type { QueryMetrics } from "../lib/api";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

export default function MetricsStrip({ metrics }: { metrics: QueryMetrics }) {
  const cost =
    metrics.estimated_cost_usd != null
      ? metrics.estimated_cost_usd === 0
        ? "free"
        : `$${metrics.estimated_cost_usd.toFixed(4)}`
      : "—";

  return (
    <div className="metrics-strip">
      <span className={`badge ${metrics.cache_hit ? "badge-hit" : "badge-miss"}`}>
        {metrics.cache_hit ? "cache hit" : "cache miss"}
      </span>
      <Stat label="total" value={`${metrics.total_ms.toFixed(0)} ms`} />
      <Stat label="retrieval" value={`${metrics.retrieval_ms.toFixed(0)} ms`} />
      <Stat label="rerank" value={`${metrics.rerank_ms.toFixed(0)} ms`} />
      <Stat label="generation" value={`${metrics.generation_ms.toFixed(0)} ms`} />
      <Stat label="chunks used" value={`${metrics.chunks_used}/${metrics.candidates_retrieved}`} />
      <Stat label="top score" value={metrics.top_score != null ? metrics.top_score.toFixed(3) : "—"} />
      <Stat
        label="tokens"
        value={
          metrics.llm_prompt_tokens != null
            ? `${metrics.llm_prompt_tokens}+${metrics.llm_completion_tokens}`
            : "—"
        }
      />
      <Stat label="cost" value={cost} />
      <Stat label="model" value={metrics.model} />
    </div>
  );
}
