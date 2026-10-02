"""Base agent class for the Doc-to-Podcast pipeline."""

import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TypedDict

from loguru import logger

from app.exceptions import AgentError
from app.llm.provider import LLMProvider
from app.models import (
    ContentAnalysis,
    EpisodeOutline,
    ParsedDocument,
    PodcastScript,
    ReviewResult,
)


class PipelineState(TypedDict, total=False):
    """Shared state passed through the agent pipeline."""
    raw_file: bytes
    filename: str
    parsed_document: ParsedDocument | None
    content_analysis: ContentAnalysis | None
    episode_outline: EpisodeOutline | None
    podcast_script: PodcastScript | None
    review_result: ReviewResult | None
    audio_segments: list[Path] | None
    final_audio: Path | None
    errors: list[str]
    progress: float
    current_step: str


class BaseAgent(ABC):
    """Abstract base class for all pipeline agents.
    
    Provides common functionality: logging, timing, error wrapping.
    Subclasses must implement the execute() method.
    """

    def __init__(
        self,
        name: str,
        description: str,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.llm_provider = llm_provider
        self._logger = logger.bind(agent=name)

    async def run(self, state: PipelineState) -> PipelineState:
        """Execute the agent with logging and error handling."""
        self._logger.info(f"Starting execution")
        state["current_step"] = self.name
        start_time = time.monotonic()

        try:
            state = await self.execute(state)
            elapsed = time.monotonic() - start_time
            self._logger.info(f"Completed in {elapsed:.2f}s")
        except AgentError:
            raise
        except Exception as e:
            elapsed = time.monotonic() - start_time
            self._logger.error(f"Failed after {elapsed:.2f}s: {e}")
            state.setdefault("errors", []).append(f"[{self.name}] {e}")
            raise AgentError(self.name, str(e)) from e

        return state

    @abstractmethod
    async def execute(self, state: PipelineState) -> PipelineState:
        """Execute the agent's core logic.
        
        Args:
            state: The current pipeline state.
            
        Returns:
            Updated pipeline state.
        """
        ...

    def _load_prompt(self, prompt_name: str) -> str:
        """Load a system prompt from the prompts directory."""
        prompt_path = Path(__file__).parent.parent / "llm" / "prompts" / f"{prompt_name}.txt"
        return prompt_path.read_text(encoding="utf-8")
