"""
ProfAI - Clean API Server
Streamlined version with only essential endpoints
"""

import logging
import asyncio
import sys
import os
import json
from typing import List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from concurrent.futures import ThreadPoolExecutor
from pydantic import BaseModel
import io
import json
import base64

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from models.schemas import CourseLMS, TTSRequest

# Import services
try:
    from services.chat_service import ChatService
    from services.document_service import DocumentService
    from services.audio_service import AudioService
    from services.teaching_service import TeachingService
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

# Initialize services
chat_service = None
document_service = None
audio_service = None
teaching_service = None

if SERVICES_AVAILABLE:
    try:
        chat_service = ChatService()
        document_service = DocumentService()
        audio_service = AudioService()
        teaching_service = TeachingService()
        print("✅ All services initialized successfully")
    except Exception as e:
        print(f"⚠️ Failed to initialize services: {e}")
        SERVICES_AVAILABLE = False

# ===== COURSE MANAGEMENT ENDPOINTS =====

@app.post("/api/upload-pdfs")
async def upload_and_process_pdfs(
    files: List[UploadFile] = File(...),
    course_title: str = Form(None)
):
    """Upload PDF files and generate course content."""
    if not SERVICES_AVAILABLE or not document_service:
        raise HTTPException(status_code=503, detail="Document processing service not available")

    try:
        logging.info(f"Processing {len(files)} PDF files for course: {course_title}")
        
        # Process PDFs and generate course
        course_data = await document_service.process_pdfs_and_generate_course(files, course_title)
        
        if not course_data:
            raise HTTPException(status_code=500, detail="Failed to generate course content")
        
        logging.info(f"Course generated successfully: {course_data.get('course_title', 'Unknown')}")
        return {"message": "Course generated successfully", "course": course_data}
        
    except Exception as e:
        logging.error(f"Error processing PDFs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/courses")
async def get_courses():
    """Get list of available courses."""
    try:
        if os.path.exists(config.OUTPUT_JSON_PATH):
            with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                course_data = json.load(f)
                return [{
                    "course_id": "1",  # Single course system
                    "course_title": course_data.get("course_title", "Generated Course"),
                    "modules": len(course_data.get("modules", []))
                }]
        return []
    except Exception as e:
        logging.error(f"Error loading courses: {e}")
        return []

