import { useEffect, useState, useCallback } from "react";
import { getHistory, ApiError, type HistoryItem } from "../lib/api";
import { useAsk } from "../context/AskContext";

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function Sidebar({ onSelect }: { onSelect?: () => void }) {
  const { loadFromHistory, queryId, historyVersion } = useAsk();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await getHistory(30);
      setItems(res.items);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, historyVersion]);

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <span className="sidebar-title">History</span>
        <span className="sidebar-count">{items.length}</span>
      </div>

      {error && <p className="sidebar-error">{error}</p>}
      {items.length === 0 && !error && <p className="sidebar-empty">Your questions will show up here.</p>}

      <ul className="history-list">
        {items.map((item) => (
          <li key={item.query_id}>
            <button
              className={`history-item${queryId === item.query_id ? " active" : ""}`}
              onClick={() => {
                loadFromHistory(item);
                onSelect?.();
              }}
            >
              <span className="history-item-text">{item.query_text}</span>
              <span className="history-item-meta">
                <span className="history-item-time">{timeAgo(item.created_at)}</span>
                {item.metrics.cache_hit && <span className="history-item-badge">cached</span>}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
