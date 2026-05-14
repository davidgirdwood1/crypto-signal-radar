from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import crud
from app.db import get_db
from app.schemas import DeadLetterOut

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats/summary")
def stats_summary(db: Session = Depends(get_db)) -> dict:
    data = crud.summary(db)
    if data["avg_model_latency_ms"] is not None:
        data["avg_model_latency_ms"] = round(float(data["avg_model_latency_ms"]), 2)
    if data["latest_event_at"] is not None:
        data["latest_event_at"] = data["latest_event_at"].isoformat()
    return data


@router.get("/stats/worker-heartbeats")
def worker_heartbeats(db: Session = Depends(get_db)) -> list[dict]:
    return [
        {
            "worker_name": hb.worker_name,
            "status": hb.status,
            "last_seen_at": hb.last_seen_at.isoformat(),
            "details": hb.details,
        }
        for hb in crud.list_worker_heartbeats(db)
    ]


@router.get("/stats/model-runs")
def model_runs(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)) -> list[dict]:
    return [
        {
            "id": str(run.id),
            "raw_event_id": str(run.raw_event_id) if run.raw_event_id else None,
            "model_name": run.model_name,
            "prompt_version": run.prompt_version,
            "input_tokens": run.input_tokens,
            "output_tokens": run.output_tokens,
            "latency_ms": run.latency_ms,
            "status": run.status,
            "error_message": run.error_message,
            "created_at": run.created_at.isoformat(),
        }
        for run in crud.list_model_runs(db, limit)
    ]


@router.get("/dead-letters", response_model=list[DeadLetterOut])
def dead_letters(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    return crud.list_dead_letters(db, limit)


@router.get("/tokens/risk-board")
def token_risk_board(
    source: str | None = None,
    classification: str | None = None,
    sentiment: str | None = None,
    min_risk_score: int | None = Query(None, ge=0, le=100),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = crud.risk_board(db, source, classification, sentiment, min_risk_score)
    for row in rows:
        if row.get("avg_confidence") is not None:
            row["avg_confidence"] = round(float(row["avg_confidence"]), 3)
        if row.get("last_seen_at") is not None:
            row["last_seen_at"] = row["last_seen_at"].isoformat()
    return rows
