"""Document Parser Agent — Agent 1 in the pipeline."""

from loguru import logger

from app.agents.base_agent import BaseAgent, PipelineState
from app.exceptions import DocumentParsingError
from app.parsers.document_parser import DocumentParser


class DocumentParserAgent(BaseAgent):
    """Extracts and structures text from uploaded documents.
    
    This agent uses deterministic parsing (no LLM) to convert
    documents of various formats into clean, structured text.
    """

    def __init__(self) -> None:
        super().__init__(
            name="DocumentParserAgent",
            description="Extract and structure text from uploaded documents",
            llm_provider=None,
        )
        self._parser = DocumentParser()

    async def execute(self, state: PipelineState) -> PipelineState:
        """Parse the uploaded document."""
        raw_file = state.get("raw_file")
        filename = state.get("filename", "unknown")

        if not raw_file:
            raise DocumentParsingError("No file data provided")

        parsed = self._parser.parse(raw_file, filename)
        state["parsed_document"] = parsed
        state["progress"] = 0.15

        self._logger.info(
            f"Parsed '{filename}': {parsed.metadata.word_count} words, "
            f"~{parsed.token_count} tokens"
        )
        return state
