"""
Sarvam Service - Handles Sarvam AI integrations for translation, STT, and TTS
"""

import io
import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
from sarvamai import SarvamAI, AsyncSarvamAI, AudioOutput
from typing import Optional
import config

class SarvamService:
    """Service for Sarvam AI operations."""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.sync_client = SarvamAI(api_subscription_key=config.SARVAM_API_KEY)
        self.async_client = AsyncSarvamAI(api_subscription_key=config.SARVAM_API_KEY)
    
    def _translate_sync(self, text: str, target_language_code: str, source_language_code: str) -> str:
        """Synchronously translate text using Sarvam AI."""
        try:
            # Use specific model for Urdu
            if "ur-IN" in [target_language_code, source_language_code]:
                response = self.sync_client.text.translate(
                    input=text,
                    source_language_code=source_language_code,
                    target_language_code=target_language_code,
                    mode="classic-colloquial",
                    model="sarvam-translate:v1"
                )
            else:
                # Use default model for other languages
                response = self.sync_client.text.translate(
                    input=text,
                    source_language_code=source_language_code,
                    target_language_code=target_language_code,
                    mode="classic-colloquial"
                )
            
            return response.translated_text
            
        except Exception as e:
            print(f"Error during Sarvam AI translation: {e}")
            return text  # Return original text on failure
    
    async def translate_text(self, text: str, target_language_code: str, source_language_code: str) -> str:
        """Asynchronously translate text."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, 
            self._translate_sync, 
            text, 
            target_language_code, 
            source_language_code
        )
    
    def _transcribe_sync(self, audio_file_buffer: io.BytesIO, language_code: Optional[str]) -> str:
        """Synchronously transcribe audio."""
        try:
            audio_file_buffer.seek(0)
            response = self.sync_client.speech_to_text.transcribe(
                file=audio_file_buffer, 
                language_code=language_code
            )
            return response.transcript
        except Exception as e:
            print(f"Error during Sarvam AI transcription: {e}")
            return ""
    
    async def transcribe_audio(self, audio_file_buffer: io.BytesIO, language_code: Optional[str] = None) -> str:
        """Asynchronously transcribe audio."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, 
            self._transcribe_sync, 
            audio_file_buffer, 
            language_code
        )
    
    async def generate_audio(self, text: str, language_code: str, speaker: str) -> io.BytesIO:
        """Generate audio from text using Sarvam's streaming TTS."""
        try:
            async with self.async_client.text_to_speech_streaming.connect(model="bulbul:v2") as ws:
                await ws.configure(target_language_code=language_code, speaker=speaker)
                await ws.convert(text)
                await ws.flush()
                
                full_audio_bytes = b''
                async for message in ws:
                    if isinstance(message, AudioOutput):
                        full_audio_bytes += base64.b64decode(message.data.audio)
                
                return io.BytesIO(full_audio_bytes)
                
        except Exception as e:
            print(f"Error during Sarvam AI streaming TTS: {e}")
            return io.BytesIO()