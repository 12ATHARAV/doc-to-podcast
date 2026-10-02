"""Pipeline orchestrator — manages the 5-agent workflow."""

from pathlib import Path
from loguru import logger

from app.agents.base_agent import PipelineState
from app.agents.analyst_agent import ContentAnalystAgent
from app.agents.outline_agent import OutlineArchitectAgent
from app.agents.parser_agent import DocumentParserAgent
from app.agents.reviewer_agent import QualityReviewerAgent
from app.agents.writer_agent import ScriptWriterAgent
from app.audio.processor import AudioProcessor
from app.config import settings
from app.exceptions import AgentReviewFailedError, PipelineError
from app.llm.gemini_provider import GeminiProvider
from app.llm.groq_provider import GroqProvider
from app.llm.provider import LLMProvider
from app.tts.tts_engine import TTSManager


class PipelineOrchestrator:
    """Orchestrates the full document-to-podcast pipeline.
    
    Manages the 5-agent sequential workflow with a review loop
    between the Script Writer and Quality Reviewer agents.
    """

    def __init__(
        self,
        progress_callback=None,
        gemini_api_key: str | None = None,
        groq_api_key: str | None = None
    ) -> None:
        # Initialize LLM provider
        self._gemini_api_key = gemini_api_key
        self._groq_api_key = groq_api_key
        self._llm = self._create_llm_provider()
        self._fallback_llm = self._create_fallback_provider()
        self._progress_callback = progress_callback

        # Initialize agents
        self._parser = DocumentParserAgent()
        self._analyst = ContentAnalystAgent(self._llm)
        self._outliner = OutlineArchitectAgent(self._llm)
        self._writer = ScriptWriterAgent(self._llm)
        self._reviewer = QualityReviewerAgent(self._llm)

        # Initialize TTS and audio
        self._tts_manager = TTSManager()
        self._audio_processor = AudioProcessor()

    def _create_llm_provider(self) -> LLMProvider:
        """Create the primary LLM provider."""
        gemini_key = self._gemini_api_key or settings.gemini_api_key
        groq_key = self._groq_api_key or settings.groq_api_key

        if settings.primary_llm == "groq" and groq_key:
            return GroqProvider(api_key=groq_key)
        if gemini_key:
            return GeminiProvider(api_key=gemini_key)
        raise PipelineError(
            "No LLM API key configured. Please provide Gemini or Groq API key in the UI."
        )

    def _create_fallback_provider(self) -> LLMProvider | None:
        """Create the fallback LLM provider."""
        gemini_key = self._gemini_api_key or settings.gemini_api_key
        groq_key = self._groq_api_key or settings.groq_api_key
        try:
            if settings.primary_llm == "gemini" and groq_key:
                return GroqProvider(api_key=groq_key)
            if settings.primary_llm == "groq" and gemini_key:
                return GeminiProvider(api_key=gemini_key)
        except Exception:
            pass
        return None

    async def update_progress(self, step: str, progress: float) -> None:
        """Call progress callback if defined."""
        logger.info(f"Pipeline Progress: {step} - {progress * 100:.0f}%")
        if self._progress_callback:
            try:
                await self._progress_callback(step, progress)
            except Exception as e:
                logger.error(f"Failed to call progress callback: {e}")

    async def run(self, file_bytes: bytes, filename: str) -> Path:
        """Run the full pipeline from document to podcast audio.
        
        Args:
            file_bytes: Raw uploaded file bytes.
            filename: Original filename.
            
        Returns:
            Path to the generated podcast MP3 file.
            
        Raises:
            PipelineError: If the pipeline fails.
        """
        state: PipelineState = {
            "raw_file": file_bytes,
            "filename": filename,
            "errors": [],
            "progress": 0.0,
            "current_step": "Initialization"
        }

        try:
            # 1. Parse Document
            await self.update_progress("Parsing Document", 0.05)
            state = await self._parser.run(state)
            
            # 2. Content Analysis
            await self.update_progress("Analyzing Content", 0.15)
            try:
                state = await self._analyst.run(state)
            except Exception as e:
                if self._fallback_llm:
                    logger.warning(f"Primary LLM failed, retrying analyst with fallback: {e}")
                    self._analyst.llm_provider = self._fallback_llm
                    state = await self._analyst.run(state)
                else:
                    raise

            # 3. Outline Episode
            await self.update_progress("Designing Outline", 0.30)
            try:
                state = await self._outliner.run(state)
            except Exception as e:
                if self._fallback_llm:
                    logger.warning(f"Primary LLM failed, retrying outline with fallback: {e}")
                    self._outliner.llm_provider = self._fallback_llm
                    state = await self._outliner.run(state)
                else:
                    raise

            # 4. Generate Script with Quality Review Loop
            await self.update_progress("Writing Script", 0.45)
            
            iterations = 0
            approved = False
            while not approved and iterations < settings.max_review_iterations:
                iterations += 1
                logger.info(f"Script generation iteration {iterations}/{settings.max_review_iterations}")
                
                try:
                    state = await self._writer.run(state)
                except Exception as e:
                    if self._fallback_llm:
                        logger.warning(f"Primary LLM failed, retrying writer with fallback: {e}")
                        self._writer.llm_provider = self._fallback_llm
                        state = await self._writer.run(state)
                    else:
                        raise

                await self.update_progress(f"Reviewing Script (Iteration {iterations})", 0.55)
                try:
                    state = await self._reviewer.run(state)
                except Exception as e:
                    if self._fallback_llm:
                        logger.warning(f"Primary LLM failed, retrying reviewer with fallback: {e}")
                        self._reviewer.llm_provider = self._fallback_llm
                        try:
                            state = await self._reviewer.run(state)
                        except Exception as e2:
                            logger.warning(f"Reviewer fallback also failed: {e2}. Skipping review.")
                            approved = True  # Skip review, proceed with draft
                            break
                    else:
                        logger.warning(f"Reviewer failed and no fallback available: {e}. Skipping review.")
                        approved = True  # Skip review, proceed with draft
                        break
                
                review = state.get("review_result")
                if review and review.approved:
                    approved = True
                    logger.info("Script approved by reviewer agent.")
                else:
                    issues = review.issues if review else []
                    logger.warning(f"Script rejected by reviewer. Issues: {issues}")

            if not approved:
                logger.warning(
                    f"Failed to produce a fully approved script after {settings.max_review_iterations} iterations. "
                    "Proceeding with the latest generated script draft."
                )

            # 5. Synthesize Voices
            await self.update_progress("Synthesizing Voices", 0.70)
            script = state.get("podcast_script")
            if not script:
                raise PipelineError("No script draft available for synthesis")

            audio_segments = await self._tts_manager.generate_audio_for_script(script)
            state["audio_segments"] = audio_segments

            # 6. Post-Process Audio
            await self.update_progress("Processing Audio", 0.85)
            output_path = self._audio_processor.process(audio_segments)
            state["final_audio"] = output_path

            await self.update_progress("Complete", 1.0)
            return output_path

        except Exception as e:
            logger.error(f"Pipeline run failed: {e}")
            raise PipelineError(f"Pipeline run failed: {e}") from e
