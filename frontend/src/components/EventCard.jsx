import SourceBadge from "./SourceBadge";

function riskLevel(score) {
  if (score <= 30) return "low";
  if (score <= 60) return "medium";
  if (score <= 80) return "high";
  return "extreme";
}

export default function EventCard({ event, highlighted = false, refCallback }) {
  const level = riskLevel(event.risk_score);
  const displayName = event.symbol || event.name || "Unknown token";

  return (
    <article className={`event-card ${highlighted ? "focused" : ""}`} ref={refCallback}>
      <div className="event-card-top">
        <div>
          <h3>{displayName}</h3>
          <p>{event.name && event.symbol ? event.name : event.source}</p>
        </div>
        <SourceBadge source={event.source} />
      </div>
      <div className="badge-row">
        <span className="badge classification">{event.classification}</span>
        <span className={`badge sentiment ${event.sentiment}`}>{event.sentiment}</span>
        <span className={`badge risk ${level}`}>risk {event.risk_score}</span>
        <span className="badge confidence">{Math.round(event.confidence * 100)}% confidence</span>
      </div>
      <p className="summary">{event.summary}</p>
      <p className="reasoning">{event.reasoning}</p>
      <div className="action-row">
        <span>{event.suggested_action}</span>
        <small>{event.model_name} | {new Date(event.created_at).toLocaleString()}</small>
      </div>
    </article>
  );
}
