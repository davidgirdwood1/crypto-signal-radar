import json

PROMPT_VERSION = "v1"

CLASSIFICATIONS = [
    "Bullish Momentum",
    "Bearish Momentum",
    "Hype / Meme Pump",
    "Scam Risk",
    "Liquidity Risk",
    "Regulatory Risk",
    "Exchange / Listing Signal",
    "Social / Narrative Signal",
    "Noise / Ignore",
]

SENTIMENTS = ["bullish", "bearish", "neutral", "risky", "unknown"]

SYSTEM_PROMPT = """You are an AI crypto event triage assistant for a localhost-only educational demo.
This is not financial advice. Classify crypto and meme coin events for educational/demo purposes only.
Be skeptical of boosted meme coins, incomplete token profiles, vague narratives, and hype-heavy signals.
Higher risk_score means more caution. Return strict JSON only. No markdown. No prose outside JSON."""


def user_prompt(event: dict) -> str:
    compact = {
        "source": event.get("source"),
        "source_event_type": event.get("source_event_type"),
        "external_id": event.get("external_id"),
        "chain_id": event.get("chain_id"),
        "token_address": event.get("token_address"),
        "coin_id": event.get("coin_id"),
        "symbol": event.get("symbol"),
        "name": event.get("name"),
        "url": event.get("url"),
        "description": event.get("description"),
        "market_cap_rank": event.get("market_cap_rank"),
        "observed_at": event.get("observed_at"),
    }
    return f"""Classify this event using one classification from {CLASSIFICATIONS} and one sentiment from {SENTIMENTS}.
Return JSON with exactly these keys:
classification, sentiment, risk_score, confidence, summary, reasoning, suggested_action, affected_assets.
risk_score must be an integer from 0 to 100. confidence must be a number from 0 to 1.

Event:
{json.dumps(compact, ensure_ascii=True, sort_keys=True)}"""
