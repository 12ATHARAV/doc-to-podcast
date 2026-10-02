"""Quality Reviewer Agent — Agent 5 in the pipeline."""

from app.agents.base_agent import BaseAgent, PipelineState
from app.exceptions import AgentError
from app.llm.provider import LLMProvider
from app.models import ReviewResult


class QualityReviewerAgent(BaseAgent):
    """Fact-checks, verifies quality, and approves/rejects scripts.
    
    Cross-references every claim against the source document,
    scores quality across 4 dimensions, and flags hallucinations.
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        super().__init__(
            name="QualityReviewerAgent",
            description="Fact-check and review script quality",
            llm_provider=llm_provider,
        )
        self._system_prompt = self._load_prompt("reviewer")

    async def execute(self, state: PipelineState) -> PipelineState:
        """Review the podcast script for quality and accuracy."""
        script = state.get("podcast_script")
        parsed = state.get("parsed_document")

        if not script:
            raise AgentError(self.name, "No podcast script available")
        if not parsed:
            raise AgentError(self.name, "No parsed document available")
        if not self.llm_provider:
            raise AgentError(self.name, "No LLM provider configured")

        user_prompt = (
            f"PODCAST SCRIPT TO REVIEW:\n"
            f"{script.model_dump_json(indent=2)}\n\n"
            f"--- SOURCE DOCUMENT ---\n\n"
            f"{parsed.text[:500_000]}\n"
        )

        self._logger.info(
            f"Reviewing script ({script.total_lines} lines)"
        )

        review = await self.llm_provider.generate(
            system_prompt=self._system_prompt,
            user_prompt=user_prompt,
            response_schema=ReviewResult,
            temperature=0.3,
        )

        if not isinstance(review, ReviewResult):
            raise AgentError(self.name, "Failed to parse review result")

        state["review_result"] = review
        state["progress"] = 0.70

        scores = review.quality_scores
        self._logger.info(
            f"Review complete — Approved: {review.approved} | "
            f"Accuracy: {scores.factual_accuracy:.1f}, "
            f"Natural: {scores.naturalness:.1f}, "
            f"Engage: {scores.engagement:.1f}, "
            f"Coherence: {scores.coherence:.1f} | "
            f"Hallucinations: {len(review.hallucination_flags)}"
        )
        return state
