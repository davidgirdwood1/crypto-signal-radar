import { useEffect, useRef, useState } from "react";
import EventCard from "./EventCard";

function tokenKey(value) {
  return String(value || "").trim().toLowerCase();
}

export default function EventFeed({ events, feedFocus, focusedToken, onClearFocus, onFocusHandled }) {
  const cardRefs = useRef(new Map());
  const [highlightedId, setHighlightedId] = useState("");
  const normalizedFocus = tokenKey(focusedToken?.key || focusedToken);

  useEffect(() => {
    if (!normalizedFocus) return;
    const target = events.find((event) => {
      const keys = [event.symbol, event.name].map(tokenKey);
      return keys.includes(normalizedFocus);
    });
    if (!target) return;

    const node = cardRefs.current.get(target.id);
    if (!node) return;
    node.scrollIntoView({ behavior: "smooth", block: "center" });
    setHighlightedId(target.id);
    onFocusHandled?.();
  }, [events, normalizedFocus, focusedToken?.requestedAt, onFocusHandled]);

  useEffect(() => {
    if (!highlightedId) return undefined;
    const timer = window.setTimeout(() => setHighlightedId(""), 1600);
    return () => window.clearTimeout(timer);
  }, [highlightedId]);

  return (
    <section className="panel feed-panel">
      <div className="panel-heading">
        <div>
          <h2>{feedFocus ? `Live Event Feed: ${feedFocus.label}` : "Live Event Feed"}</h2>
          {feedFocus && <button className="text-button" onClick={onClearFocus}>Clear focus</button>}
        </div>
        <span>{events.length}</span>
      </div>
      <div className="event-list">
        {events.map((event) => {
          return (
            <EventCard
              event={event}
              highlighted={event.id === highlightedId}
              key={event.id}
              refCallback={(node) => {
                if (node) cardRefs.current.set(event.id, node);
                else cardRefs.current.delete(event.id);
              }}
            />
          );
        })}
        {!events.length && <div className="empty-state">Waiting for Kafka events to be classified.</div>}
      </div>
    </section>
  );
}
