from uuid import UUID

from sqlalchemy import desc, func, select, text
from sqlalchemy.orm import Session

from app.models import ClassifiedEvent, DeadLetter, ModelRun, RawEvent, WorkerHeartbeat


def list_raw_events(db: Session, limit: int = 100) -> list[RawEvent]:
    return list(db.scalars(select(RawEvent).order_by(desc(RawEvent.observed_at)).limit(limit)))


def list_classified_events(
    db: Session,
    limit: int = 100,
    source: str | None = None,
    classification: str | None = None,
    sentiment: str | None = None,
    min_risk_score: int | None = None,
    token_key: str | None = None,
    dedupe_token_events: bool = False,
) -> list[ClassifiedEvent]:
    stmt = select(ClassifiedEvent)
    if source:
        stmt = stmt.where(ClassifiedEvent.source == source)
    if classification:
        stmt = stmt.where(ClassifiedEvent.classification == classification)
    if sentiment:
        stmt = stmt.where(ClassifiedEvent.sentiment == sentiment)
    if min_risk_score is not None:
        stmt = stmt.where(ClassifiedEvent.risk_score >= min_risk_score)
    if token_key:
        normalized_token_key = token_key.strip().lower()
        stmt = stmt.where(
            func.lower(
                func.coalesce(
                    func.nullif(ClassifiedEvent.symbol, ""),
                    func.nullif(ClassifiedEvent.name, ""),
                    "UNKNOWN",
                )
            )
            == normalized_token_key
        )
    if dedupe_token_events:
        ranked = stmt.add_columns(
            func.row_number()
            .over(
                partition_by=(
                    ClassifiedEvent.source,
                    RawEvent.source_event_type,
                ),
                order_by=desc(ClassifiedEvent.created_at),
            )
            .label("rn")
        ).join(RawEvent, ClassifiedEvent.raw_event_id == RawEvent.id).subquery()
        stmt = (
            select(ClassifiedEvent)
            .join(ranked, ClassifiedEvent.id == ranked.c.id)
            .where(ranked.c.rn == 1)
        )
    stmt = stmt.order_by(desc(ClassifiedEvent.created_at)).limit(limit)
    return list(db.scalars(stmt))


def get_classified_event(db: Session, event_id: UUID) -> ClassifiedEvent | None:
    return db.get(ClassifiedEvent, event_id)


def summary(db: Session) -> dict:
    classification_counts = dict(db.execute(select(ClassifiedEvent.classification, func.count()).group_by(ClassifiedEvent.classification)).all())
    source_counts = dict(db.execute(select(RawEvent.source, func.count()).group_by(RawEvent.source)).all())
    return {
        "raw_events_count": db.scalar(select(func.count()).select_from(RawEvent)) or 0,
        "classified_events_count": db.scalar(select(func.count()).select_from(ClassifiedEvent)) or 0,
        "dead_letters_count": db.scalar(select(func.count()).select_from(DeadLetter)) or 0,
        "avg_model_latency_ms": db.scalar(select(func.avg(ModelRun.latency_ms)).where(ModelRun.latency_ms.is_not(None))),
        "latest_event_at": db.scalar(select(func.max(RawEvent.observed_at))),
        "classification_counts": classification_counts,
        "source_counts": source_counts,
    }


def list_worker_heartbeats(db: Session) -> list[WorkerHeartbeat]:
    return list(db.scalars(select(WorkerHeartbeat).order_by(desc(WorkerHeartbeat.last_seen_at))))


def list_model_runs(db: Session, limit: int = 50) -> list[ModelRun]:
    return list(db.scalars(select(ModelRun).order_by(desc(ModelRun.created_at)).limit(limit)))


def list_dead_letters(db: Session, limit: int = 50) -> list[DeadLetter]:
    return list(db.scalars(select(DeadLetter).order_by(desc(DeadLetter.created_at)).limit(limit)))


def risk_board(
    db: Session,
    source: str | None = None,
    classification: str | None = None,
    sentiment: str | None = None,
    min_risk_score: int | None = None,
) -> list[dict]:
    filters = []
    params = {}
    if source:
        filters.append("source = :source")
        params["source"] = source
    if classification:
        filters.append("classification = :classification")
        params["classification"] = classification
    if sentiment:
        filters.append("sentiment = :sentiment")
        params["sentiment"] = sentiment
    if min_risk_score is not None:
        filters.append("risk_score >= :min_risk_score")
        params["min_risk_score"] = min_risk_score
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = db.execute(
        text(
            f"""
            WITH ranked AS (
              SELECT
                COALESCE(NULLIF(symbol, ''), NULLIF(name, ''), 'UNKNOWN') AS token_key,
                symbol,
                name,
                classification,
                sentiment,
                risk_score,
                confidence,
                created_at,
                row_number() OVER (
                  PARTITION BY COALESCE(NULLIF(symbol, ''), NULLIF(name, ''), 'UNKNOWN')
                  ORDER BY created_at DESC
                ) AS rn
              FROM classified_events
              {where_clause}
            )
            SELECT
              token_key,
              max(symbol) FILTER (WHERE symbol IS NOT NULL) AS symbol,
              max(name) FILTER (WHERE name IS NOT NULL) AS name,
              max(classification) FILTER (WHERE rn = 1) AS latest_classification,
              max(sentiment) FILTER (WHERE rn = 1) AS latest_sentiment,
              max(risk_score) AS max_risk_score,
              avg(confidence) AS avg_confidence,
              count(*) AS event_count,
              max(created_at) AS last_seen_at
            FROM ranked
            GROUP BY token_key
            ORDER BY last_seen_at DESC, max_risk_score DESC
            LIMIT 100
            """
        ),
        params,
    ).mappings()
    return [dict(row) for row in rows]
