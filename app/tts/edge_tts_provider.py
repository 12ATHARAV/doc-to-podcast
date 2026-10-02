"""Microsoft Edge TTS implementation."""

import asyncio
import edge_tts
from pathlib import Path
from loguru import logger

from app.config import settings
from app.exceptions import TTSSynthesisError


class EdgeTTSProvider:
    """Generates audio files from text using Microsoft Edge TTS."""

    def __init__(self) -> None:
        self.voices = {
            "ALEX": settings.male_voice or "en-US-AndrewNeural",
            "MAYA": settings.female_voice or "en-US-AriaNeural",
        }
        self.fallbacks = {
            "ALEX": settings.male_voice_fallback or "en-US-GuyNeural",
            "MAYA": settings.female_voice_fallback or "en-US-JennyNeural",
        }
        logger.info(f"Initialized EdgeTTSProvider with voices: {self.voices}")

    async def synthesize(
        self, text: str, speaker: str, output_path: Path, rate: str = "+0%", pitch: str = "+0Hz"
    ) -> Path:
        """Synthesize a line of text using Edge TTS.
        
        Args:
            text: Text to synthesize.
            speaker: ALEX or MAYA.
            output_path: Path where the output MP3 will be saved.
            rate: Speed modifier (e.g. "+10%", "-5%").
            pitch: Pitch modifier (e.g. "+5Hz", "-2Hz").
            
        Returns:
            Path to the generated audio file.
            
        Raises:
            TTSSynthesisError: If speech synthesis fails.
        """
        voice = self.voices.get(speaker, "en-US-AriaNeural")
        
        for attempt in range(settings.tts_max_retries + 1):
            try:
                communicate = edge_tts.Communicate(
                    text=text,
                    voice=voice,
                    rate=rate,
                    pitch=pitch,
                )
                await communicate.save(str(output_path))
                
                # Check if file was actually created and is not empty
                if output_path.exists() and output_path.stat().st_size > 0:
                    return output_path
                    
                raise Exception("Generated audio file is empty or missing")

            except Exception as e:
                logger.warning(
                    f"Edge TTS attempt {attempt} failed for speaker {speaker}: {e}"
                )
                if attempt == settings.tts_max_retries:
                    # Try fallback voice on the final attempt
                    fallback_voice = self.fallbacks.get(speaker, "en-US-JennyNeural")
                    logger.info(f"Retrying with fallback voice: {fallback_voice}")
                    try:
                        communicate = edge_tts.Communicate(
                            text=text,
                            voice=fallback_voice,
                            rate=rate,
                            pitch=pitch,
                        )
                        await communicate.save(str(output_path))
                        if output_path.exists() and output_path.stat().st_size > 0:
                            return output_path
                    except Exception as fallback_err:
                        raise TTSSynthesisError(
                            f"Edge TTS synthesis failed with both primary and fallback voices: {fallback_err}"
                        ) from fallback_err
                        
                    raise TTSSynthesisError(
                        f"Edge TTS synthesis failed after max attempts: {e}"
                    ) from e
                
                # Exponential backoff
                await asyncio.sleep(2**attempt)
                
        raise TTSSynthesisError("Edge TTS synthesis failed unexpectedly")
