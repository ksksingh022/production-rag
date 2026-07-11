import { useState } from "react";
import type { SourceChunk } from "../lib/api";

export default function SourceCard({ source, highlight }: { source: SourceChunk; highlight?: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const preview = source.text.length > 160 ? source.text.slice(0, 160) + "…" : source.text;

  return (
    <div
      className={`source-card${highlight ? " source-card-highlight" : ""}`}
      onClick={() => setExpanded((v) => !v)}
    >
      <div className="source-card-header">
        <span className="source-chunk-id">{source.chunk_id}</span>
        <span className="source-score">{source.score.toFixed(3)}</span>
      </div>
      {highlight && <span className="source-single-badge">Sole source for this answer</span>}
      <p className="source-text">{expanded ? source.text : preview}</p>
      {(source.source || source.dataset_name) && (
        <div className="source-meta">
          {source.source && <span>{source.source}</span>}
          {source.dataset_name && <span>{source.dataset_name}</span>}
        </div>
      )}
    </div>
  );
}
