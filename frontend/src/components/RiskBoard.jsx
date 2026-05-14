function formatSeenAt(value) {
  if (!value) return { date: "n/a", time: "" };

  const date = new Date(value);

  return {
    date: date.toLocaleDateString(),
    time: date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }),
  };
}

function riskLevel(score) {
  if (score <= 30) return "low";
  if (score <= 60) return "medium";
  if (score <= 80) return "high";
  return "extreme";
}

export default function RiskBoard({ rows, onSelectToken }) {
  return (
    <section className="panel risk-panel">
      <div className="panel-heading">
        <h2>Crypto Risk Board</h2>
        <span>{rows.length}</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Token</th>
              <th>Risk</th>
              <th>Class</th>
              <th>Events</th>
              <th>Seen</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const seenAt = formatSeenAt(row.last_seen_at);

              return (
                <tr
                  className={`risk-board-row ${riskLevel(row.max_risk_score)}`}
                  key={row.token_key}
                  onClick={() => onSelectToken?.(row)}
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelectToken?.(row);
                    }
                  }}
                >
                  <td>
                    <strong>{row.symbol || row.name || row.token_key}</strong>
                    <span>{row.latest_sentiment}</span>
                  </td>
                  <td><span className={`risk-chip ${riskLevel(row.max_risk_score)}`}>{row.max_risk_score}</span></td>
                  <td><span className="class-chip">{row.latest_classification}</span></td>
                  <td>{row.event_count}</td>
                  <td className="seen-cell">
                    <span>{seenAt.date}</span>
                    {seenAt.time && <span>{seenAt.time}</span>}
                  </td>
                </tr>
              );
            })}
            {!rows.length && (
              <tr>
                <td colSpan="5" className="empty-cell">No classified tokens yet</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
