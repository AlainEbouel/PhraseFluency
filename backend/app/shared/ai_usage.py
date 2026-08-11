import logging

from sqlalchemy.orm import Session

from app.shared.models import AIOperation, AIUsage

logger = logging.getLogger(__name__)

# USD per 1,000 tokens. Approximate reference pricing; update when OpenAI
# pricing changes or when the configured model changes.
#
# tts-1 is actually billed per 1,000 characters, not tokens — input_tokens
# is used to carry a character count for that model as a pragmatic reuse
# of this same table rather than a separate cost model. whisper-1 (STT)
# is billed per audio minute, which doesn't fit this table at all; its
# cost is left at the zero-entry fallback below (a known approximation
# gap, acceptable for docs' "measurable, not exact" AI usage tracking).
_PRICING_PER_1K_TOKENS: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.0025, 0.01),
    "tts-1": (0.015, 0.0),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = _PRICING_PER_1K_TOKENS.get(model)
    if prices is None:
        logger.warning("No pricing entry for model %s; recording zero estimated cost", model)
        return 0.0
    input_price, output_price = prices
    return (input_tokens / 1000) * input_price + (output_tokens / 1000) * output_price


def record_ai_usage(
    db: Session,
    *,
    operation: AIOperation,
    model: str,
    input_tokens: int,
    output_tokens: int,
    user_id=None,
) -> AIUsage:
    usage = AIUsage(
        user_id=user_id,
        operation=operation,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost=estimate_cost(model, input_tokens, output_tokens),
    )
    db.add(usage)
    return usage
