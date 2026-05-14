import hashlib
import time
from datetime import UTC, datetime
from typing import Any

import requests

from common.config import settings
from common.db import update_heartbeat
from common.kafka import COINGECKO_TRENDING_TOPIC, json_producer, send_json
from common.logging import configure_logging

logger = configure_logging("worker-coingecko-producer")

URL = "https://api.coingecko.com/api/v3/search/trending"


def _bucket(now: datetime) -> str:
    minute = now.minute - (now.minute % max(1, settings.coingecko_poll_interval_seconds // 60 or 1))
    return now.replace(minute=minute, second=0, microsecond=0).isoformat()


def normalize(item: dict[str, Any], observed_at: datetime) -> dict[str, Any]:
    coin = item.get("item", item)
    coin_id = coin.get("id") or coin.get("coin_id")
    normalized = {
        "source": "coingecko",
        "source_event_type": "trending_coin",
        "external_id": str(coin_id or coin.get("slug") or coin.get("name")),
        "coin_id": coin_id,
        "symbol": coin.get("symbol"),
        "name": coin.get("name"),
        "market_cap_rank": coin.get("market_cap_rank"),
        "raw_payload": item,
        "observed_at": observed_at.isoformat(),
    }
    basis = "|".join(["coingecko", "trending_coin", str(coin_id or coin.get("symbol")), _bucket(observed_at)])
    normalized["unique_hash"] = hashlib.sha256(basis.encode("utf-8")).hexdigest()
    return normalized


def poll_once(producer) -> None:
    try:
        observed_at = datetime.now(UTC)
        response = requests.get(URL, timeout=20)
        response.raise_for_status()
        payload = response.json()
        coins = payload.get("coins", []) if isinstance(payload, dict) else []
        events = [normalize(item, observed_at) for item in coins if isinstance(item, dict)]
        for event in events:
            send_json(producer, COINGECKO_TRENDING_TOPIC, event, key=event["unique_hash"])
        logger.info("published %s trending events to %s", len(events), COINGECKO_TRENDING_TOPIC)
        update_heartbeat("worker-coingecko-producer", "ok", {"published_last_poll": len(events)})
    except Exception as exc:
        logger.exception("failed polling CoinGecko: %s", exc)
        update_heartbeat("worker-coingecko-producer", "degraded", {"last_error": str(exc)})


def main() -> None:
    producer = json_producer()
    while True:
        poll_once(producer)
        time.sleep(settings.coingecko_poll_interval_seconds)


if __name__ == "__main__":
    main()
