import json
from typing import Any

from kafka import KafkaConsumer, KafkaProducer

from common.config import settings


DEX_BOOSTS_TOPIC = "crypto.dex.boosts.raw"
DEX_PROFILES_TOPIC = "crypto.dex.profiles.raw"
COINGECKO_TRENDING_TOPIC = "crypto.coingecko.trending.raw"
CLASSIFIED_TOPIC = "crypto.events.classified"
DEADLETTER_TOPIC = "crypto.events.deadletter"


def json_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        retries=5,
        value_serializer=lambda value: json.dumps(value, default=str).encode("utf-8"),
        key_serializer=lambda value: value.encode("utf-8") if value else None,
    )


def json_consumer(group_id: str, topics: list[str]) -> KafkaConsumer:
    return KafkaConsumer(
        *topics,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
    )


def send_json(producer: KafkaProducer, topic: str, payload: dict[str, Any], key: str | None = None) -> None:
    producer.send(topic, value=payload, key=key)
    producer.flush(timeout=10)
