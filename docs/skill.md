# 🛠️ System Skills Specifications: Doc-to-Podcast

This document outlines the core functional skills utilized by agents and engines across the Doc-to-Podcast application workflow.

---

## 📂 Core Skills Registry

### 1. Document Parsing (`app/parsers/document_parser.py`)
*   **Description:** Converts binary files (PDFs, Word docs, Presentations) or raw text payloads into normalized, clean plaintext strings.
*   **Prerequisites:** External packages: `markitdown`, `PyMuPDF` (fitz), `python-docx`, `BeautifulSoup`.
*   **Input:** File byte buffer and filename.
*   **Output:** `ParsedDocument` object.
*   **Key Pipeline Actions:**
    1.  File format detection based on file extension.
    2.  Attempts Microsoft MarkItDown extraction.
    3.  Applies format-specific fallback parsers if primary parser returns None or raises an error.
    4.  Strips consecutive whitespace characters, cleans formatting artifacts, and normalizes line endings.
    5.  Performs regex section detection (identifying headers).

### 2. Content Analysis (`app/agents/analyst_agent.py`)
*   **Description:** Distills document content to identify key themes, stories, quotes, and debate topics.
*   **Prerequisites:** LLM provider connectivity.
*   **Input:** `ParsedDocument` text and metadata.
*   **Output:** JSON schema representing theme elements and engagement indices.

### 3. Podcast Outline Design (`app/agents/outline_agent.py`)
*   **Description:** Builds segment timelines and schedules hooks, act segments, pacing intervals, and callbacks.
*   **Prerequisites:** Structured `ContentAnalysis` schema.
*   **Input:** Theme outputs and recommended duration.
*   **Output:** Segment metadata sequence.

### 4. Dialog Scriptwriting (`app/agents/writer_agent.py`)
*   **Description:** Generates natural dialogue turns including contractions, disfluencies, filler words, interruptions, and emotive markers.
*   **Prerequisites:** Structured Outline and full Parsed Document context.
*   **Input:** Outline schema + Document Text + optional previous reviewer feedbacks.
*   **Output:** Array of dialogue turns.

### 5. Fact Verification & Review (`app/agents/reviewer_agent.py`)
*   **Description:** Compares generated script statements against the original document block to flag errors and evaluate natural conversation scores.
*   **Prerequisites:** Complete Script + Parsed Document context.
*   **Input:** Completed script + original text.
*   **Output:** `ReviewResult` with metrics and revision comments.

### 6. Speech Synthesis (`app/tts/tts_engine.py`)
*   **Description:** Translates dialogue text into MP3 clips using neural voice profiles.
*   **Prerequisites:** `edge-tts` package, local output folders, async task manager.
*   **Input:** Dialog lines array.
*   **Output:** Ordered array of output file paths.
*   **Key Pipeline Actions:**
    1.  Maps dialogue emotion tags to specific prosody parameters (e.g. `rate` speed-up for excited, `pitch` drop for serious).
    2.  Strips tags like `<break>` and `<emphasis>` to avoid pronunciation bugs in edge-tts.
    3.  Runs async threads constrained by a batch semaphore (`tts_max_concurrent`) to guarantee fast generation without HTTP connection timeouts.

### 7. Audio Post-Production & Mastering (`app/audio/processor.py`)
*   **Description:** Splices dialogue clips together with crossfades, inserts silent spacing between turns, and normalizes final loudness levels.
*   **Prerequisites:** `pydub`, standard `ffmpeg` binaries configured on the system path.
*   **Input:** List of dialog MP3 clip file paths.
*   **Output:** Single, mastered MP3 file.
