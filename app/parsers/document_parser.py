"""Multi-format document parser with fallback chain."""

import io
import re
from pathlib import Path

import chardet
from loguru import logger

from app.exceptions import DocumentParsingError
from app.models import DocumentMetadata, ParsedDocument


class DocumentParser:
    """Parses documents of various formats into clean structured text.
    
    Supports: PDF, DOCX, PPTX, TXT, MD, HTML, CSV, JSON, XML.
    Uses markitdown as the primary parser with format-specific fallbacks.
    """

    SUPPORTED_EXTENSIONS = {
        ".pdf", ".docx", ".doc", ".pptx", ".txt", ".md",
        ".rtf", ".csv", ".xlsx", ".json", ".xml", ".html", ".htm",
    }

    def parse(self, file_bytes: bytes, filename: str) -> ParsedDocument:
        """Parse a document file into structured text.
        
        Args:
            file_bytes: Raw bytes of the uploaded file.
            filename: Original filename (used to detect format).
            
        Returns:
            ParsedDocument with extracted text and metadata.
            
        Raises:
            DocumentParsingError: If parsing fails for all strategies.
        """
        ext = Path(filename).suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise DocumentParsingError(
                f"Unsupported file format: {ext}. "
                f"Supported: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}"
            )

        logger.info(f"Parsing {filename} ({len(file_bytes)} bytes, format: {ext})")

        # Try primary parser (markitdown)
        text = self._try_markitdown(file_bytes, filename, ext)

        # Fallback to format-specific parsers
        if not text:
            text = self._try_fallback(file_bytes, filename, ext)

        if not text or not text.strip():
            raise DocumentParsingError(
                f"Could not extract text from {filename}. "
                "The file may be empty, corrupted, or contain only images."
            )

        # Clean the extracted text
        text = self._clean_text(text)

        # Extract metadata
        metadata = self._extract_metadata(text, filename, file_bytes, ext)

        # Count tokens (rough estimate)
        token_count = len(text) // 4  # ~4 chars per token

        logger.info(
            f"Parsed {filename}: {metadata.word_count} words, "
            f"~{token_count} tokens, {len(metadata.sections)} sections"
        )

        return ParsedDocument(
            text=text,
            metadata=metadata,
            source_file=filename,
            token_count=token_count,
        )

    def _try_markitdown(self, file_bytes: bytes, filename: str, ext: str) -> str | None:
        """Attempt parsing with markitdown."""
        try:
            from markitdown import MarkItDown

            md = MarkItDown()
            # Write to a temp file since markitdown expects file paths
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            try:
                result = md.convert(tmp_path)
                return result.text_content
            finally:
                Path(tmp_path).unlink(missing_ok=True)

        except ImportError:
            logger.warning("markitdown not installed, skipping")
            return None
        except Exception as e:
            logger.warning(f"markitdown failed for {filename}: {e}")
            return None

    def _try_fallback(self, file_bytes: bytes, filename: str, ext: str) -> str | None:
        """Try format-specific fallback parsers."""
        parsers = {
            ".pdf": self._parse_pdf,
            ".docx": self._parse_docx,
            ".doc": self._parse_docx,
            ".txt": self._parse_text,
            ".md": self._parse_text,
            ".html": self._parse_html,
            ".htm": self._parse_html,
            ".csv": self._parse_text,
            ".json": self._parse_text,
            ".xml": self._parse_text,
        }

        parser_fn = parsers.get(ext)
        if parser_fn:
            try:
                return parser_fn(file_bytes, filename)
            except Exception as e:
                logger.warning(f"Fallback parser failed for {filename}: {e}")
        return None

    def _parse_pdf(self, file_bytes: bytes, filename: str) -> str | None:
        """Parse PDF using PyMuPDF."""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(stream=file_bytes, filetype="pdf")
            pages = []
            for page in doc:
                pages.append(page.get_text())
            doc.close()
            return "\n\n".join(pages)
        except ImportError:
            logger.warning("PyMuPDF not installed")
            return None

    def _parse_docx(self, file_bytes: bytes, filename: str) -> str | None:
        """Parse DOCX using python-docx."""
        try:
            from docx import Document

            doc = Document(io.BytesIO(file_bytes))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n\n".join(paragraphs)
        except ImportError:
            logger.warning("python-docx not installed")
            return None

    def _parse_text(self, file_bytes: bytes, filename: str) -> str | None:
        """Parse plain text with encoding detection."""
        detected = chardet.detect(file_bytes)
        encoding = detected.get("encoding", "utf-8") or "utf-8"
        try:
            return file_bytes.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            return file_bytes.decode("utf-8", errors="replace")

    def _parse_html(self, file_bytes: bytes, filename: str) -> str | None:
        """Parse HTML using BeautifulSoup."""
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(file_bytes, "html.parser")
            # Remove script and style elements
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()
            return soup.get_text(separator="\n", strip=True)
        except ImportError:
            logger.warning("BeautifulSoup not installed")
            return None

    def _clean_text(self, text: str) -> str:
        """Clean extracted text by removing artifacts."""
        # Normalize whitespace
        text = re.sub(r"[ \t]+", " ", text)
        # Remove excessive newlines (more than 2)
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Remove common artifacts
        text = re.sub(r"\x00", "", text)  # null bytes
        text = re.sub(r"[\r\f\v]", "\n", text)  # normalize line endings
        return text.strip()

    def _extract_metadata(
        self, text: str, filename: str, file_bytes: bytes, ext: str
    ) -> DocumentMetadata:
        """Extract metadata from the parsed text."""
        words = text.split()
        word_count = len(words)
        sections = self._detect_sections(text)

        # Estimate page count (roughly 300 words per page)
        page_count = max(1, word_count // 300)
        if ext == ".pdf":
            try:
                import fitz
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                page_count = len(doc)
                doc.close()
            except Exception:
                pass

        # Estimate read time (average 200 wpm)
        read_time = max(1, word_count // 200)

        return DocumentMetadata(
            title=Path(filename).stem.replace("_", " ").replace("-", " ").title(),
            page_count=page_count,
            word_count=word_count,
            sections=sections,
            estimated_read_time_minutes=read_time,
        )

    def _detect_sections(self, text: str) -> list[str]:
        """Detect section headings from the text."""
        sections = []
        lines = text.split("\n")
        for line in lines:
            stripped = line.strip()
            # Markdown headings
            if stripped.startswith("#"):
                heading = stripped.lstrip("# ").strip()
                if heading and len(heading) < 200:
                    sections.append(heading)
            # Short uppercase lines (likely headings)
            elif (
                stripped.isupper()
                and 3 < len(stripped) < 100
                and not stripped.endswith(".")
            ):
                sections.append(stripped.title())
        return sections[:50]  # Cap at 50 sections
