"""LLM structured output validation with retry loop."""

from __future__ import annotations

import json
from collections.abc import Callable

from pydantic import BaseModel, ValidationError


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
            return model.model_validate(data)
        except json.JSONDecodeError as e:
            last_error = f"Invalid JSON: {e}"
        except ValidationError as e:
            last_error = f"Validation error: {e}"

        if attempt < max_retries and llm_call is not None:
            output = llm_call(last_error)
        elif attempt < max_retries:
            break

    raise ValidationExhaustedError(
        f"LLM output validation failed after {max_retries} retries. Last error: {last_error}"
    )
