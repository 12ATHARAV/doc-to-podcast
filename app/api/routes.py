"""API routes for uploading documents and downloading generated podcasts."""

import uuid
from fastapi import APIRouter, BackgroundTasks, File, UploadFile, HTTPException, Form
from fastapi.responses import FileResponse
from loguru import logger

from app.config import settings
from app.models import JobStatus, JobStatusEnum
from app.tasks.podcast_task import jobs_db, run_podcast_pipeline

router = APIRouter(prefix="/api")


@router.post("/upload", response_model=JobStatus)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    gemini_api_key: str = Form(""),
    groq_api_key: str = Form("")
):
    """Upload a document and start the podcast generation pipeline in the background."""
    settings.ensure_dirs()
    
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    upload_path = settings.base_dir / settings.uploads_dir / file.filename
    try:
        with open(upload_path, "wb") as f:
            f.write(file_bytes)
    except Exception as e:
        logger.warning(f"Could not save upload file copy to disk: {e}")

    job_id = str(uuid.uuid4())
    job = JobStatus(
        id=job_id,
        status=JobStatusEnum.QUEUED,
        source_filename=file.filename
    )
    jobs_db[job_id] = job

    background_tasks.add_task(
        run_podcast_pipeline,
        job_id,
        file_bytes,
        file.filename,
        gemini_api_key=gemini_api_key,
        groq_api_key=groq_api_key
    )
    logger.info(f"Queued podcast generation job {job_id} for file {file.filename}")

    return job


@router.get("/status/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Retrieve the status of a podcast generation job."""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs_db[job_id]


@router.get("/jobs", response_model=list[JobStatus])
async def list_jobs():
    """List all podcast generation jobs."""
    return list(jobs_db.values())


@router.get("/download/{job_id}")
async def download_podcast(job_id: str):
    """Download the final generated podcast MP3 file."""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = jobs_db[job_id]
    if job.status != JobStatusEnum.COMPLETED or not job.output_file:
        raise HTTPException(status_code=400, detail="Podcast is not ready for download")
        
    file_path = settings.base_dir / settings.output_dir / job.output_file
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Podcast audio file not found on disk")
        
    return FileResponse(
        path=str(file_path),
        media_type="audio/mpeg",
        filename=job.output_file
    )


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a podcast generation job and its associated files."""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = jobs_db[job_id]
    
    if job.output_file:
        file_path = settings.base_dir / settings.output_dir / job.output_file
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            logger.warning(f"Could not delete podcast file {file_path}: {e}")

    del jobs_db[job_id]
    return {"status": "success", "message": f"Job {job_id} deleted."}
