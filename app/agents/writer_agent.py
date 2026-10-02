"""Script Writer Agent — Agent 4 in the pipeline."""

from app.agents.base_agent import BaseAgent, PipelineState
from app.exceptions import AgentError
from app.llm.provider import LLMProvider
from app.models import PodcastScript


class ScriptWriterAgent(BaseAgent):
    """Writes the full two-person conversational podcast script.
    
    Creates natural dialogue between Alex (male) and Maya (female)
    with engagement techniques, SSML tags, and emotional markers.
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        super().__init__(
            name="ScriptWriterAgent",
            description="Write the full two-person podcast script",
            llm_provider=llm_provider,
        )
        self._system_prompt = self._load_prompt("writer")

    async def execute(self, state: PipelineState) -> PipelineState:
        """Write the podcast script."""
        outline = state.get("episode_outline")
        parsed = state.get("parsed_document")
        review = state.get("review_result")

        if not outline:
            raise AgentError(self.name, "No episode outline available")
        if not parsed:
            raise AgentError(self.name, "No parsed document available")
        if not self.llm_provider:
            raise AgentError(self.name, "No LLM provider configured")

        # Build user prompt with outline + source text
        revision_note = ""
        if review and not review.approved:
            revision_note = (
                f"\n\nPREVIOUS REVIEW FEEDBACK (please address these issues):\n"
                f"Issues: {'; '.join(review.issues)}\n"
                f"Suggestions: {'; '.join(review.suggestions)}\n"
                f"Hallucination flags: {'; '.join(review.hallucination_flags)}\n"
            )

        user_prompt = (
            f"EPISODE OUTLINE:\n"
            f"{outline.model_dump_json(indent=2)}\n\n"
            f"--- SOURCE DOCUMENT ---\n\n"
            f"{parsed.text[:500_000]}\n"  # Cap at ~500K chars for safety
            f"{revision_note}"
        )

        self._logger.info(
            f"Writing script for '{outline.title}' "
            f"({len(outline.segments)} segments)"
        )

        script = await self.llm_provider.generate(
            system_prompt=self._system_prompt,
            user_prompt=user_prompt,
            response_schema=PodcastScript,
            temperature=0.8,
        )

        if not isinstance(script, PodcastScript):
            raise AgentError(self.name, "Failed to parse podcast script")

        # Update computed fields
        script.total_lines = len(script.lines)
        # Rough estimate: ~150 words per minute speech, ~7 words per line avg
        script.estimated_duration_minutes = round(
            sum(len(line.text.split()) for line in script.lines) / 150, 1
        )

        state["podcast_script"] = script
        state["progress"] = 0.60

        self._logger.info(
            f"Script complete: {script.total_lines} lines, "
            f"~{script.estimated_duration_minutes} min"
        )
        return state