@app.get("/api/course/{course_id}")
async def get_course_content(course_id: str):
    """Get specific course content."""
    try:
        if os.path.exists(config.OUTPUT_JSON_PATH):
            with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                course_data = json.load(f)
                course_data["course_id"] = course_id
                return course_data
        raise HTTPException(status_code=404, detail="Course not found")
    except Exception as e:
        logging.error(f"Error loading course {course_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== CHAT & COMMUNICATION ENDPOINTS =====

@app.post("/api/chat")
async def chat_endpoint(request: dict):
    """Text-only chat endpoint for dedicated chat page."""
    if not SERVICES_AVAILABLE or not chat_service:
        raise HTTPException(status_code=503, detail="Chat service not available")
    
    try:
        query = request.get('message') or request.get('query')
        language = request.get('language', 'en-IN')
        
        if not query:
            raise HTTPException(status_code=400, detail="Message/query is required")
        
        logging.info(f"Chat query: {query[:50]}...")
        response_data = await chat_service.ask_question(query, language)
        return response_data
    except Exception as e:
        logging.error(f"Error in chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat-with-audio")
async def chat_with_audio_endpoint(request: dict):
    """Chat endpoint with automatic audio generation for home page chat box."""
    if not SERVICES_AVAILABLE or not chat_service or not audio_service:
        raise HTTPException(status_code=503, detail="Chat or audio service not available")
    
    try:
        query = request.get('message') or request.get('query')
        language = request.get('language', 'en-IN')
        
        if not query:
            raise HTTPException(status_code=400, detail="Message/query is required")
        
        logging.info(f"Chat with audio query: {query[:50]}...")
        
        # Get text response
        response_data = await chat_service.ask_question(query, language)
        response_text = response_data.get('answer') or response_data.get('response', '')
        
        if not response_text:
            raise HTTPException(status_code=500, detail="No response generated")
        
        # Generate audio for the response
        logging.info(f"Generating audio for response: {response_text[:50]}...")
        audio_buffer = await audio_service.generate_audio_from_text(response_text, language)
        
        # Return both text and audio
        if audio_buffer.getbuffer().nbytes > 0:
            # Convert audio to base64 for JSON response
            import base64
            audio_base64 = base64.b64encode(audio_buffer.getvalue()).decode('utf-8')
            response_data['audio'] = audio_base64
            response_data['has_audio'] = True
        else:
            response_data['has_audio'] = False
            logging.warning("Audio generation failed, returning text only")
        
        return response_data
        
    except Exception as e:
        logging.error(f"Error in chat with audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/transcribe")
async def transcribe_endpoint(language: str = Form("en-IN"), audio_file: UploadFile = File(...)):
    """Audio transcription for voice input."""
    if not SERVICES_AVAILABLE or not audio_service:
        raise HTTPException(status_code=503, detail="Audio service not available")
    
    try:
        logging.info(f"Transcribing audio in language: {language}")
        
        audio_content = await audio_file.read()
        audio_buffer = io.BytesIO(audio_content)
        
        transcribed_text = await audio_service.transcribe_audio(audio_buffer, language)
        
        if not transcribed_text:
            raise HTTPException(status_code=400, detail="Could not transcribe audio")
        
        logging.info(f"Transcribed: {transcribed_text[:50]}...")
        return {"transcribed_text": transcribed_text}
        
    except Exception as e:
        logging.error(f"Error in transcription: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== CLASS TEACHING ENDPOINTS =====

@app.post("/api/start-class")
async def start_class_endpoint(request: dict):
    """Start a class session with content preview and audio generation."""
    if not SERVICES_AVAILABLE or not teaching_service or not audio_service:
        raise HTTPException(status_code=503, detail="Required services not available")
    
    try:
        course_id = request.get("course_id")
        module_index = request.get("module_index", 0)
        sub_topic_index = request.get("sub_topic_index", 0)
        language = request.get("language", "en-IN")
        content_only = request.get("content_only", False)  # If true, return only content preview
        
        logging.info(f"Starting class for course: {course_id}, module: {module_index}, topic: {sub_topic_index}")
        
        # Load course content
        if not os.path.exists(config.OUTPUT_JSON_PATH):
            raise HTTPException(status_code=404, detail="Course content not found")
        
        with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
            course_data = json.load(f)
        
        # Validate indices
        if module_index >= len(course_data.get("modules", [])):
            raise HTTPException(status_code=400, detail="Module not found")
            
        module = course_data["modules"][module_index]
        
        if sub_topic_index >= len(module.get("sub_topics", [])):
            raise HTTPException(status_code=400, detail="Sub-topic not found")
            
        sub_topic = module["sub_topics"][sub_topic_index]
        
        # Generate teaching content
        raw_content = sub_topic.get('content', '')
        if not raw_content:
            raw_content = f"This topic covers {sub_topic['title']} as part of {module['title']}."
        
        try:
            teaching_content = await teaching_service.generate_teaching_content(
                module_title=module['title'],
                sub_topic_title=sub_topic['title'],
                raw_content=raw_content,
                language=language
            )
            
            if not teaching_content or len(teaching_content.strip()) == 0:
                raise Exception("Empty teaching content generated")
                
        except Exception as e:
            logging.error(f"Error generating teaching content: {e}")
            # Fallback content
            teaching_content = f"Welcome to the lesson on {sub_topic['title']}. {raw_content[:500]}..."
        
        logging.info(f"Generated teaching content: {len(teaching_content)} characters")
        
        # If only content preview is requested, return it
        if content_only:
            return {
                "content_preview": teaching_content[:400] + "..." if len(teaching_content) > 400 else teaching_content,
                "full_content_length": len(teaching_content),
                "module_title": module['title'],
                "sub_topic_title": sub_topic['title']
            }
        
        # Generate audio
        logging.info("Generating audio for teaching content...")
        audio_buffer = await audio_service.generate_audio_from_text(teaching_content, language)
        
        if not audio_buffer.getbuffer().nbytes:
            raise HTTPException(status_code=500, detail="Failed to generate audio")
        
        logging.info(f"Audio generated: {audio_buffer.getbuffer().nbytes} bytes")
        return StreamingResponse(audio_buffer, media_type="audio/mpeg")
        
    except Exception as e:
        logging.error(f"Error starting class: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== WEBSOCKET STREAMING ENDPOINTS =====

@app.websocket("/ws/test")
async def websocket_test(websocket: WebSocket):
    """Simple WebSocket test endpoint."""
    try:
        await websocket.accept()
        logging.info("Test WebSocket connection accepted")
        
        await websocket.send_json({
            "type": "connection_ready",
            "message": "Test WebSocket connected successfully"
        })
        
        while True:
            try:
                data = await websocket.receive_json()
                message_type = data.get("type")
                
                if message_type == "ping":
                    await websocket.send_json({"type": "pong", "message": "Test connection alive"})
                elif message_type == "echo":
                    await websocket.send_json({"type": "echo", "data": data})
                else:
                    await websocket.send_json({"type": "error", "error": f"Unknown type: {message_type}"})
                    
            except WebSocketDisconnect:
                logging.info("Test WebSocket client disconnected")
                break
            except Exception as e:
                logging.error(f"Test WebSocket error: {e}")
                break
                
    except Exception as e:
        logging.error(f"Test WebSocket connection error: {e}")

@app.websocket("/ws/audio-stream")
async def websocket_audio_stream(websocket: WebSocket):
    """WebSocket endpoint for real-time audio streaming with sub-900ms latency."""
    try:
        await websocket.accept()
        logging.info("WebSocket connection accepted")
        
        # Send connection confirmation immediately
        await websocket.send_json({
            "type": "connection_ready",
            "message": "WebSocket connected and ready",
            "services_available": SERVICES_AVAILABLE,
            "chat_service": chat_service is not None,
            "audio_service": audio_service is not None
        })
        
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_json()
                message_type = data.get("type")
                
                logging.info(f"Received WebSocket message: {message_type}")
                
                if message_type == "ping":
                    await websocket.send_json({"type": "pong", "message": "Connection alive"})
                
                elif message_type == "chat_with_audio":
                    if not SERVICES_AVAILABLE or not chat_service or not audio_service:
                        await websocket.send_json({"type": "error", "error": "Required services not available"})
                        continue
                    await handle_chat_with_audio(websocket, data, chat_service, audio_service)
                
                elif message_type == "start_class":
                    if not SERVICES_AVAILABLE or not teaching_service or not audio_service:
                        await websocket.send_json({"type": "error", "error": "Teaching services not available"})
                        continue
                    await handle_start_class(websocket, data, teaching_service, audio_service)
                
                elif message_type == "audio_only":
                    if not SERVICES_AVAILABLE or not audio_service:
                        await websocket.send_json({"type": "error", "error": "Audio service not available"})
                        continue
                    await handle_audio_only(websocket, data, audio_service)
                
                else:
                    await websocket.send_json({
                        "type": "error", 
                        "error": f"Unknown message type: {message_type}"
                    })
                    
            except WebSocketDisconnect:
                logging.info("WebSocket client disconnected")
                break
            except Exception as e:
                logging.error(f"Error processing WebSocket message: {e}")
                import traceback
                traceback.print_exc()
                try:
                    await websocket.send_json({
                        "type": "error",
                        "error": f"Message processing error: {str(e)}"
                    })
                except:
                    break
                
    except Exception as e:
        logging.error(f"WebSocket connection error: {e}")
        import traceback
        traceback.print_exc()
        try:
            await websocket.close()
        except:
            pass

async def handle_chat_with_audio(websocket: WebSocket, data: dict, chat_service, audio_service):
    """Handle chat with audio streaming."""
    try:
        query = data.get("message")
        language = data.get("language", "en-IN")
        
        if not query:
            await websocket.send_json({"type": "error", "error": "Message is required"})
            return
        
        logging.info(f"Processing chat query: {query[:50]}...")
        
        # Send immediate acknowledgment
        await websocket.send_json({
            "type": "processing_started",
            "message": "Generating response..."
        })
        
        try:
            # Get text response
            response_data = await chat_service.ask_question(query, language)
            response_text = response_data.get('answer') or response_data.get('response', '')
            
            if not response_text:
                await websocket.send_json({"type": "error", "error": "No response generated"})
                return
            
            logging.info(f"Generated response: {len(response_text)} chars")
            
            # Send text response immediately
            await websocket.send_json({
                "type": "text_response",
                "text": response_text,
                "metadata": response_data
            })
            
        except Exception as e:
            logging.error(f"Chat service error: {e}")
            await websocket.send_json({
                "type": "error",
                "error": f"Chat service failed: {str(e)}"
            })
            return
        
        # Generate audio using the faster non-streaming method for now
        await websocket.send_json({
            "type": "audio_stream_start",
            "message": "Generating audio..."
        })
        
        try:
            logging.info("Starting audio generation...")
            # Use ultra-fast generation for better reliability
            audio_buffer = await audio_service.generate_audio_from_text(response_text, language, ultra_fast=True)
            
            if audio_buffer and audio_buffer.getbuffer().nbytes > 0:
                logging.info(f"Audio generated: {audio_buffer.getbuffer().nbytes} bytes")
                # Send as single chunk for now
                audio_base64 = base64.b64encode(audio_buffer.getvalue()).decode('utf-8')
                await websocket.send_json({
                    "type": "audio_chunk",
                    "chunk_id": 1,
                    "audio_data": audio_base64,
                    "size": audio_buffer.getbuffer().nbytes
                })
                
                await websocket.send_json({
                    "type": "audio_stream_complete",
                    "total_chunks": 1,
                    "message": "Audio generation complete"
                })
            else:
                logging.warning("No audio generated")
                await websocket.send_json({
                    "type": "error",
                    "error": "Failed to generate audio - empty result"
                })
                
        except Exception as e:
            logging.error(f"Audio generation error: {e}")
            import traceback
            traceback.print_exc()
            await websocket.send_json({
                "type": "error",
                "error": f"Audio generation failed: {str(e)}"
            })
            
    except Exception as e:
        logging.error(f"Chat with audio error: {e}")
        import traceback
        traceback.print_exc()
        await websocket.send_json({
            "type": "error",
            "error": f"Chat processing failed: {str(e)}"
        })

async def handle_start_class(websocket: WebSocket, data: dict, teaching_service, audio_service):
    """Handle start class with real-time audio streaming."""
    try:
        course_id = data.get("course_id")
        module_index = data.get("module_index", 0)
        sub_topic_index = data.get("sub_topic_index", 0)
        language = data.get("language", "en-IN")
        
        logging.info(f"WebSocket start class: course={course_id}, module={module_index}, topic={sub_topic_index}")
        
        # Send immediate acknowledgment
        await websocket.send_json({
            "type": "class_starting",
            "message": "Loading course content...",
            "course_id": course_id,
            "module_index": module_index,
            "sub_topic_index": sub_topic_index
        })
        
        try:
            # Load course content
            if not os.path.exists(config.OUTPUT_JSON_PATH):
                await websocket.send_json({"type": "error", "error": "Course content not found"})
                return
            
            with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                course_data = json.load(f)
            
            # Validate indices
            if module_index >= len(course_data.get("modules", [])):
                await websocket.send_json({"type": "error", "error": "Module not found"})
                return
                
            module = course_data["modules"][module_index]
            
            if sub_topic_index >= len(module.get("sub_topics", [])):
                await websocket.send_json({"type": "error", "error": "Sub-topic not found"})
                return
                
            sub_topic = module["sub_topics"][sub_topic_index]
            
            # Send course info
            await websocket.send_json({
                "type": "course_info",
                "module_title": module['title'],
                "sub_topic_title": sub_topic['title'],
                "message": "Generating teaching content..."
            })
            
            # Generate teaching content
            raw_content = sub_topic.get('content', '')
            if not raw_content:
                raw_content = f"This topic covers {sub_topic['title']} as part of {module['title']}."
            
            try:
                teaching_content = await teaching_service.generate_teaching_content(
                    module_title=module['title'],
                    sub_topic_title=sub_topic['title'],
                    raw_content=raw_content,
                    language=language
                )
                
                if not teaching_content or len(teaching_content.strip()) == 0:
                    raise Exception("Empty teaching content generated")
                    
            except Exception as e:
                logging.error(f"Error generating teaching content: {e}")
                # Fallback content
                teaching_content = f"Welcome to the lesson on {sub_topic['title']}. {raw_content[:500]}..."
            
            logging.info(f"Generated teaching content: {len(teaching_content)} characters")
            
            # Send teaching content
            await websocket.send_json({
                "type": "teaching_content",
                "content": teaching_content,
                "content_length": len(teaching_content),
                "message": "Content generated, starting audio..."
            })
            
        except Exception as e:
            logging.error(f"Course loading error: {e}")
            await websocket.send_json({
                "type": "error",
                "error": f"Failed to load course content: {str(e)}"
            })
            return
        
        # Generate audio with streaming
        await websocket.send_json({
            "type": "audio_stream_start",
            "message": "Generating class audio..."
        })
        
        try:
            logging.info("Starting class audio generation...")
            # Use ultra-fast generation for better reliability
            audio_buffer = await audio_service.generate_audio_from_text(teaching_content, language, ultra_fast=True)
            
            if audio_buffer and audio_buffer.getbuffer().nbytes > 0:
                logging.info(f"Class audio generated: {audio_buffer.getbuffer().nbytes} bytes")
                audio_base64 = base64.b64encode(audio_buffer.getvalue()).decode('utf-8')
                await websocket.send_json({
                    "type": "audio_chunk",
                    "chunk_id": 1,
                    "audio_data": audio_base64,
                    "size": audio_buffer.getbuffer().nbytes
                })
                
                await websocket.send_json({
                    "type": "class_complete",
                    "total_chunks": 1,
                    "message": "Class audio ready to play!"
                })
            else:
                logging.warning("No class audio generated")
                await websocket.send_json({
                    "type": "error",
                    "error": "Failed to generate class audio"
                })
                
        except Exception as e:
            logging.error(f"Class audio generation error: {e}")
            import traceback
            traceback.print_exc()
            await websocket.send_json({
                "type": "error",
                "error": f"Class audio generation failed: {str(e)}"
            })
            
    except Exception as e:
        logging.error(f"Start class error: {e}")
        import traceback
        traceback.print_exc()
        await websocket.send_json({
            "type": "error",
            "error": f"Class processing failed: {str(e)}"
        })

async def handle_audio_only(websocket: WebSocket, data: dict, audio_service):
    """Handle audio-only generation."""
    try:
        text = data.get("text")
        language = data.get("language", "en-IN")
        
        if not text:
            await websocket.send_json({"type": "error", "error": "Text is required"})
            return
        
        logging.info(f"Processing audio-only request: {len(text)} chars")
        
        await websocket.send_json({
            "type": "audio_stream_start",
            "message": "Generating audio..."
        })
        
        try:
            logging.info("Starting audio generation...")
            # Use ultra-fast generation for better reliability
            audio_buffer = await audio_service.generate_audio_from_text(text, language, ultra_fast=True)
            
            if audio_buffer and audio_buffer.getbuffer().nbytes > 0:
                logging.info(f"Audio generated: {audio_buffer.getbuffer().nbytes} bytes")
                audio_base64 = base64.b64encode(audio_buffer.getvalue()).decode('utf-8')
                await websocket.send_json({
                    "type": "audio_chunk",
                    "chunk_id": 1,
                    "audio_data": audio_base64,
                    "size": audio_buffer.getbuffer().nbytes
                })
                
                await websocket.send_json({
                    "type": "audio_stream_complete",
                    "total_chunks": 1
                })
            else:
                logging.warning("No audio generated")
                await websocket.send_json({
                    "type": "error",
                    "error": "Failed to generate audio - empty result"
                })
                
        except Exception as e:
            logging.error(f"Audio generation error: {e}")
            import traceback
            traceback.print_exc()
            await websocket.send_json({
                "type": "error",
                "error": f"Audio generation failed: {str(e)}"
            })
            
    except Exception as e:
        logging.error(f"Audio only error: {e}")
        import traceback
        traceback.print_exc()
        await websocket.send_json({
            "type": "error",
            "error": f"Audio processing failed: {str(e)}"
        })

# ===== SYSTEM ENDPOINTS =====

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "services_available": SERVICES_AVAILABLE,
        "services": {
            "chat_service": chat_service is not None,
            "document_service": document_service is not None,
            "audio_service": audio_service is not None,
            "teaching_service": teaching_service is not None
        }
    }

@app.get("/test-services")
async def test_services():
    """Test endpoint to verify services are working."""
    results = {}
    
    # Test chat service
    if chat_service:
        try:
            response = await chat_service.ask_question("Hello", "en-IN")
            results["chat_service"] = {"status": "working", "response_length": len(str(response))}
        except Exception as e:
            results["chat_service"] = {"status": "error", "error": str(e)}
    else:
        results["chat_service"] = {"status": "not_available"}
    
    # Test audio service
    if audio_service:
        try:
            audio_buffer = await audio_service.generate_audio_from_text("Hello test", "en-IN", ultra_fast=True)
            results["audio_service"] = {"status": "working", "audio_size": audio_buffer.getbuffer().nbytes}
        except Exception as e:
            results["audio_service"] = {"status": "error", "error": str(e)}
    else:
        results["audio_service"] = {"status": "not_available"}
    
    return {
        "overall_status": "tested",
        "services_available": SERVICES_AVAILABLE,
        "test_results": results
    }

@app.get("/websocket-info")
async def websocket_info():
    """Information about available WebSocket endpoints."""
    base_url = "ws://localhost:5001"  # Adjust based on your config
    
    return {
        "websocket_endpoints": {
            "/ws/test": {
                "url": f"{base_url}/ws/test",
                "description": "Simple WebSocket test endpoint for connection testing",
                "supported_messages": ["ping", "echo"],
                "example_usage": {
                    "ping": {"type": "ping"},
                    "echo": {"type": "echo", "message": "test"}
                }
            },
            "/ws/audio-stream": {
                "url": f"{base_url}/ws/audio-stream",
                "description": "Real-time audio streaming with sub-900ms latency",
                "supported_messages": ["ping", "chat_with_audio", "start_class", "audio_only"],
                "example_usage": {
                    "ping": {"type": "ping"},
                    "chat_with_audio": {
                        "type": "chat_with_audio",
                        "message": "Hello, how are you?",
                        "language": "en-IN"
                    },
                    "start_class": {
                        "type": "start_class",
                        "course_id": "1",
                        "module_index": 0,
                        "sub_topic_index": 0,
                        "language": "en-IN"
                    },
                    "audio_only": {
                        "type": "audio_only",
                        "text": "Convert this text to audio",
                        "language": "en-IN"
                    }
                }
            }
        },
        "note": "WebSocket endpoints don't appear in Swagger/OpenAPI docs. Use WebSocket clients to test.",
        "test_page": "/stream-test",
        "python_test_script": "test_websocket.py"
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

@app.get("/chat")
async def serve_chat():
    return FileResponse(os.path.join(web_dir, 'chat.html'))

@app.get("/stream-test")
async def serve_stream_test():
    return FileResponse(os.path.join(web_dir, 'stream-test.html'))

@app.get("/websocket-status")
async def serve_websocket_status():
    return FileResponse(os.path.join(web_dir, 'websocket-status.html'))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="info")