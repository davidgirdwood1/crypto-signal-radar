import { Bot, CircleCheck, PauseCircle, RadioTower, TriangleAlert } from "lucide-react";

const WORKER_LABELS = {
  "worker-ai-classifier": "AI Classifier",
  "worker-dex-producer": "DEX Producer",
  "worker-coingecko-producer": "CoinGecko Producer"
};

const SOURCE_LABELS = {
  dexscreener: "DEX Screener",
  coingecko: "CoinGecko"
};

const STALE_AFTER_MS = {
  "worker-ai-classifier": 30_000,
  "worker-dex-producer": 150_000,
  "worker-coingecko-producer": 420_000
};

function workerLabel(name) {
  return WORKER_LABELS[name] || name.replace(/^worker-/, "").replaceAll("-", " ");
}

function sourceLabel(name) {
  return SOURCE_LABELS[name] || name;
}

function displayStatus(worker) {
  if (!worker?.last_seen_at) return "paused";
  const ageMs = Date.now() - new Date(worker.last_seen_at).getTime();
  const staleAfter = STALE_AFTER_MS[worker.worker_name] || 120_000;
  if (Number.isFinite(ageMs) && ageMs > staleAfter) return "paused";
  return worker.status;
}

function StatusIcon({ status }) {
  if (status === "ok" || status === "idle") return <CircleCheck size={14} />;
  if (status === "paused") return <PauseCircle size={14} />;
  return <TriangleAlert size={14} />;
}

export default function PipelineHealth({ cards, heartbeats, summary, loading }) {
  const sources = Object.entries(summary.source_counts || {});

  return (
    <section className="health-grid" aria-label="Pipeline health">
      {cards.map(({ label, value, icon: Icon, onClick }) => {
        const Component = onClick ? "button" : "div";
        return (
          <Component
            className={`metric-card ${onClick ? "metric-card-button" : ""}`}
            key={label}
            onClick={onClick}
            type={onClick ? "button" : undefined}
          >
            <div className="metric-icon"><Icon size={18} /></div>
            <span>{label}</span>
            <strong>{loading ? "..." : value}</strong>
          </Component>
        );
      })}
      <div className="worker-strip">
        {heartbeats.length ? heartbeats.map((worker) => (
          <span className={`worker-pill ${displayStatus(worker)}`} key={worker.worker_name}>
            <Bot size={14} />
            <span>{workerLabel(worker.worker_name)}</span>
            <span className="status-mark">
              <StatusIcon status={displayStatus(worker)} />
              {displayStatus(worker)}
            </span>
          </span>
        )) : (
          <span className="worker-pill paused">
            <RadioTower size={14} />
            <span>Workers</span>
            <span className="status-mark"><PauseCircle size={14} /> warming</span>
          </span>
        )}
        <span className="source-counts">
          <span>Sources</span>
          {sources.length ? sources.map(([key, value]) => (
            <strong key={key}>{sourceLabel(key)} {value}</strong>
          )) : <strong>none yet</strong>}
        </span>
      </div>
    </section>
  );
}
