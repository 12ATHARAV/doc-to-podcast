import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.parsers.document_parser import DocumentParser
from app.llm.gemini_provider import GeminiProvider
from app.llm.groq_provider import GroqProvider
from app.exceptions import LLMError
from app.agents.orchestrator import PipelineOrchestrator

client = TestClient(app)

def test_document_parser_txt():
    parser = DocumentParser()
    parsed = parser.parse(b"Hello world. This is a parser test.", "test.txt")
    assert parsed.source_file == "test.txt"
    assert parsed.token_count > 0
    assert "Hello world" in parsed.text
    assert parsed.metadata.word_count == 7

def test_document_parser_html():
    parser = DocumentParser()
    html_content = b"<html><body><h1>Title</h1><p>Body text here.</p></body></html>"
    parsed = parser.parse(html_content, "test.html")
    assert "Title" in parsed.text
    assert "Body text here." in parsed.text

def test_llm_provider_missing_key():
    # If key is missing and not in environment, it should raise LLMError
    with patch("app.llm.gemini_provider.settings.gemini_api_key", ""):
        with pytest.raises(LLMError):
            GeminiProvider(api_key=None)

def test_llm_provider_with_key():
    with patch("app.llm.gemini_provider.genai.Client") as mock_client:
        provider = GeminiProvider(api_key="test_key_gemini")
        assert provider is not None
        mock_client.assert_called_once_with(api_key="test_key_gemini")

def test_groq_provider_with_key():
    with patch("app.llm.groq_provider.AsyncGroq") as mock_client:
        provider = GroqProvider(api_key="test_key_groq")
        assert provider is not None
        mock_client.assert_called_once_with(api_key="test_key_groq")

def test_upload_route_requires_file():
    response = client.post("/api/upload")
    assert response.status_code == 422

@patch("app.api.routes.run_podcast_pipeline")
def test_upload_route_success(mock_run_pipeline):
    files = {"file": ("test.txt", b"Factual source document text here.", "text/plain")}
    data = {
        "gemini_api_key": "user_gemini_key",
        "groq_api_key": "user_groq_key"
    }
    response = client.post("/api/upload", files=files, data=data)
    assert response.status_code == 200
    json_data = response.json()
    assert "id" in json_data
    assert json_data["status"] == "queued"
    assert json_data["source_filename"] == "test.txt"
    
    # Verify the background task is queued with correct arguments
    mock_run_pipeline.assert_called_once()
    called_args, called_kwargs = mock_run_pipeline.call_args
    assert called_kwargs["gemini_api_key"] == "user_gemini_key"
    assert called_kwargs["groq_api_key"] == "user_groq_key"


@pytest.mark.asyncio
async def test_orchestrator_reviewer_rejection_proceeds_with_draft():
    # Test that if the reviewer rejects the script (approved=False), the pipeline proceeds to synthesis and succeeds
    from app.models import ReviewResult, QualityScores, PodcastScript, ParsedDocument, DocumentMetadata, EpisodeOutline
    from pathlib import Path
    
    orchestrator = PipelineOrchestrator(gemini_api_key="test_gemini")
    
    mock_parsed = ParsedDocument(text="Source text", source_file="doc.txt", metadata=DocumentMetadata())
    mock_script = PodcastScript(lines=[])
    
    mock_review = ReviewResult(
        approved=False,
        quality_scores=QualityScores(factual_accuracy=5.0, naturalness=5.0, engagement=5.0, coherence=5.0),
        issues=["Too formal"],
        suggestions=["Make it more conversational"]
    )
    
    async def mock_async_run(state):
        state["parsed_document"] = mock_parsed
        state["content_analysis"] = MagicMock()
        state["episode_outline"] = EpisodeOutline(title="Test", estimated_duration_minutes=5, segments=[])
        state["podcast_script"] = mock_script
        state["review_result"] = mock_review
        return state

    orchestrator._parser.run = mock_async_run
    orchestrator._analyst.run = mock_async_run
    orchestrator._outliner.run = mock_async_run
    orchestrator._writer.run = mock_async_run
    orchestrator._reviewer.run = mock_async_run
    
    async def mock_tts(script):
        return []
    orchestrator._tts_manager.generate_audio_for_script = mock_tts
    orchestrator._audio_processor.process = MagicMock(return_value=Path("output/test_output.mp3"))
    
    output_path = await orchestrator.run(b"test data", "doc.txt")
    assert output_path == Path("output/test_output.mp3")


@pytest.mark.asyncio
async def test_orchestrator_reviewer_exception_proceeds_with_draft():
    # Test that if the reviewer completely crashes (e.g. raises an exception), the pipeline proceeds to synthesis and succeeds
    from app.models import ParsedDocument, DocumentMetadata, EpisodeOutline, PodcastScript
    from pathlib import Path
    
    orchestrator = PipelineOrchestrator(gemini_api_key="test_gemini")
    
    mock_parsed = ParsedDocument(text="Source text", source_file="doc.txt", metadata=DocumentMetadata())
    mock_script = PodcastScript(lines=[])
    
    async def mock_async_run(state):
        return state

    async def mock_reviewer_crash(state):
        raise Exception("Reviewer crashed")

    orchestrator._parser.run = mock_async_run
    orchestrator._analyst.run = mock_async_run
    orchestrator._outliner.run = mock_async_run
    
    async def mock_writer_run(state):
        state["podcast_script"] = mock_script
        return state
    orchestrator._writer.run = mock_writer_run
    orchestrator._reviewer.run = mock_reviewer_crash
    
    async def mock_tts(script):
        return []
    orchestrator._tts_manager.generate_audio_for_script = mock_tts
    orchestrator._audio_processor.process = MagicMock(return_value=Path("output/test_output.mp3"))
    
    # Should complete without raising
    output_path = await orchestrator.run(b"test data", "doc.txt")
    assert output_path == Path("output/test_output.mp3")

