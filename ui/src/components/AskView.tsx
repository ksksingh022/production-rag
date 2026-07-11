import { useAsk } from "../context/AskContext";
import MetricsStrip from "./MetricsStrip";
import SourceCard from "./SourceCard";

export default function AskView() {
  const {
    query,
    setQuery,
    answer,
    sources,
    metrics,
    queryId,
    status,
    error,
    feedbackSent,
    useStreaming,
    setUseStreaming,
    ask,
    sendFeedback,
  } = useAsk();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    ask(query);
  }

  return (
    <div className="ask-view">
      <form onSubmit={handleSubmit} className="query-form">
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask a question about the ingested corpus…"
          rows={3}
          maxLength={1000}
        />
        <div className="query-form-actions">
          <label className="toggle">
            <input
              type="checkbox"
              checked={useStreaming}
              onChange={(e) => setUseStreaming(e.target.checked)}
            />
            Stream response
          </label>
          <button type="submit" disabled={status === "streaming" || !query.trim()}>
            {status === "streaming" ? "Asking…" : "Ask"}
          </button>
        </div>
      </form>

      {error && <div className="error-banner">{error}</div>}

      {(answer || status === "streaming") && (
        <div className="answer-block">
          <p className="answer-text">
            {answer}
            {status === "streaming" && <span className="cursor-blink">▍</span>}
          </p>

          {status === "done" && queryId && (
            <div className="feedback-row">
              <button
                className={`feedback-btn ${feedbackSent === 1 ? "active" : ""}`}
                onClick={() => sendFeedback(1)}
                disabled={!!feedbackSent}
              >
                👍
              </button>
              <button
                className={`feedback-btn ${feedbackSent === -1 ? "active" : ""}`}
                onClick={() => sendFeedback(-1)}
                disabled={!!feedbackSent}
              >
                👎
              </button>
              {feedbackSent && <span className="feedback-thanks">thanks for the feedback</span>}
            </div>
          )}
        </div>
      )}

      {metrics && <MetricsStrip metrics={metrics} />}

      {sources.length > 0 && (
        <div className="sources-block">
          <h3>Sources</h3>
          <div className="source-grid">
            {sources.map((s) => (
              <SourceCard key={s.chunk_id} source={s} highlight={sources.length === 1} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
