# 🤖 Agent System Specifications: Doc-to-Podcast

This document specifies the design, capabilities, boundaries, and communication schemas of the five agents participating in the **Doc-to-Podcast** pipeline.

---

## 🏗️ Sequential Pipeline Architecture

```
[Raw File] ──▶ 1. Parser Agent (Deterministic)
                    └──▶ ParsedDocument (Clean Text + Metadata)
                            ──▶ 2. Analyst Agent (Gemini 2.5 Flash)
                                    └──▶ ContentAnalysis (Themes, Facts, Analogy Specs)
                                            ──▶ 3. Outline Agent (Gemini 2.5 Flash)
                                                    └──▶ EpisodeOutline (Timeline Segments)
                                                            ──▶ 4. Writer Agent (Gemini 2.5 Flash) ◀──┐ (Feedback Loop)
                                                                    └──▶ PodcastScript                │
                                                                            ──▶ 5. Reviewer Agent ────┘
                                                                                    └──▶ ReviewResult (Approved / Rejected)
```

---

## 📋 Agent Spec sheets

### 1. DocumentParserAgent
*   **Role:** deterministic file text extractor.
*   **LLM Provider:** None (performs standard library conversions).
*   **Goal:** Convert incoming binaries or text files into uniform markdown/plain text and extract high-level structure.
*   **Tools:** `markitdown`, `fitz` (PyMuPDF), `docx`, `BeautifulSoup`, `chardet`.
*   **Input Schema:** Raw bytes (`bytes`), file extension (`str`).
*   **Output Schema:** `ParsedDocument` containing cleaned text, metadata with page/word counts, estimated read time, and a list of section headers.
*   **Guardrails:** Max file read timeouts, character normalizations to strip null bytes, and fallback strategies.

### 2. ContentAnalystAgent
*   **Role:** Information distiller & story extractor.
*   **LLM Provider:** Gemini 2.5 Flash (Temperature: 0.4).
*   **Goal:** Read the parsed text, extract key themes, identify complex sections requiring analogies, and pull fascinating facts or statistics.
*   **System Prompt:** `app/llm/prompts/analyst.txt`
*   **Input Schema:** `ParsedDocument`
*   **Output Schema:** `ContentAnalysis` structured JSON containing list of themes, facts, concepts, quotes, debate points, and recommended length.
*   **Guardrails:** strict groundings — no external information should be injected.

### 3. OutlineArchitectAgent
*   **Role:** Show runner and narrative designer.
*   **LLM Provider:** Gemini 2.5 Flash (Temperature: 0.6).
*   **Goal:** Structure the episode segments ensuring a compelling intro hook, act divisions (Foundation -> Deep Dive -> Synthesis), balanced host interaction, and cliffhanger transitions.
*   **System Prompt:** `app/llm/prompts/outline.txt`
*   **Input Schema:** `ContentAnalysis`
*   **Output Schema:** `EpisodeOutline` listing segment titles, target durations, planned energy levels, and transition hooks.
*   **Guardrails:** Limits segment lengths to ensure pace is dynamic (no single subject exceeds 5 minutes).

### 4. ScriptWriterAgent
*   **Role:** Host dialog writer (Alex & Maya).
*   **LLM Provider:** Gemini 2.5 Flash (Primary) / Groq Llama 3.3 70B (Fallback) (Temperature: 0.8).
*   **Goal:** Generate natural, unscripted-sounding banter, explanations, disagreements, and humor using speech modifiers and emotion labels.
*   **System Prompt:** `app/llm/prompts/writer.txt`
*   **Input Schema:** `EpisodeOutline` + `ParsedDocument` + optional previous `ReviewResult` feedback.
*   **Output Schema:** `PodcastScript` (array of DialogueLines containing speaker, text with tags, emotion label, and segment association).
*   **Guardrails:** Enforce contractions (e.g., "don't" instead of "do not") and colloquial speech styles; max 500k context ingestion safety limits.

### 5. QualityReviewerAgent
*   **Role:** Fact checker & editor.
*   **LLM Provider:** Gemini 2.5 Flash (Temperature: 0.3).
*   **Goal:** Audit the script lines against the source document. Verify accuracy, check for host voice balances, evaluate conversation flow, and rate quality metrics.
*   **System Prompt:** `app/llm/prompts/reviewer.txt`
*   **Input Schema:** `PodcastScript` + `ParsedDocument`
*   **Output Schema:** `ReviewResult` indicating approval flag, quality scores, lists of issues, suggestions, and hallucination flags.
*   **Guardrails:** Any score below 7.0 or any entry in `hallucination_flags` triggers an automatic rejection, pushing the pipeline back into script revision.
