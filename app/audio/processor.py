"""Audio processor — stitches and masters the final podcast file."""

import uuid
from pathlib import Path
from loguru import logger
from pydub import AudioSegment
from pydub.effects import normalize

from app.config import settings
from app.exceptions import AudioProcessingError


class AudioProcessor:
    """Combines, crossfades, and normalizes audio segments into a final podcast."""

    def process(self, segment_paths: list[Path]) -> Path:
        """Stitch individual audio segments into a single cohesive podcast.
        
        Args:
            segment_paths: Ordered list of paths to individual dialogue line audio files.
            
        Returns:
            Path to the finished podcast MP3 file.
            
        Raises:
            AudioProcessingError: If stitching or mastering fails.
        """
        if not segment_paths:
            raise AudioProcessingError("No audio segments provided to stitch.")

        logger.info(f"Stitching {len(segment_paths)} audio segments...")
        settings.ensure_dirs()
        
        try:
            combined = AudioSegment.empty()
            
            # Load pauses
            speaker_pause = AudioSegment.silent(duration=settings.speaker_pause_ms)
            continuation_pause = AudioSegment.silent(duration=settings.continuation_pause_ms)
            
            prev_speaker = None
            
            for i, path in enumerate(segment_paths):
                if not path.exists():
                    logger.warning(f"Audio segment missing: {path}, skipping.")
                    continue
                
                segment = AudioSegment.from_file(str(path))
                
                parts = path.stem.split("_")
                current_speaker = parts[-1] if parts else None
                
                # Add pauses between dialogue lines
                if i > 0:
                    if current_speaker == prev_speaker:
                        combined += continuation_pause
                    else:
                        combined += speaker_pause
                
                if settings.crossfade_ms > 0 and len(combined) > settings.crossfade_ms:
                    combined = combined.append(segment, crossfade=settings.crossfade_ms)
                else:
                    combined += segment
                    
                prev_speaker = current_speaker

            logger.info("Applying loudness normalization...")
            mastered = normalize(combined)

            # Export final MP3
            output_filename = f"podcast_{uuid.uuid4().hex[:8]}.mp3"
            output_path = settings.base_dir / settings.output_dir / output_filename
            
            logger.info(f"Exporting final podcast to {output_path}...")
            mastered.export(
                str(output_path),
                format="mp3",
                bitrate=settings.output_bitrate,
                parameters=["-ar", str(settings.sample_rate)]
            )
            
            logger.info("Audio processing complete.")
            return output_path

        except Exception as e:
            logger.error(f"Failed to process audio: {e}")
            raise AudioProcessingError(f"Audio post-production failed: {e}") from e
