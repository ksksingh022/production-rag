import { createContext, useContext, useState, useRef, useCallback, type ReactNode } from "react";
import {
  postQuery,
  postFeedback,
  streamQuery,
  ApiError,
  type SourceChunk,
  type QueryMetrics,
  type HistoryItem,
} from "../lib/api";

type Status = "idle" | "streaming" | "done" | "error";

interface AskState {
  query: string;
  setQuery: (q: string) => void;
  answer: string;
  sources: SourceChunk[];
  metrics: QueryMetrics | null;
  queryId: string | null;
  status: Status;
  error: string | null;
  feedbackSent: 1 | -1 | null;
  useStreaming: boolean;
  setUseStreaming: (v: boolean) => void;
  ask: (query: string) => Promise<void>;
  loadFromHistory: (item: HistoryItem) => void;
  sendFeedback: (rating: 1 | -1) => Promise<void>;
  /** Bumped after every completed query so the history sidebar knows to refetch. */
  historyVersion: number;
}

const AskContext = createContext<AskState | null>(null);

export function AskProvider({ children }: { children: ReactNode }) {
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<SourceChunk[]>([]);
  const [metrics, setMetrics] = useState<QueryMetrics | null>(null);
  const [queryId, setQueryId] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [feedbackSent, setFeedbackSent] = useState<1 | -1 | null>(null);
  const [useStreaming, setUseStreaming] = useState(true);
  const [historyVersion, setHistoryVersion] = useState(0);
  const submitting = useRef(false);

  const ask = useCallback(
    async (q: string) => {
      if (!q.trim() || submitting.current) return;
      submitting.current = true;

      setQuery(q);
      setAnswer("");
      setSources([]);
      setMetrics(null);
      setQueryId(null);
      setFeedbackSent(null);
      setError(null);
      setStatus("streaming");

      if (useStreaming) {
        await streamQuery(
          { query: q },
          {
            onDelta: (delta) => setAnswer((prev) => prev + delta),
            onDone: ({ query_id, sources, metrics }) => {
              setQueryId(query_id);
              setSources(sources);
              setMetrics(metrics);
              setStatus("done");
              setHistoryVersion((v) => v + 1);
            },
            onError: (message) => {
              setError(message);
              setStatus("error");
            },
          }
        );
      } else {
        try {
          const res = await postQuery({ query: q });
          setAnswer(res.answer);
          setSources(res.sources);
          setMetrics(res.metrics);
          setQueryId(res.query_id);
          setStatus("done");
          setHistoryVersion((v) => v + 1);
        } catch (err) {
          setError(err instanceof ApiError ? err.message : String(err));
          setStatus("error");
        }
      }
      submitting.current = false;
    },
    [useStreaming]
  );

  const loadFromHistory = useCallback((item: HistoryItem) => {
    setQuery(item.query_text);
    setAnswer(item.answer);
    setSources(item.sources);
    setMetrics(item.metrics);
    setQueryId(item.query_id);
    setStatus("done");
    setError(null);
    // Carry over whatever rating (if any) this query already has, so a previously
    // rated question stays locked when revisited instead of re-offering the vote.
    setFeedbackSent(item.feedback);
  }, []);

  const sendFeedback = useCallback(
    async (rating: 1 | -1) => {
      if (!queryId || feedbackSent) return;
      setFeedbackSent(rating);
      try {
        await postFeedback(queryId, rating);
      } catch (err) {
        // 409 means the server already has a rating for this query (e.g. a race with
        // another tab) -- stay locked rather than re-opening the vote; any other error
        // is a real failure, so let the user try again.
        if (err instanceof ApiError && err.status === 409) return;
        setFeedbackSent(null);
      }
    },
    [queryId, feedbackSent]
  );

  return (
    <AskContext.Provider
      value={{
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
        loadFromHistory,
        sendFeedback,
        historyVersion,
      }}
    >
      {children}
    </AskContext.Provider>
  );
}

export function useAsk(): AskState {
  const ctx = useContext(AskContext);
  if (!ctx) throw new Error("useAsk must be used within an AskProvider");
  return ctx;
}
