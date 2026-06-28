# tests/test_llm_validator.py
from __future__ import annotations

import pytest
from pydantic import BaseModel, Field
from hilog_agent.llm.validator import validate_and_retry, ValidationExhaustedError


class SampleOutput(BaseModel):
    answer: str
    confidence: int = Field(ge=0, le=100)


class TestValidator:
    def test_valid_output_passes(self):
        result = validate_and_retry(
            raw_output='{"answer": "hello", "confidence": 80}',
            model=SampleOutput,
            max_retries=3,
            llm_call=None,
        )
        assert result.answer == "hello"
        assert result.confidence == 80

    def test_invalid_json_retries(self):
        call_count = 0

        def fake_llm(error_msg: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return '{"answer": "ok", "confidence": 50}'
            return '{"answer": "fallback", "confidence": 0}'

        result = validate_and_retry(
            raw_output="not valid json{{{",
            model=SampleOutput,
            max_retries=2,
            llm_call=lambda err: fake_llm(err),
        )
        assert result.answer == "ok"

    def test_exhausted_retries_raises(self):
        with pytest.raises(ValidationExhaustedError):
            validate_and_retry(
                raw_output="invalid {{{",
                model=SampleOutput,
                max_retries=0,
                llm_call=None,
            )
