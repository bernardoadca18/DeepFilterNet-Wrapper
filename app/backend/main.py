import os
import uuid
import asyncio
import tempfile
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime

import torch
import soundfile as sf
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger

import sys
sys.path.insert(0, '/app/DeepFilterNet')

from df.enhance import init_df, enhance
from df.io import load_audio, save_audio

logger.add(
    "/app/temp_files/app.log",
    rotation="10 MB",
    level=os.getenv("LOG_LEVEL", "INFO")
)

app = FastAPI(
    title="DeepFilterNet API",
    description="Noise reduction API using DeepFilterNet",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL_CACHE_DIR = Path(os.getenv("MODEL_CACHE_DIR", "/app/model_cache"))
TEMP_FILES_DIR = Path(os.getenv("TEMP_FILES_DIR", "/app/temp_files"))
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "DeepFilterNet3")
MAX_FILE_SIZE = 100 * 1024 * 1024

model = None
df_state = None
df_sr = 48000

jobs = {}

class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int
    message: str
    created_at: str
    completed_at: Optional[str] = None
    original_filename: Optional[str] = None
    error: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    gpu_available: bool
    timestamp: str

def init_model():
    global model, df_state, df_sr
    logger.info(f"Loading {DEFAULT_MODEL} model...")
    model, df_state, _, _ = init_df(
        model_base_dir=DEFAULT_MODEL,
        post_filter=False,
        log_level="INFO"
    )
    df_sr = df_state.sr()
    logger.info(f"Model loaded successfully. Sample rate: {df_sr}Hz")

@app.on_event("startup")
async def startup_event():
    try:
        init_model()
        logger.info("DeepFilterNet API started successfully")
    except Exception as e:
        logger.error(f"Failed to initialize model: {e}")
        raise

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy" if model is not None else "initializing",
        model_loaded=model is not None,
        gpu_available=torch.cuda.is_available(),
        timestamp=datetime.utcnow().isoformat()
    )

def process_audio_job(job_id: str, input_path: Path, output_path: Path, original_filename: str):
    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["progress"] = 20
        jobs[job_id]["message"] = "Loading audio file"
        
        audio, meta = load_audio(str(input_path), df_sr)
        jobs[job_id]["progress"] = 40
        jobs[job_id]["message"] = "Processing audio with DeepFilterNet"
        
        enhanced = enhance(model, df_state, audio, pad=True)
        jobs[job_id]["progress"] = 80
        jobs[job_id]["message"] = "Saving enhanced audio"
        
        save_audio(str(output_path), enhanced, df_sr)
        jobs[job_id]["progress"] = 100
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["message"] = "Processing complete"
        jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()
        
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["message"] = f"Processing failed: {str(e)}"

@app.post("/api/enhance")
async def enhance_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    if not file.filename.lower().endswith('.wav'):
        raise HTTPException(status_code=400, detail="Only WAV files are supported")
    
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File size exceeds 100MB limit")
    
    job_id = str(uuid.uuid4())
    job_dir = TEMP_FILES_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    input_path = job_dir / f"input_{file.filename}"
    output_path = job_dir / f"enhanced_{file.filename}"
    
    with open(input_path, "wb") as f:
        f.write(content)
    
    jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "message": "Job queued for processing",
        "created_at": datetime.utcnow().isoformat(),
        "original_filename": file.filename,
        "input_path": str(input_path),
        "output_path": str(output_path),
        "job_dir": str(job_dir)
    }
    
    background_tasks.add_task(
        process_audio_job, 
        job_id, 
        input_path, 
        output_path, 
        file.filename
    )
    
    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id,
            "message": "Processing started",
            "status_url": f"/api/status/{job_id}"
        }
    )

@app.get("/api/status/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    return JobStatus(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        message=job["message"],
        created_at=job["created_at"],
        completed_at=job.get("completed_at"),
        original_filename=job.get("original_filename"),
        error=job.get("error")
    )

@app.get("/api/download/{job_id}")
async def download_enhanced_audio(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    if job["status"] != "completed":
        raise HTTPException(
            status_code=400, 
            detail=f"Job is not completed. Current status: {job['status']}"
        )
    
    output_path = Path(job["output_path"])
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Enhanced file not found")
    
    original_filename = job.get("original_filename", "audio.wav")
    download_name = f"enhanced_{original_filename}"
    
    return FileResponse(
        path=output_path,
        media_type="audio/wav",
        filename=download_name
    )

@app.get("/api/download/{job_id}/original")
async def download_original_audio(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    input_path = Path(job["input_path"])
    
    if not input_path.exists():
        raise HTTPException(status_code=404, detail="Original file not found")
    
    return FileResponse(
        path=input_path,
        media_type="audio/wav",
        filename=job.get("original_filename", "original.wav")
    )

@app.delete("/api/job/{job_id}")
async def delete_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    job_dir = Path(job["job_dir"])
    
    if job_dir.exists():
        shutil.rmtree(job_dir)
    
    del jobs[job_id]
    
    return {"message": "Job deleted successfully"}

@app.get("/")
async def root():
    return {
        "name": "DeepFilterNet API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "enhance": "POST /api/enhance",
            "status": "GET /api/status/{job_id}",
            "download": "GET /api/download/{job_id}",
            "health": "GET /api/health"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8994, log_level="info")
