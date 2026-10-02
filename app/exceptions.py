"""Custom exceptions for the Doc-to-Podcast pipeline."""


class DocToPodcastError(Exception):
    """Base exception for all Doc-to-Podcast errors."""


class DocumentParsingError(DocToPodcastError):
    """Raised when document parsing fails."""


class LLMError(DocToPodcastError):
    """Base exception for LLM-related errors."""


class LLMRateLimitError(LLMError):
    """Raised when LLM API rate limit is exceeded."""


class LLMContextTooLargeError(LLMError):
    """Raised when input exceeds the LLM's context window."""


class TTSError(DocToPodcastError):
    """Base exception for TTS-related errors."""


class TTSSynthesisError(TTSError):
    """Raised when TTS synthesis fails for a specific line."""


class AudioProcessingError(DocToPodcastError):
    """Raised when audio post-processing fails."""


class AgentError(DocToPodcastError):
    """Raised when an agent fails during execution."""

    def __init__(self, agent_name: str, message: str):
        self.agent_name = agent_name
        super().__init__(f"[{agent_name}] {message}")


class AgentReviewFailedError(AgentError):
    """Raised when the quality reviewer rejects the script after max retries."""


class PipelineError(DocToPodcastError):
    """Raised when the overall pipeline fails."""
