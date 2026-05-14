from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from common.config import settings
from common.db import session_scope
from common.kafka import (
    CLASSIFIED_TOPIC,
    COINGECKO_TRENDING_TOPIC,
    DEADLETTER_TOPIC,
    DEX_BOOSTS_TOPIC,
    DEX_PROFILES_TOPIC,
    json_consumer,
    json_producer,
    send_json,
)
from common.logging import configure_logging
from common.models import ClassifiedEvent, DeadLetter, ModelRun, RawEvent, WorkerHeartbeat
from common.deepseek_client import classify_event
from common.prompts import PROMPT_VERSION

logger = configure_logging("worker-ai-classifier")

TOPICS = [DEX_BOOSTS_TOPIC, DEX_PROFILES_TOPIC, COINGECKO_TRENDING_TOPIC]


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _heartbeat(db, status: str, details: dict[str, Any] | None = None) -> None:
    heartbeat = db.get(WorkerHeartbeat, "worker-ai-classifier")
    if heartbeat is None:
        heartbeat = WorkerHeartbeat(worker_name="worker-ai-classifier")
        db.add(heartbeat)
    heartbeat.status = status
    heartbeat.last_seen_at = datetime.now(UTC)
    heartbeat.details = details or {}


def _insert_raw_event(db, event: dict[str, Any]) -> RawEvent:
    existing = db.scalar(select(RawEvent).where(RawEvent.unique_hash == event["unique_hash"]))
    if existing:
        return existing

    raw_event = RawEvent(
        source=event["source"],
        source_event_type=event["source_event_type"],
        external_id=event.get("external_id"),
        chain_id=event.get("chain_id"),
        token_address=event.get("token_address"),
        symbol=event.get("symbol"),
        name=event.get("name"),
        url=event.get("url"),
        description=event.get("description"),
        raw_payload=event.get("raw_payload", event),
        observed_at=_parse_dt(event.get("observed_at")),
        unique_hash=event["unique_hash"],
        processing_status="processing",
    )
    db.add(raw_event)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return db.scalar(select(RawEvent).where(RawEvent.unique_hash == event["unique_hash"]))
    return raw_event


def _record_dead_letter(producer, topic: str, payload: dict[str, Any], error: str) -> None:
    logger.exception("dead-lettering event from %s: %s", topic, error)
    with session_scope() as db:
        db.add(DeadLetter(source_topic=topic, payload=payload, error_message=error))
        _heartbeat(db, "degraded", {"last_error": error})
    send_json(producer, DEADLETTER_TOPIC, {"source_topic": topic, "payload": payload, "error_message": error})


def process_event(producer, topic: str, event: dict[str, Any]) -> None:
    with session_scope() as db:
        raw_event = _insert_raw_event(db, event)
        already_classified = db.scalar(
            select(ClassifiedEvent.id).where(ClassifiedEvent.raw_event_id == raw_event.id).limit(1)
        )
        if already_classified and not event.get("reprocess_raw_event_id"):
            _heartbeat(db, "ok", {"last_topic": topic, "duplicate_skipped": True})
            logger.info("skipped duplicate classification for raw event %s", raw_event.id)
            return
        model_result = classify_event(event)
        classification = model_result["classification"]
        raw_model_response = model_result["raw_response"] | {"mock_mode": model_result["mock_mode"]}

        classified = ClassifiedEvent(
            raw_event_id=raw_event.id,
            source=event["source"],
            symbol=event.get("symbol"),
            name=event.get("name"),
            classification=classification["classification"],
            sentiment=classification["sentiment"],
            risk_score=classification["risk_score"],
            confidence=classification["confidence"],
            summary=classification["summary"],
            reasoning=classification["reasoning"],
            suggested_action=classification["suggested_action"],
            affected_assets=classification["affected_assets"],
            model_name=settings.deepseek_model,
            prompt_version=PROMPT_VERSION,
            model_latency_ms=model_result["latency_ms"],
            raw_model_response=raw_model_response,
        )
        db.add(classified)
        raw_event.processing_status = "classified"
        db.add(
            ModelRun(
                raw_event_id=raw_event.id,
                model_name=settings.deepseek_model,
                prompt_version=PROMPT_VERSION,
                input_tokens=model_result["input_tokens"],
                output_tokens=model_result["output_tokens"],
                latency_ms=model_result["latency_ms"],
                status="mock" if model_result["mock_mode"] else "success",
                error_message=None,
            )
        )
        _heartbeat(
            db,
            "ok",
            {
                "last_topic": topic,
                "mock_mode": model_result["mock_mode"],
                "poll_timeout_seconds": settings.ai_worker_poll_timeout_seconds,
            },
        )
        db.flush()
        classified_payload = {
            "id": str(classified.id),
            "raw_event_id": str(raw_event.id),
            "classification": classification,
            "source": event["source"],
            "symbol": event.get("symbol"),
            "name": event.get("name"),
            "mock_mode": model_result["mock_mode"],
        }
    send_json(producer, CLASSIFIED_TOPIC, classified_payload, key=classified_payload["raw_event_id"])
    logger.info("classified %s %s as %s", event.get("source"), event.get("symbol") or event.get("name"), classification["classification"])


def main() -> None:
    consumer = json_consumer("crypto-signal-radar-ai-classifier", TOPICS)
    producer = json_producer()
    logger.info("listening on %s", ", ".join(TOPICS))

    while True:
        try:
            records = consumer.poll(timeout_ms=settings.ai_worker_poll_timeout_seconds * 1000)
            if not records:
                with session_scope() as db:
                    _heartbeat(db, "idle", {"topics": TOPICS})
                continue
            for messages in records.values():
                for message in messages:
                    try:
                        process_event(producer, message.topic, message.value)
                    except Exception as exc:
                        _record_dead_letter(producer, message.topic, message.value, str(exc))
        except Exception as exc:
            logger.exception("consumer loop error: %s", exc)


if __name__ == "__main__":
    main()
