"""
ProfAI - Main API Server
A unified API server for AI-powered course generation and multilingual chat.
"""

import logging
import asyncio
import sys
import os
import json
from typing import List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from concurrent.futures import ThreadPoolExecutor
from pydantic import BaseModel
import io

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from models.schemas import CourseLMS

# Import services
try:
    from services.chat_service import ChatService
    from services.document_service import DocumentService
    from services.audio_service import AudioService
    SERVICES_AVAILABLE = True
    print("✅ All services loaded successfully")
except ImportError as e:
    print(f"⚠️ Some services not available: {e}")
    SERVICES_AVAILABLE = False

# Initialize FastAPI app
app = FastAPI(
    title="ProfAI API",
    description="AI-powered multilingual educational assistant with course generation and chat capabilities.",
    version="2.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Mount static files
web_dir = os.path.join(os.path.dirname(__file__), "web")
if os.path.exists(web_dir):
    app.mount("/static", StaticFiles(directory=web_dir), name="static")

# Create thread pool for async operations
executor = ThreadPoolExecutor()

# Initialize services
chat_service = None
document_service = None
audio_service = None

if SERVICES_AVAILABLE:
    try:
        chat_service = ChatService()
        document_service = DocumentService()
        audio_service = AudioService()
        print("✅ All services initialized successfully")
    except Exception as e:
        print(f"⚠️ Failed to initialize services: {e}")
        SERVICES_AVAILABLE = False

# Pydantic models
class TextQuery(BaseModel):
    query: str
    language: Optional[str] = "en-IN"

class TTSRequest(BaseModel):
    text: str
    language: Optional[str] = "en-IN"

# ===== COURSE GENERATION ENDPOINTS =====

@app.post("/api/upload-pdfs")
async def upload_and_process_pdfs(
    files: List[UploadFile] = File(...),
    course_title: str = Form(None)
):
    """Upload PDF files and generate course content."""
    if not SERVICES_AVAILABLE or not document_service:
        raise HTTPException(status_code=503, detail="Document processing service not available")
    
    try:
        # Validate files
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded")
        
        for file in files:
            if not file.filename.lower().endswith('.pdf'):
                raise HTTPException(status_code=400, detail=f"File {file.filename} is not a PDF")
        
        logging.info(f"Processing {len(files)} PDF files")
        
        # Process files
        loop = asyncio.get_event_loop()
        course_data = await loop.run_in_executor(
            executor, 
            document_service.process_uploaded_pdfs, 
            files, 
            course_title
        )
        
        return {
            "message": "Course generated successfully!",
            "course_id": "1",
            "course_title": course_data.get("course_title", "Generated Course"),
            "modules_count": len(course_data.get("modules", [])),
            "course_data": course_data
        }
        
    except Exception as e:
        logging.error(f"Error in upload endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/courses")
async def get_courses():
    """Get list of available courses."""
    try:
        if os.path.exists(config.OUTPUT_JSON_PATH):
            with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                course_data = json.load(f)
            
            return [{
                "course_id": "1",
                "course_title": course_data.get("course_title", "Generated Course")
            }]
        else:
            return []
            
    except Exception as e:
        logging.error(f"Error fetching courses: {e}")
        return []

@app.get("/api/course/{course_id}")
async def get_course_content(course_id: str):
    """Get specific course content."""
    try:
        if os.path.exists(config.OUTPUT_JSON_PATH):
            with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                course_data = json.load(f)
            return course_data
        else:
            raise HTTPException(status_code=404, detail="Course not found")
            
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Course content not found")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Course content file is corrupted")
    except Exception as e:
        logging.error(f"Error retrieving course {course_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ===== CHAT/RAG ENDPOINTS =====

@app.post("/ask_text")
async def ask_text_endpoint(query: TextQuery):
    """Text-based chat with RAG."""
    if not SERVICES_AVAILABLE or not chat_service:
        raise HTTPException(status_code=503, detail="Chat service not available")
    
    try:
        logging.info(f"Processing text query: {query.query[:50]}...")
        response_data = await chat_service.ask_question(query.query, query.language)
        return response_data
    except Exception as e:
        logging.error(f"Error in text query: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.post("/ask_voice")
async def ask_voice_endpoint(language: str = Form("en-IN"), audio_file: UploadFile = File(...)):
    """Voice-based chat with RAG."""
    if not SERVICES_AVAILABLE or not chat_service or not audio_service:
        raise HTTPException(status_code=503, detail="Voice services not available")
    
    try:
        logging.info("Processing voice query...")
        
        # Transcribe audio
        audio_data = io.BytesIO(await audio_file.read())
        transcribed_text = await audio_service.transcribe_audio(audio_data, language)
        
        if not transcribed_text:
            raise HTTPException(status_code=400, detail="Audio transcription failed")
        
        logging.info(f"Transcribed: {transcribed_text[:50]}...")
        
        # Process with RAG
        response_data = await chat_service.ask_question(transcribed_text, language)
        
        return {"transcribed_text": transcribed_text, **response_data}
        
    except Exception as e:
        logging.error(f"Error in voice query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate_audio")
async def generate_audio_endpoint(request: TTSRequest):
    """Text-to-speech generation."""
    if not SERVICES_AVAILABLE or not audio_service:
        raise HTTPException(status_code=503, detail="Audio service not available")
    
    try:
        logging.info(f"Generating audio for: {request.text[:50]}...")
        
        audio_buffer = await audio_service.generate_audio_from_text(request.text, request.language)
        
        if not audio_buffer.getbuffer().nbytes:
            raise HTTPException(status_code=500, detail="Failed to generate audio")
        
        return StreamingResponse(audio_buffer, media_type="audio/mpeg")
        
    except Exception as e:
        logging.error(f"Error generating audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chat/status")
async def get_chat_status():
    """Check chat system status."""
    return {
        "services_available": SERVICES_AVAILABLE,
        "chat_service": chat_service is not None,
        "document_service": document_service is not None,
        "audio_service": audio_service is not None,
        "rag_active": chat_service.is_rag_active if chat_service else False,
        "vectorstore_available": chat_service.vectorstore is not None if chat_service else False
    }

# ===== WEB INTERFACE ENDPOINTS =====

@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(web_dir, 'index.html'))

@app.get("/upload")
async def serve_upload():
    return FileResponse(os.path.join(web_dir, 'upload.html'))

@app.get("/courses")
async def serve_courses():
    return FileResponse(os.path.join(web_dir, 'courses.html'))

@app.get("/course")
async def serve_course():
    return FileResponse(os.path.join(web_dir, 'course.html'))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5001, reload=True)