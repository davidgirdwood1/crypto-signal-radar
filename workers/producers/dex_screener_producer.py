import hashlib
import time
from datetime import UTC, datetime
from typing import Any

import requests

from common.config import settings
from common.db import update_heartbeat
from common.kafka import DEX_BOOSTS_TOPIC, DEX_PROFILES_TOPIC, json_producer, send_json
from common.logging import configure_logging

logger = configure_logging("worker-dex-producer")

DEX_LATEST_BOOSTS_URL = "https://api.dexscreener.com/token-boosts/latest/v1"
DEX_TOP_BOOSTS_URL = "https://api.dexscreener.com/token-boosts/top/v1"
DEX_LATEST_PROFILES_URL = "https://api.dexscreener.com/token-profiles/latest/v1"
DEX_TOKEN_METADATA_URL_TEMPLATE = "https://api.dexscreener.com/tokens/v1/{chain_id}/{token_addresses}"

ENDPOINTS = [
    ("latest_boost", DEX_LATEST_BOOSTS_URL, DEX_BOOSTS_TOPIC),
    ("top_boost", DEX_TOP_BOOSTS_URL, DEX_BOOSTS_TOPIC),
    ("latest_profile", DEX_LATEST_PROFILES_URL, DEX_PROFILES_TOPIC),
]


def _items(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "items", "results"):
            if isinstance(payload.get(key), list):
                return [item for item in payload[key] if isinstance(item, dict)]
    return []


def _bucket(now: datetime) -> str:
    minute = now.minute - (now.minute % max(1, settings.dex_poll_interval_seconds // 60 or 1))
    return now.replace(minute=minute, second=0, microsecond=0).isoformat()


def _token_key(chain_id: str | None, token_address: str | None) -> tuple[str, str] | None:
    if not chain_id or not token_address:
        return None
    return (str(chain_id).lower(), str(token_address).lower())


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _token_from_pair(pair: dict[str, Any], token_address: str) -> dict[str, Any] | None:
    wanted = token_address.lower()
    for field in ("baseToken", "quoteToken"):
        token = pair.get(field)
        if isinstance(token, dict) and str(token.get("address", "")).lower() == wanted:
            return token
    return None


def _fetch_token_metadata(items: list[dict]) -> dict[tuple[str, str], dict[str, Any]]:
    addresses_by_chain: dict[str, set[str]] = {}
    original_addresses: dict[tuple[str, str], str] = {}
    for item in items:
        chain_id = item.get("chainId") or item.get("chain_id")
        token_address = item.get("tokenAddress") or item.get("token_address")
        key = _token_key(chain_id, token_address)
        if not key:
            continue
        addresses_by_chain.setdefault(key[0], set()).add(key[1])
        original_addresses[key] = str(token_address)

    metadata: dict[tuple[str, str], dict[str, Any]] = {}
    for chain_id, addresses in addresses_by_chain.items():
        for chunk in _chunks(sorted(addresses), 30):
            originals = [original_addresses[(chain_id, address)] for address in chunk]
            url = DEX_TOKEN_METADATA_URL_TEMPLATE.format(chain_id=chain_id, token_addresses=",".join(originals))
            try:
                response = requests.get(url, timeout=15)
                response.raise_for_status()
                pairs = response.json()
                if not isinstance(pairs, list):
                    continue
                for pair in pairs:
                    if not isinstance(pair, dict):
                        continue
                    for address in chunk:
                        token = _token_from_pair(pair, address)
                        if not token:
                            continue
                        key = (chain_id, address)
                        liquidity = ((pair.get("liquidity") or {}).get("usd") or 0) if isinstance(pair.get("liquidity"), dict) else 0
                        if liquidity <= metadata.get(key, {}).get("liquidity_usd", -1):
                            continue
                        metadata[key] = {
                            "symbol": token.get("symbol"),
                            "name": token.get("name"),
                            "liquidity_usd": liquidity,
                        }
            except Exception as exc:
                logger.warning("failed enriching %s token metadata: %s", chain_id, exc)
    return metadata


def _short_address(token_address: str | None) -> str | None:
    if not token_address:
        return None
    if len(token_address) <= 12:
        return token_address
    return f"{token_address[:6]}...{token_address[-4:]}"


def normalize(item: dict, event_type: str, observed_at: datetime, token_metadata: dict[str, Any] | None = None) -> dict:
    token_address = item.get("tokenAddress") or item.get("token_address")
    url = item.get("url")
    external_id = item.get("id") or token_address or url
    links = item.get("links") if isinstance(item.get("links"), list) else []
    description = item.get("description") or " ".join(str(link.get("label") or link.get("type") or "") for link in links if isinstance(link, dict)).strip() or None
    token_metadata = token_metadata or {}
    normalized = {
        "source": "dexscreener",
        "source_event_type": event_type,
        "external_id": str(external_id) if external_id else None,
        "chain_id": item.get("chainId") or item.get("chain_id"),
        "token_address": token_address,
        "symbol": item.get("symbol") or item.get("tokenSymbol") or token_metadata.get("symbol"),
        "name": item.get("name") or item.get("tokenName") or token_metadata.get("name") or _short_address(token_address),
        "url": url,
        "description": description,
        "raw_payload": item,
        "observed_at": observed_at.isoformat(),
    }
    basis = "|".join(
        [
            normalized["source"],
            normalized["source_event_type"],
            str(token_address or url or external_id),
            _bucket(observed_at),
        ]
    )
    normalized["unique_hash"] = hashlib.sha256(basis.encode("utf-8")).hexdigest()
    return normalized


def poll_once(producer) -> None:
    observed_at = datetime.now(UTC)
    published = 0
    for event_type, url, topic in ENDPOINTS:
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            items = _items(response.json())
            metadata = _fetch_token_metadata(items)
            events = [
                normalize(
                    item,
                    event_type,
                    observed_at,
                    metadata.get(_token_key(item.get("chainId") or item.get("chain_id"), item.get("tokenAddress") or item.get("token_address"))),
                )
                for item in items
            ]
            for event in events:
                send_json(producer, topic, event, key=event["unique_hash"])
            published += len(events)
            logger.info("published %s %s events to %s", len(events), event_type, topic)
        except Exception as exc:
            logger.exception("failed polling %s: %s", url, exc)
            update_heartbeat("worker-dex-producer", "degraded", {"last_error": str(exc), "endpoint": url})
    update_heartbeat("worker-dex-producer", "ok", {"published_last_poll": published})


def main() -> None:
    producer = json_producer()
    while True:
        poll_once(producer)
        time.sleep(settings.dex_poll_interval_seconds)


if __name__ == "__main__":
    main()
