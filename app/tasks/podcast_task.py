"""Background task implementation for podcast generation."""

import asyncio
from datetime import datetime
from loguru import logger

from app.agents.orchestrator import PipelineOrchestrator
from app.api.websocket import manager
from app.models import JobStatus, JobStatusEnum


# Shared job database in memory (for simplicity and zero external dependencies)
jobs_db: dict[str, JobStatus] = {}


async def run_podcast_pipeline(
    job_id: str,
    file_bytes: bytes,
    filename: str,
    gemini_api_key: str = "",
    groq_api_key: str = ""
) -> None:
    """Run the pipeline in the background and update job status."""
    logger.info(f"Starting background job: {job_id} for file: {filename}")
    
    # Ensure job entry exists
    if job_id not in jobs_db:
        jobs_db[job_id] = JobStatus(id=job_id, source_filename=filename)
        
    job = jobs_db[job_id]
    job.status = JobStatusEnum.PARSING
    job.progress_pct = 0.0
    job.current_step = "Initializing Pipeline"
    job.updated_at = datetime.now()
    
    # Define progress callback
    async def progress_callback(step: str, progress: float) -> None:
        job.current_step = step
        job.progress_pct = progress
        job.updated_at = datetime.now()
        
        # Map step names to JobStatusEnums for tracking
        step_lower = step.lower()
        if "parsing" in step_lower:
            job.status = JobStatusEnum.PARSING
        elif "analyzing" in step_lower:
            job.status = JobStatusEnum.ANALYZING
        elif "outline" in step_lower:
            job.status = JobStatusEnum.OUTLINING
        elif "writing" in step_lower:
            job.status = JobStatusEnum.WRITING
        elif "review" in step_lower:
            job.status = JobStatusEnum.REVIEWING
        elif "synthesizing" in step_lower:
            job.status = JobStatusEnum.SYNTHESIZING
        elif "audio" in step_lower:
            job.status = JobStatusEnum.PROCESSING_AUDIO
        elif "complete" in step_lower:
            job.status = JobStatusEnum.COMPLETED
            
        # Send WebSocket update
        ws_msg = {
            "job_id": job_id,
            "status": job.status.value,
            "progress": job.progress_pct,
            "step": job.current_step,
            "error": job.error_message,
        }
        await manager.send_update(job_id, ws_msg)

    try:
        orchestrator = PipelineOrchestrator(
            progress_callback=progress_callback,
            gemini_api_key=gemini_api_key,
            groq_api_key=groq_api_key
        )
        output_path = await orchestrator.run(file_bytes, filename)
        
        job.status = JobStatusEnum.COMPLETED
        job.progress_pct = 1.0
        job.current_step = "Finished"
        job.output_file = output_path.name
        job.updated_at = datetime.now()
        
        # Broadcast final success
        await manager.send_update(job_id, {
            "job_id": job_id,
            "status": job.status.value,
            "progress": 1.0,
            "step": "Finished",
            "output_file": job.output_file,
            "error": None
        })
        logger.info(f"Background job {job_id} completed successfully! Output: {output_path.name}")
        
    except Exception as e:
        logger.error(f"Background job {job_id} failed: {e}")
        job.status = JobStatusEnum.FAILED
        job.error_message = str(e)
        job.updated_at = datetime.now()
        
        # Broadcast error
        await manager.send_update(job_id, {
            "job_id": job_id,
            "status": job.status.value,
            "progress": job.progress_pct,
            "step": "Failed",
            "output_file": None,
            "error": str(e)
        })
