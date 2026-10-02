"""Pydantic models for the Doc-to-Podcast pipeline.

Defines all data structures passed between agents, including
document metadata, content analysis, episode outlines, dialogue
scripts, review results, and job status tracking.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


# --- Enums ---

class EnergyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CLIMAX = "climax"


class Emotion(str, Enum):
    EXCITED = "excited"
    CURIOUS = "curious"
    THOUGHTFUL = "thoughtful"
    AMUSED = "amused"
    SURPRISED = "surprised"
    SERIOUS = "serious"


class PodcastLength(str, Enum):
    SHORT = "short"        # 5-10 min
    MEDIUM = "medium"      # 10-25 min
    LONG = "long"          # 25-60 min
    DEEP_DIVE = "deep-dive" # 60+ min


class JobStatusEnum(str, Enum):
    QUEUED = "queued"
    PARSING = "parsing"
    ANALYZING = "analyzing"
    OUTLINING = "outlining"
    WRITING = "writing"
    REVIEWING = "reviewing"
    SYNTHESIZING = "synthesizing"
    PROCESSING_AUDIO = "processing_audio"
    COMPLETED = "completed"
    FAILED = "failed"


# --- Document Models ---

class DocumentMetadata(BaseModel):
    """Metadata extracted from the uploaded document."""
    title: str = "Untitled Document"
    author: str = "Unknown"
    page_count: int = 0
    word_count: int = 0
    sections: list[str] = Field(default_factory=list)
    estimated_read_time_minutes: int = 0


class ParsedDocument(BaseModel):
    """Result of document parsing — clean text with metadata."""
    text: str
    metadata: DocumentMetadata
    source_file: str
    token_count: int = 0


# --- Content Analysis Models ---

class Theme(BaseModel):
    """A key theme identified in the document."""
    name: str
    description: str
    source_refs: list[str] = Field(default_factory=list)
    engagement_score: float = Field(ge=1.0, le=10.0)


class Fact(BaseModel):
    """A fascinating fact extracted from the document."""
    content: str
    source_ref: str = ""
    surprise_factor: float = Field(ge=1.0, le=10.0, default=5.0)


class Concept(BaseModel):
    """A complex concept that needs simplification."""
    name: str
    explanation: str
    analogy_suggestion: str = ""
    complexity_level: int = Field(ge=1, le=5, default=3)


class Quote(BaseModel):
    """A quotable moment from the document."""
    text: str
    attribution: str = ""
    context: str = ""


class DebatePoint(BaseModel):
    """A point where reasonable disagreement exists."""
    topic: str
    perspective_a: str
    perspective_b: str


class Story(BaseModel):
    """A human story or case study from the document."""
    title: str
    summary: str
    source_ref: str = ""


class ContentAnalysis(BaseModel):
    """Complete content analysis output from the Analyst Agent."""
    themes: list[Theme] = Field(default_factory=list)
    fascinating_facts: list[Fact] = Field(default_factory=list)
    complex_concepts: list[Concept] = Field(default_factory=list)
    quotable_moments: list[Quote] = Field(default_factory=list)
    debate_points: list[DebatePoint] = Field(default_factory=list)
    human_stories: list[Story] = Field(default_factory=list)
    overall_engagement_score: float = Field(ge=1.0, le=10.0, default=5.0)
    recommended_length: PodcastLength = PodcastLength.MEDIUM


# --- Episode Outline Models ---

class Segment(BaseModel):
    """A single segment of the podcast episode."""
    id: int
    title: str
    description: str
    topics: list[str] = Field(default_factory=list)
    engagement_technique: str = ""
    estimated_duration_seconds: int = 180
    energy_level: EnergyLevel = EnergyLevel.MEDIUM
    transition_hook: str = ""


class EpisodeOutline(BaseModel):
    """Complete episode outline from the Outline Architect Agent."""
    title: str
    estimated_duration_minutes: int
    segments: list[Segment] = Field(default_factory=list)


# --- Script Models ---

class DialogueLine(BaseModel):
    """A single line of dialogue in the podcast script."""
    speaker: Literal["ALEX", "MAYA"]
    text: str
    emotion: Emotion = Emotion.CURIOUS
    segment_id: int = 0


class PodcastScript(BaseModel):
    """Complete podcast script from the Script Writer Agent."""
    lines: list[DialogueLine] = Field(default_factory=list)
    total_lines: int = 0
    estimated_duration_minutes: float = 0.0


# --- Review Models ---

class QualityScores(BaseModel):
    """Quality scores from the Quality Reviewer Agent."""
    factual_accuracy: float = Field(ge=0.0, le=10.0)
    naturalness: float = Field(ge=0.0, le=10.0)
    engagement: float = Field(ge=0.0, le=10.0)
    coherence: float = Field(ge=0.0, le=10.0)

    @property
    def min_score(self) -> float:
        return min(
            self.factual_accuracy,
            self.naturalness,
            self.engagement,
            self.coherence,
        )


class ReviewResult(BaseModel):
    """Review result from the Quality Reviewer Agent."""
    approved: bool = False
    quality_scores: QualityScores
    hallucination_flags: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


# --- Job Tracking ---

class JobStatus(BaseModel):
    """Tracks the status of a podcast generation job."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatusEnum = JobStatusEnum.QUEUED
    progress_pct: float = 0.0
    current_step: str = "Queued"
    error_message: str | None = None
    output_file: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    source_filename: str = ""
    episode_title: str | None = None
