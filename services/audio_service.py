"""
Audio Service - Handles audio transcription and generation
"""

import io
from typing import Optional
import config
from services.sarvam_service import SarvamService

class AudioService:
    """Service for audio processing operations."""
    
    def __init__(self):
        self.sarvam_service = SarvamService()
    
    async def transcribe_audio(self, audio_file_buffer: io.BytesIO, language: Optional[str] = None) -> str:
        """Transcribe audio to text."""
        effective_language = language or config.SUPPORTED_LANGUAGES[0]['code']
        return await self.sarvam_service.transcribe_audio(audio_file_buffer, effective_language)
    
    async def generate_audio_from_text(self, text: str, language: Optional[str] = None, ultra_fast: bool = False) -> io.BytesIO:
        """Generate audio from text with speed options."""
        effective_language = language or config.SUPPORTED_LANGUAGES[0]['code']
        
        if ultra_fast:
            return await self.sarvam_service.generate_audio_ultra_fast(
                text, 
                effective_language, 
                config.SARVAM_TTS_SPEAKER
            )
        else:
            return await self.sarvam_service.generate_audio(
                text, 
                effective_language, 
                config.SARVAM_TTS_SPEAKER
            )
    
    async def stream_audio_from_text(self, text: str, language: Optional[str] = None):
        """Stream audio chunks as they're generated for real-time playback."""
        effective_language = language or config.SUPPORTED_LANGUAGES[0]['code']
        
        async for audio_chunk in self.sarvam_service.stream_audio_generation(
            text, 
            effective_language, 
            config.SARVAM_TTS_SPEAKER
        ):
            yield audio_chunk