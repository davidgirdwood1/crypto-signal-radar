import json
import time
from typing import Any

import requests

from common.config import settings
from common.prompts import CLASSIFICATIONS, PROMPT_VERSION, SENTIMENTS, SYSTEM_PROMPT, user_prompt


def _mock_classify(event: dict[str, Any]) -> dict[str, Any]:
    source_type = event.get("source_event_type", "")
    text = " ".join(
        str(event.get(key) or "")
        for key in ("symbol", "name", "description", "url", "source_event_type")
    ).lower()
    symbol = (event.get("symbol") or event.get("name") or "TOKEN").upper()

    if "boost" in source_type or "meme" in text or "inu" in text or "pepe" in text:
        classification = "Hype / Meme Pump"
        sentiment = "risky"
        risk_score = 78
    elif "profile" in source_type:
        classification = "Social / Narrative Signal"
        sentiment = "neutral"
        risk_score = 55
    elif event.get("market_cap_rank"):
        classification = "Bullish Momentum"
        sentiment = "bullish"
        risk_score = 38
    else:
        classification = "Noise / Ignore"
        sentiment = "unknown"
        risk_score = 50

    return {
        "classification": classification,
        "sentiment": sentiment,
        "risk_score": risk_score,
        "confidence": 0.72,
        "summary": f"{symbol} triggered a {classification.lower()} event from {event.get('source')}.",
        "reasoning": "This deterministic local classifier is running because DEEPSEEK_API_KEY is not set. It uses source type and basic token metadata to create a stable demo result. Treat this as pipeline validation, not investment research.",
        "suggested_action": "Watchlist only. Do not treat this as a validated investment signal.",
        "affected_assets": [symbol],
        "mock_mode": True,
    }


def _validate_model_json(data: dict[str, Any]) -> dict[str, Any]:
    classification = data.get("classification")
    sentiment = data.get("sentiment")
    if classification not in CLASSIFICATIONS:
        raise ValueError(f"Invalid classification: {classification}")
    if sentiment not in SENTIMENTS:
        raise ValueError(f"Invalid sentiment: {sentiment}")

    risk_score = int(data.get("risk_score"))
    confidence = float(data.get("confidence"))
    if not 0 <= risk_score <= 100:
        raise ValueError("risk_score must be between 0 and 100")
    if not 0 <= confidence <= 1:
        raise ValueError("confidence must be between 0 and 1")

    return {
        "classification": classification,
        "sentiment": sentiment,
        "risk_score": risk_score,
        "confidence": confidence,
        "summary": str(data.get("summary", ""))[:1000],
        "reasoning": str(data.get("reasoning", ""))[:4000],
        "suggested_action": str(data.get("suggested_action", ""))[:1000],
        "affected_assets": data.get("affected_assets") if isinstance(data.get("affected_assets"), list) else [],
    }


def _parse_model_json(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, char in enumerate(content):
            if char != "{":
                continue
            try:
                parsed, _ = decoder.raw_decode(content[index:])
                break
            except json.JSONDecodeError:
                continue
        else:
            raise

    if not isinstance(parsed, dict):
        raise ValueError("Model response must be a JSON object")
    return parsed


def classify_event(event: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    if not settings.deepseek_api_key:
        result = _mock_classify(event)
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "classification": _validate_model_json(result),
            "raw_response": result,
            "latency_ms": latency_ms,
            "input_tokens": None,
            "output_tokens": None,
            "mock_mode": True,
        }

    def fallback(error: Exception) -> dict[str, Any]:
        result = _mock_classify(event) | {"fallback_error": str(error), "fallback_reason": type(error).__name__}
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "classification": _validate_model_json(result),
            "raw_response": result,
            "latency_ms": latency_ms,
            "input_tokens": None,
            "output_tokens": None,
            "mock_mode": True,
        }

    body = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt(event)},
        ],
        "temperature": 0.2,
        "max_tokens": 800,
    }
    attempts = max(1, settings.deepseek_max_retries + 1)
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = requests.post(
                f"{settings.deepseek_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.deepseek_api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=settings.deepseek_request_timeout_seconds,
            )
            response.raise_for_status()
            raw_response = response.json()
            content = raw_response["choices"][0]["message"]["content"]
            parsed = _parse_model_json(content)
            break
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code in {401, 403}:
                raise
            last_error = exc
        except (requests.RequestException, KeyError, json.JSONDecodeError, ValueError) as exc:
            last_error = exc

        if attempt < attempts - 1:
            time.sleep(1)
    else:
        if settings.deepseek_fallback_to_mock_on_error and last_error is not None:
            return fallback(last_error)
        if last_error is not None:
            raise last_error
        raise RuntimeError("DeepSeek classification failed without an exception")

    latency_ms = int((time.perf_counter() - started) * 1000)
    usage = raw_response.get("usage") or {}
    return {
        "classification": _validate_model_json(parsed),
        "raw_response": raw_response,
        "latency_ms": latency_ms,
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
        "mock_mode": False,
    }
