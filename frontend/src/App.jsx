import { useEffect, useState } from "react";
import { Activity, Database, Pause, Play, RadioTower, ShieldAlert, Timer, X } from "lucide-react";
import { fetchClassifiedEvents, fetchDeadLetters, fetchHeartbeats, fetchRiskBoard, fetchSummary } from "./api";
import EventFeed from "./components/EventFeed";
import FilterBar from "./components/FilterBar";
import PipelineHealth from "./components/PipelineHealth";
import RiskBoard from "./components/RiskBoard";

const emptySummary = {
  raw_events_count: 0,
  classified_events_count: 0,
  dead_letters_count: 0,
  avg_model_latency_ms: null,
  classification_counts: {},
  source_counts: {}
};

function formatSeconds(ms) {
  if (ms == null) return "n/a";
  const seconds = Number(ms) / 1000;
  if (!Number.isFinite(seconds)) return "n/a";
  return `${seconds.toFixed(seconds >= 10 ? 1 : 2)} s`;
}

function tokenKey(value) {
  return String(value || "").trim().toLowerCase();
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString() : "n/a";
}

export default function App() {
  const [summary, setSummary] = useState(emptySummary);
  const [heartbeats, setHeartbeats] = useState([]);
  const [events, setEvents] = useState([]);
  const [riskBoard, setRiskBoard] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(false);
  const [focusedToken, setFocusedToken] = useState(null);
  const [feedFocus, setFeedFocus] = useState(null);
  const [deadLetters, setDeadLetters] = useState([]);
  const [deadLettersOpen, setDeadLettersOpen] = useState(false);
  const [deadLettersLoading, setDeadLettersLoading] = useState(false);
  const [deadLettersError, setDeadLettersError] = useState("");
  const [filters, setFilters] = useState({
    source: "",
    classification: "",
    sentiment: "",
    min_risk_score: ""
  });

  async function load() {
    try {
      setError("");
      const [summaryData, heartbeatData, eventData, riskData] = await Promise.all([
        fetchSummary(),
        fetchHeartbeats(),
        fetchClassifiedEvents(feedFocus ? { ...filters, token_key: feedFocus.tokenKey, dedupe_token_events: true } : filters),
        fetchRiskBoard(filters)
      ]);
      setSummary(summaryData);
      setHeartbeats(heartbeatData);
      setEvents(eventData);
      setRiskBoard(riskData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [filters, feedFocus]);

  useEffect(() => {
    if (!polling) return undefined;
    const interval = window.setInterval(load, 15000);
    return () => window.clearInterval(interval);
  }, [polling, filters, feedFocus]);

  function togglePolling() {
    setPolling((current) => {
      const next = !current;
      if (next) load();
      return next;
    });
  }

  function eventMatchesToken(event, row) {
    const selectedKeys = [row.symbol, row.name, row.token_key].map(tokenKey).filter(Boolean);
    const eventKeys = [event.symbol, event.name].map(tokenKey).filter(Boolean);
    return selectedKeys.some((selectedKey) => eventKeys.includes(selectedKey));
  }

  async function handleRiskSelect(row) {
    if (!events.some((event) => eventMatchesToken(event, row))) {
      try {
        setError("");
        setEvents(await fetchClassifiedEvents({ ...filters, token_key: row.token_key, dedupe_token_events: true }));
      } catch (err) {
        setError(err.message);
        return;
      }
    }
    setFeedFocus({
      label: row.symbol || row.name || row.token_key,
      tokenKey: row.token_key
    });
    setFocusedToken({
      key: tokenKey(row.token_key || row.symbol || row.name),
      requestedAt: Date.now()
    });
  }

  async function clearFeedFocus() {
    setFeedFocus(null);
    setFocusedToken(null);
    try {
      setError("");
      setEvents(await fetchClassifiedEvents(filters));
    } catch (err) {
      setError(err.message);
    }
  }

  async function openDeadLetters() {
    setDeadLettersOpen(true);
    setDeadLettersLoading(true);
    setDeadLettersError("");
    try {
      setDeadLetters(await fetchDeadLetters());
    } catch (err) {
      setDeadLettersError(err.message);
    } finally {
      setDeadLettersLoading(false);
    }
  }

  const metricCards = [
    { label: "Raw events", value: summary.raw_events_count, icon: Database },
    { label: "Classified", value: summary.classified_events_count, icon: Activity },
    { label: "Dead letters", value: summary.dead_letters_count, icon: ShieldAlert, onClick: summary.dead_letters_count > 0 ? openDeadLetters : undefined },
    { label: "Avg model response", value: formatSeconds(summary.avg_model_latency_ms), icon: Timer },
    { label: "Workers", value: heartbeats.length || "warming", icon: RadioTower }
  ];

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>Crypto Signal Radar</h1>
          <p>AI-powered crypto event triage using Kafka, FastAPI, PostgreSQL, and DeepSeek</p>
        </div>
        <div className="polling-control">
          <span>{polling ? "Live polling" : "Paused"}</span>
          <button
            className={`icon-button ${polling ? "polling" : "paused"}`}
            onClick={togglePolling}
            aria-label={polling ? "Pause dashboard polling" : "Start dashboard polling"}
            title={polling ? "Pause dashboard polling" : "Start dashboard polling"}
          >
            {polling ? <Pause size={18} /> : <Play size={18} />}
          </button>
        </div>
      </header>

      {error && <div className="error-banner">API unavailable: {error}</div>}

      <PipelineHealth cards={metricCards} heartbeats={heartbeats} summary={summary} loading={loading} />

      <section className="dashboard-grid">
        <div className="feed-column">
          <FilterBar filters={filters} onChange={setFilters} />
          <EventFeed
            events={events}
            feedFocus={feedFocus}
            focusedToken={focusedToken}
            onClearFocus={clearFeedFocus}
            onFocusHandled={() => setFocusedToken(null)}
          />
        </div>
        <aside className="side-column">
          <RiskBoard rows={riskBoard} onSelectToken={handleRiskSelect} />
        </aside>
      </section>

      {deadLettersOpen && (
        <div className="modal-backdrop" role="presentation">
          <section className="modal" role="dialog" aria-modal="true" aria-labelledby="dead-letter-title">
            <div className="modal-heading">
              <div>
                <h2 id="dead-letter-title">Dead Letters</h2>
                <span>{deadLetters.length} recent failures</span>
              </div>
              <button
                className="icon-button"
                onClick={() => setDeadLettersOpen(false)}
                aria-label="Close dead letters"
                title="Close dead letters"
              >
                <X size={18} />
              </button>
            </div>
            <div className="dead-letter-list">
              {deadLettersLoading && <div className="empty-state">Loading dead letters.</div>}
              {deadLettersError && <div className="error-banner">Unable to load dead letters: {deadLettersError}</div>}
              {!deadLettersLoading && !deadLettersError && deadLetters.map((letter) => (
                <article className="dead-letter" key={letter.id}>
                  <div className="dead-letter-meta">
                    <strong>{letter.source_topic}</strong>
                    <span>{formatDate(letter.created_at)}</span>
                  </div>
                  <p>{letter.error_message}</p>
                  <div className="dead-letter-meta">
                    <span>Retries {letter.retry_count}</span>
                    <span>{letter.id}</span>
                  </div>
                  <pre>{JSON.stringify(letter.payload, null, 2)}</pre>
                </article>
              ))}
              {!deadLettersLoading && !deadLettersError && !deadLetters.length && (
                <div className="empty-state">No dead letters found.</div>
              )}
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
