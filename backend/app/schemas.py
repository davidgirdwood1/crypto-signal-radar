from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RawEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: str
    source_event_type: str
    external_id: str | None = None
    chain_id: str | None = None
    token_address: str | None = None
    symbol: str | None = None
    name: str | None = None
    url: str | None = None
    description: str | None = None
    raw_payload: dict
    observed_at: datetime
    created_at: datetime
    unique_hash: str
    processing_status: str


class ClassifiedEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    raw_event_id: UUID | None
    source: str
    symbol: str | None = None
    name: str | None = None
    classification: str
    sentiment: str
    risk_score: int
    confidence: float
    summary: str
    reasoning: str
    suggested_action: str
    affected_assets: list
    model_name: str
    prompt_version: str
    model_latency_ms: int | None = None
    raw_model_response: dict | None = None
    created_at: datetime


class ReprocessResponse(BaseModel):
    status: str
    raw_event_id: UUID


class DeadLetterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_topic: str
    payload: dict
    error_message: str
    retry_count: int
    created_at: datetime
