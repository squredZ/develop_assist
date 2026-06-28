"""LLM structured output validation with retry loop."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class ValidationExhaustedError(Exception):
    """Raised when LLM output validation retries are exhausted."""


def validate_and_retry(
    raw_output: str,
    model: type[BaseModel],
    max_retries: int,
    llm_call: Callable[[str], str] | None,
) -> BaseModel:
    """Validate raw LLM output against a Pydantic model. Retry with error feedback.

    On failure, calls `llm_call(error_message)` to get a corrected output.
    Raises ValidationExhaustedError if max_retries is reached.
    """
    last_error: str | None = None
    output = raw_output

    for attempt in range(max_retries + 1):
        try:
            data = json.loads(output)
            result = model.model_validate(data)
            logger.info("validation passed on attempt %d/%d", attempt + 1, max_retries + 1)
            return result
        except json.JSONDecodeError as e:
            last_error = f"Invalid JSON: {e}"
            logger.warning(
                "validation attempt %d/%d: JSON decode error — %s", attempt + 1, max_retries + 1, e
            )
        except ValidationError as e:
            last_error = f"Validation error: {e}"
            logger.warning(
                "validation attempt %d/%d: pydantic error — %s", attempt + 1, max_retries + 1, e
            )

        if attempt < max_retries and llm_call is not None:
            logger.info("retrying with LLM error feedback...")
            output = llm_call(last_error)
        elif attempt < max_retries:
            break

    logger.error("validation exhausted after %d retries — last error: %s", max_retries, last_error)
    raise ValidationExhaustedError(
        f"LLM output validation failed after {max_retries} retries. Last error: {last_error}"
    )
