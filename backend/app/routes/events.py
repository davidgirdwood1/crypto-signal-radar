from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from kafka import KafkaProducer
from sqlalchemy.orm import Session

from app import crud
from app.config import settings
from app.db import get_db
from app.models import RawEvent
from app.schemas import ClassifiedEventOut, RawEventOut, ReprocessResponse

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/raw", response_model=list[RawEventOut])
def raw_events(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    return crud.list_raw_events(db, limit=limit)


@router.get("/classified", response_model=list[ClassifiedEventOut])
def classified_events(
    limit: int = Query(100, ge=1, le=500),
    source: str | None = None,
    classification: str | None = None,
    sentiment: str | None = None,
    min_risk_score: int | None = Query(None, ge=0, le=100),
    token_key: str | None = None,
    dedupe_token_events: bool = False,
    db: Session = Depends(get_db),
):
    return crud.list_classified_events(db, limit, source, classification, sentiment, min_risk_score, token_key, dedupe_token_events)


@router.get("/classified/{event_id}", response_model=ClassifiedEventOut)
def classified_event(event_id: UUID, db: Session = Depends(get_db)):
    event = crud.get_classified_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Classified event not found")
    return event


@router.post("/{raw_event_id}/reprocess", response_model=ReprocessResponse)
def reprocess_event(raw_event_id: UUID, db: Session = Depends(get_db)):
    raw_event = db.get(RawEvent, raw_event_id)
    if not raw_event:
        raise HTTPException(status_code=404, detail="Raw event not found")

    producer = KafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda value: __import__("json").dumps(value, default=str).encode("utf-8"),
    )
    if raw_event.source == "coingecko":
        topic = "crypto.coingecko.trending.raw"
    elif raw_event.source_event_type == "latest_profile":
        topic = "crypto.dex.profiles.raw"
    else:
        topic = "crypto.dex.boosts.raw"
    payload = {
        "source": raw_event.source,
        "source_event_type": raw_event.source_event_type,
        "external_id": raw_event.external_id,
        "chain_id": raw_event.chain_id,
        "token_address": raw_event.token_address,
        "symbol": raw_event.symbol,
        "name": raw_event.name,
        "url": raw_event.url,
        "description": raw_event.description,
        "raw_payload": raw_event.raw_payload,
        "observed_at": raw_event.observed_at.isoformat(),
        "unique_hash": raw_event.unique_hash,
        "reprocess_raw_event_id": str(raw_event.id),
    }
    producer.send(topic, payload)
    producer.flush(timeout=10)
    producer.close()
    return {"status": "queued", "raw_event_id": raw_event.id}
