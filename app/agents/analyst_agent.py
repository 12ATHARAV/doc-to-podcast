"""Content Analyst Agent — Agent 2 in the pipeline."""

from app.agents.base_agent import BaseAgent, PipelineState
from app.exceptions import AgentError
from app.llm.provider import LLMProvider
from app.models import ContentAnalysis


class ContentAnalystAgent(BaseAgent):
    """Analyzes document content to extract podcast-worthy material.
    
    Identifies key themes, fascinating facts, complex concepts,
    quotable moments, debate points, and human stories.
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        super().__init__(
            name="ContentAnalystAgent",
            description="Deep analysis of document content for podcast potential",
            llm_provider=llm_provider,
        )
        self._system_prompt = self._load_prompt("analyst")

    async def execute(self, state: PipelineState) -> PipelineState:
        """Analyze the parsed document content."""
        parsed = state.get("parsed_document")
        if not parsed:
            raise AgentError(self.name, "No parsed document available")

        if not self.llm_provider:
            raise AgentError(self.name, "No LLM provider configured")

        user_prompt = (
            f"Document Title: {parsed.metadata.title}\n"
            f"Word Count: {parsed.metadata.word_count}\n"
            f"Sections: {', '.join(parsed.metadata.sections[:20])}\n\n"
            f"--- DOCUMENT CONTENT ---\n\n"
            f"{parsed.text}"
        )

        self._logger.info(
            f"Analyzing document ({parsed.token_count} tokens) "
            f"with {self.llm_provider.name}"
        )

        analysis = await self.llm_provider.generate(
            system_prompt=self._system_prompt,
            user_prompt=user_prompt,
            response_schema=ContentAnalysis,
            temperature=0.4,
        )

        if not isinstance(analysis, ContentAnalysis):
            raise AgentError(self.name, "Failed to parse content analysis")

        state["content_analysis"] = analysis
        state["progress"] = 0.30

        self._logger.info(
            f"Analysis complete: {len(analysis.themes)} themes, "
            f"{len(analysis.fascinating_facts)} facts, "
            f"engagement score: {analysis.overall_engagement_score}"
        )
        return state
