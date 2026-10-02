"""TTS Manager — Coordinates parallel voice synthesis."""

import asyncio
from pathlib import Path
from loguru import logger

from app.config import settings
from app.models import PodcastScript, DialogueLine, Emotion
from app.tts.edge_tts_provider import EdgeTTSProvider


class TTSManager:
    """Manages parallel synthesis of dialogue lines using Edge TTS."""

    def __init__(self) -> None:
        self.provider = EdgeTTSProvider()
        
        # Tuned for Ava/Andrew Multilingual Neural voices — wider dynamic range
        # creates more expressive, human-like delivery
        self.emotion_modifiers = {
            Emotion.EXCITED:    {"rate": "+12%", "pitch": "+4Hz"},
            Emotion.CURIOUS:    {"rate": "-3%",  "pitch": "+2Hz"},
            Emotion.THOUGHTFUL: {"rate": "-8%",  "pitch": "-1Hz"},
            Emotion.AMUSED:     {"rate": "+5%",  "pitch": "+3Hz"},
            Emotion.SURPRISED:  {"rate": "+8%",  "pitch": "+6Hz"},
            Emotion.SERIOUS:    {"rate": "-5%",  "pitch": "-2Hz"},
        }

    def _get_modifiers(self, emotion: Emotion) -> dict[str, str]:
        """Get rate and pitch modifiers for a given emotion."""
        return self.emotion_modifiers.get(emotion, {"rate": "+0%", "pitch": "+0Hz"})

    async def _synthesize_line(self, line: DialogueLine, line_index: int, temp_dir: Path) -> Path:
        """Synthesize a single dialogue line."""
        output_path = temp_dir / f"line_{line_index:04d}_{line.speaker.lower()}.mp3"
        modifiers = self._get_modifiers(line.emotion)
        
        logger.debug(
            f"Synthesizing line {line_index} ({line.speaker}): "
            f"emotion={line.emotion.value}, text='{line.text[:30]}...'"
        )
        
        cleaned_text = self._strip_ssml(line.text)

        await self.provider.synthesize(
            text=cleaned_text,
            speaker=line.speaker,
            output_path=output_path,
            rate=modifiers["rate"],
            pitch=modifiers["pitch"],
        )
        return output_path

    def _strip_ssml(self, text: str) -> str:
        """Remove SSML tags to prevent edge-tts from failing or speaking them literally."""
        import re
        return re.sub(r"<[^>]+>", "", text)

    async def generate_audio_for_script(self, script: PodcastScript) -> list[Path]:
        """Synthesize all lines of a script in parallel batches."""
        settings.ensure_dirs()
        temp_dir = settings.base_dir / settings.temp_dir
        
        # Clear temp directory
        for f in temp_dir.glob("*.mp3"):
            try:
                f.unlink()
            except Exception:
                pass

        logger.info(f"Starting script synthesis. Total lines: {script.total_lines}")
        
        results: list[Path] = [Path()] * len(script.lines)
        semaphore = asyncio.Semaphore(settings.tts_max_concurrent)
        
        async def worker(line: DialogueLine, index: int):
            async with semaphore:
                for attempt in range(2):
                    try:
                        path = await self._synthesize_line(line, index, temp_dir)
                        results[index] = path
                        break
                    except Exception as e:
                        if attempt == 1:
                            logger.error(f"Failed to synthesize line {index}: {e}")
                            raise
                        await asyncio.sleep(1)

        tasks = []
        for i, line in enumerate(script.lines):
            tasks.append(worker(line, i))
            
        await asyncio.gather(*tasks)
        
        logger.info("Script synthesis complete.")
        return results
