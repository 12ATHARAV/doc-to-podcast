"""Groq LLM provider implementation."""

import json

from groq import AsyncGroq
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


class GroqProvider(LLMProvider):
    """Groq provider with Llama 3.3 70B and 128K context."""

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or settings.groq_api_key
        if not key:
            raise LLMError("Groq API key is required. Please provide it in the UI or configuration.")
        self._client = AsyncGroq(api_key=key)
        self._model = settings.groq_model
        logger.info(f"Initialized GroqProvider with model: {self._model}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type(LLMRateLimitError),
        reraise=True,
    )
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.7,
    ) -> str | BaseModel:
        """Generate a response using Groq."""
        try:
            # Enforce JSON formatting rules and inject target schema structure
            if response_schema is not None:
                schema_json = json.dumps(response_schema.model_json_schema(), indent=2)
                system_prompt += (
                    f"\n\nCRITICAL: The output MUST be a valid JSON object matching the following JSON Schema:\n{schema_json}"
                    "\nEnsure all required fields are present and use the exact keys specified in the schema."
                )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            kwargs: dict = {
                "model": self._model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 8192,
            }

            if response_schema is not None:
                kwargs["response_format"] = {"type": "json_object"}

            response = await self._client.chat.completions.create(**kwargs)
            raw_text = response.choices[0].message.content

            if raw_text is None:
                raise LLMError("Groq returned an empty response.")

            if response_schema is not None:
                return response_schema.model_validate_json(raw_text)

            return raw_text

        except Exception as e:
            error_msg = str(e).lower()
            if "rate" in error_msg or "429" in error_msg:
                logger.warning(f"Groq rate limit hit: {e}")
                raise LLMRateLimitError(str(e)) from e
            if "too large" in error_msg or "context" in error_msg:
                raise LLMContextTooLargeError(str(e)) from e
            if isinstance(e, (LLMError, LLMRateLimitError, LLMContextTooLargeError)):
                raise
            logger.error(f"Groq generation failed: {e}")
            raise LLMError(f"Groq generation failed: {e}") from e

    def count_tokens(self, text: str) -> int:
        """Rough token count estimate."""
        return len(text) // 4

    @property
    def max_context_tokens(self) -> int:
        return 128_000

    @property
    def name(self) -> str:
        return f"Groq ({self._model})"
