"""Google Gemini LLM provider implementation."""

import json

from google import genai
from google.genai import types
from loguru import logger
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.exceptions import LLMContextTooLargeError, LLMError, LLMRateLimitError
from app.llm.provider import LLMProvider


class GeminiProvider(LLMProvider):
    """Google Gemini 2.5 Flash provider with 1M token context window."""

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or settings.gemini_api_key
        if not key:
            raise LLMError("Gemini API key is required. Please provide it in the UI or configuration.")
        self._client = genai.Client(api_key=key)
        self._model = settings.gemini_model
        logger.info(f"Initialized GeminiProvider with model: {self._model}")

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=3, min=5, max=90),
        retry=retry_if_exception_type((LLMRateLimitError,)),
        reraise=True,
    )
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.7,
    ) -> str | BaseModel:
        """Generate a response using Google Gemini."""
        try:
            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
            )

            if response_schema is not None:
                config.response_mime_type = "application/json"
                config.response_schema = response_schema

            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=user_prompt,
                config=config,
            )

            raw_text = response.text
            if raw_text is None:
                raise LLMError("Gemini returned an empty response.")

            if response_schema is not None:
                return response_schema.model_validate_json(raw_text)

            return raw_text

        except Exception as e:
            error_msg = str(e).lower()
            # Treat 503/UNAVAILABLE, rate limits, and quota errors as retryable
            if any(kw in error_msg for kw in ("rate", "quota", "429", "503", "unavailable", "overloaded", "high demand")):
                logger.warning(f"Gemini retryable error (will retry): {e}")
                raise LLMRateLimitError(str(e)) from e
            if "too large" in error_msg or "context" in error_msg:
                raise LLMContextTooLargeError(str(e)) from e
            if isinstance(e, (LLMError, LLMRateLimitError, LLMContextTooLargeError)):
                raise
            logger.error(f"Gemini generation failed: {e}")
            raise LLMError(f"Gemini generation failed: {e}") from e

    def count_tokens(self, text: str) -> int:
        """Count tokens using Gemini's tokenizer."""
        try:
            response = self._client.models.count_tokens(
                model=self._model,
                contents=text,
            )
            return response.total_tokens
        except Exception:
            # Fallback: rough estimate (1 token ≈ 4 chars for English)
            return len(text) // 4

    @property
    def max_context_tokens(self) -> int:
        return 1_000_000

    @property
    def name(self) -> str:
        return f"Gemini ({self._model})"
