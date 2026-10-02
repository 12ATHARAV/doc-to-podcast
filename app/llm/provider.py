"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class LLMProvider(ABC):
    """Abstract interface for LLM providers.
    
    All LLM providers (Gemini, Groq, Ollama) must implement this
    interface to be used interchangeably in the agent pipeline.
    """

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.7,
    ) -> str | BaseModel:
        """Generate a response from the LLM.
        
        Args:
            system_prompt: System-level instructions for the LLM.
            user_prompt: The user's input/question.
            response_schema: Optional Pydantic model for structured output.
            temperature: Sampling temperature (0.0-1.0).
            
        Returns:
            Raw string response, or a parsed Pydantic model if
            response_schema is provided.
            
        Raises:
            LLMError: If generation fails.
            LLMRateLimitError: If rate limit is exceeded.
            LLMContextTooLargeError: If input exceeds context window.
        """
        ...

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in the given text."""
        ...

    @property
    @abstractmethod
    def max_context_tokens(self) -> int:
        """Maximum number of tokens this provider supports."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this provider."""
        ...
