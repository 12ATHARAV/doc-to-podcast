"""Outline Architect Agent — Agent 3 in the pipeline."""

from app.agents.base_agent import BaseAgent, PipelineState
from app.exceptions import AgentError
from app.llm.provider import LLMProvider
from app.models import ContentAnalysis, EpisodeOutline


class OutlineArchitectAgent(BaseAgent):
    """Designs the podcast episode structure for maximum engagement.
    
    Creates a detailed episode outline with segments, pacing,
    energy levels, and transition hooks.
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        super().__init__(
            name="OutlineArchitectAgent",
            description="Design podcast episode structure for maximum engagement",
            llm_provider=llm_provider,
        )
        self._system_prompt = self._load_prompt("outline")

    async def execute(self, state: PipelineState) -> PipelineState:
        """Design the episode outline."""
        analysis = state.get("content_analysis")
        if not analysis:
            raise AgentError(self.name, "No content analysis available")

        if not self.llm_provider:
            raise AgentError(self.name, "No LLM provider configured")

        user_prompt = (
            f"Content Analysis:\n"
            f"{analysis.model_dump_json(indent=2)}\n\n"
            f"Create a detailed podcast episode outline based on this analysis."
        )

        self._logger.info("Designing episode outline")

        outline = await self.llm_provider.generate(
            system_prompt=self._system_prompt,
            user_prompt=user_prompt,
            response_schema=EpisodeOutline,
            temperature=0.6,
        )

        if not isinstance(outline, EpisodeOutline):
            raise AgentError(self.name, "Failed to parse episode outline")

        state["episode_outline"] = outline
        state["progress"] = 0.45

        self._logger.info(
            f"Outline complete: '{outline.title}' — "
            f"{len(outline.segments)} segments, "
            f"~{outline.estimated_duration_minutes} min"
        )
        return state
