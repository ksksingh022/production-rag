const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;

function headers(json = true): HeadersInit {
  const h: Record<string, string> = {};
  if (json) h["Content-Type"] = "application/json";
  if (API_KEY) h["X-API-Key"] = API_KEY;
  return h;
}

export interface SourceChunk {
  chunk_id: string;
  text: string;
  score: number;
  source: string | null;
  dataset_name: string | null;
}

export interface QueryMetrics {
  cache_hit: boolean;
  retrieval_ms: number;
  rerank_ms: number;
  generation_ms: number;
  total_ms: number;
  candidates_retrieved: number;
  chunks_used: number;
  top_score: number | null;
  llm_prompt_tokens: number | null;
  llm_completion_tokens: number | null;
  estimated_cost_usd: number | null;
  provider: string;
  model: string;
  embedding_model: string;
}

export interface QueryResponse {
  query_id: string;
  answer: string;
  sources: SourceChunk[];
  metrics: QueryMetrics;
}

export interface QueryRequest {
  query: string;
  top_k?: number;
  filters?: Record<string, unknown>;
  rerank?: boolean;
  use_cache?: boolean;
  provider?: string;
  model?: string;
}

export interface StatsResponse {
  total_queries: number;
  queries_last_24h: number;
  cache_hit_rate: number;
  latency_ms: { p50: number; p95: number; p99: number };
  avg_chunks_used: number;
  error_rate: number;
  total_tokens: number;
  estimated_cost_usd_24h: number;
  top_queries: { query: string; count: number }[];
  feedback: { positive: number; negative: number };
}

export interface TimelinePoint {
  created_at: string;
  total_ms: number;
  cache_hit: boolean;
  tokens: number;
}

export interface HistoryItem {
  query_id: string;
  query_text: string;
  answer: string;
  sources: SourceChunk[];
  metrics: QueryMetrics;
  created_at: string;
  feedback: 1 | -1 | null;
}

export interface HistoryResponse {
  items: HistoryItem[];
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function handleJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    let detail = body;
    try {
      detail = JSON.parse(body).detail ?? body;
    } catch {
      /* not JSON, use raw text */
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

export async function postQuery(payload: QueryRequest): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/query`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(payload),
  });
  return handleJson<QueryResponse>(res);
}

export async function getStats(): Promise<StatsResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/stats`, { headers: headers(false) });
  return handleJson<StatsResponse>(res);
}

export async function getTimeline(limit = 200): Promise<{ points: TimelinePoint[] }> {
  const res = await fetch(`${API_BASE_URL}/api/v1/stats/timeline?limit=${limit}`, { headers: headers(false) });
  return handleJson<{ points: TimelinePoint[] }>(res);
}

export async function getHistory(limit = 30): Promise<HistoryResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/history?limit=${limit}`, { headers: headers(false) });
  return handleJson<HistoryResponse>(res);
}

export async function postFeedback(queryId: string, rating: 1 | -1, comment?: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/v1/feedback`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ query_id: queryId, rating, comment }),
  });
  await handleJson(res);
}

export interface StreamHandlers {
  onDelta: (text: string) => void;
  onDone: (payload: { query_id: string; sources: SourceChunk[]; metrics: QueryMetrics }) => void;
  onError: (message: string) => void;
}

/** Consumes the SSE stream from POST /api/v1/query/stream, feeding token deltas and
 * the final sources/query_id event back to the caller via callbacks. */
export async function streamQuery(payload: QueryRequest, handlers: StreamHandlers): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/v1/query/stream`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(payload),
  });

  if (!res.ok || !res.body) {
    const text = await res.text();
    handlers.onError(text || `Request failed with status ${res.status}`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const raw of events) {
      const line = raw.trim();
      if (!line.startsWith("data:")) continue;
      const jsonStr = line.slice("data:".length).trim();
      try {
        const event = JSON.parse(jsonStr);
        if (event.error) {
          handlers.onError(event.error);
        } else if (event.done) {
          handlers.onDone({ query_id: event.query_id, sources: event.sources, metrics: event.metrics });
        } else if (event.delta) {
          handlers.onDelta(event.delta);
        }
      } catch {
        // ignore malformed SSE chunk
      }
    }
  }
}
