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
from utils.connection_monitor import (
    is_client_connected, 
    is_normal_closure, 
    log_disconnection,
    should_continue_streaming
)

class SarvamService:
    """Service for Sarvam AI operations."""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=6)  # Increased for parallel processing
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
        """Generate audio from text with optimized parallel processing for low latency."""
        try:
            print(f"🔊 Fast audio generation for {len(text)} characters")
            
            # Aggressive text cleaning and optimization for speed
            cleaned_text = self._clean_text_for_tts_fast(text)
            print(f"   Optimized text: {len(cleaned_text)} chars")
            
            # Dynamic chunk sizing based on text length for optimal speed
            if len(cleaned_text) <= 2500:
                print("   Single chunk - ultra fast...")
                return await self._generate_audio_single(cleaned_text, language_code, speaker)
            elif len(cleaned_text) <= 6000:
                print("   Small parallel batch...")
                return await self._generate_audio_parallel_chunks(cleaned_text, language_code, speaker, 2000)
            else:
                print("   Large parallel processing...")
                return await self._generate_audio_parallel_chunks(cleaned_text, language_code, speaker, 2500)
                
        except Exception as e:
            print(f"❌ Error during fast TTS: {e}")
            return io.BytesIO()
    
    async def generate_audio_ultra_fast(self, text: str, language_code: str, speaker: str) -> io.BytesIO:
        """Ultra-fast audio generation with aggressive truncation for minimal latency."""
        try:
            print(f"⚡ Ultra-fast generation for {len(text)} chars")
            
            # Aggressive truncation for speed
            if len(text) > 3000:
                text = text[:2800] + "."
                print(f"   Truncated to 2800 chars for ultra speed")
            
            # Minimal cleaning for maximum speed
            import re
            text = re.sub(r'[*#_`\[\]{}\\]', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            
            # Single request only for maximum speed
            return await self._generate_audio_single(text, language_code, speaker)
            
        except Exception as e:
            print(f"❌ Ultra-fast TTS error: {e}")
            return io.BytesIO()
    
    async def stream_audio_generation(self, text: str, language_code: str, speaker: str, websocket=None):
        """Stream audio chunks in real-time for sub-300ms latency - OPTIMIZED VERSION."""
        try:
            print(f"🚀 REAL-TIME streaming for {len(text)} chars")
            
            # Check if client is still connected before starting
            if websocket and self._is_client_disconnected(websocket):
                print("   🔌 Client already disconnected - stopping generation")
                return
            
            # Aggressive text cleaning for maximum speed
            cleaned_text = self._clean_text_for_ultra_fast_streaming(text)
            
            # Use VERY small chunks for immediate first audio
            chunk_size = 800  # Much smaller for faster first chunk
            
            if len(cleaned_text) <= chunk_size:
                # Single chunk - direct streaming from Sarvam
                print("   Single chunk - direct streaming")
                async for chunk in self._stream_audio_direct(cleaned_text, language_code, speaker, websocket):
                    yield chunk
            else:
                # Multi-chunk with immediate first chunk delivery
                print("   Multi-chunk streaming with immediate delivery")
                async for chunk in self._stream_audio_immediate(cleaned_text, language_code, speaker, chunk_size, websocket):
                    yield chunk
                    
        except Exception as e:
            error_msg = str(e)
            if self._is_normal_disconnection(error_msg):
                print(f"   🔌 Client disconnected during streaming: {e}")
                print(f"   ⚠️ Stopping audio generation - client no longer connected")
                return
            else:
                print(f"❌ Streaming error: {e}")
                # Only fallback for actual errors, not disconnections
                if websocket and not self._is_client_disconnected(websocket):
                    try:
                        print("   Falling back to ultra-fast generation")
                        audio_buffer = await self.generate_audio_ultra_fast(text, language_code, speaker)
                        if audio_buffer and audio_buffer.getbuffer().nbytes > 0:
                            yield audio_buffer.getvalue()
                    except Exception as fallback_error:
                        print(f"   Fallback also failed: {fallback_error}")
                        return
    
    async def _stream_audio_direct(self, text: str, language_code: str, speaker: str, websocket=None):
        """Direct streaming from Sarvam with immediate chunk delivery."""
        try:
            print(f"   🎯 Direct streaming: {len(text)} chars")
            
            # Check if client is still connected before starting
            if websocket and self._is_client_disconnected(websocket):
                print("   🔌 Client disconnected before streaming - stopping")
                return
            
            # Import AudioOutput here to avoid import issues
            from sarvamai import AudioOutput
            
            async with self.async_client.text_to_speech_streaming.connect(model="bulbul:v2") as ws:
                # Configure immediately
                await ws.configure(target_language_code=language_code, speaker=speaker)
                
                # Start conversion immediately
                await ws.convert(text)
                
                # Stream chunks as they arrive with connection checking
                chunk_count = 0
                async for message in ws:
                    # Check connection before yielding each chunk
                    if websocket and self._is_client_disconnected(websocket):
                        print(f"   🔌 Client disconnected after {chunk_count} chunks - stopping")
                        return
                    
                    if isinstance(message, AudioOutput) and message.data and message.data.audio:
                        chunk_count += 1
                        audio_chunk = base64.b64decode(message.data.audio)
                        if audio_chunk and len(audio_chunk) > 0:
                            print(f"   ⚡ Chunk {chunk_count}: {len(audio_chunk)} bytes")
                            yield audio_chunk
                
                # Final flush only if client is still connected
                if not websocket or not self._is_client_disconnected(websocket):
                    await ws.flush()
                    print(f"   ✅ Direct streaming complete: {chunk_count} chunks")
                else:
                    print(f"   🔌 Client disconnected during flush - stopping at {chunk_count} chunks")
                            
        except Exception as e:
            error_msg = str(e)
            if self._is_normal_disconnection(error_msg):
                print(f"   🔌 Client disconnected during streaming: {e}")
                print(f"   ⚠️ Stopping audio generation - client no longer connected")
                return  # Stop generation if client disconnected
            else:
                print(f"   ❌ Direct stream error: {e}")
                # Only fallback if client is still connected
                if not websocket or not self._is_client_disconnected(websocket):
                    try:
                        print(f"   🔄 Fallback to fast generation")
                        audio_buffer = await self._generate_audio_single(text, language_code, speaker)
                        if audio_buffer and audio_buffer.getbuffer().nbytes > 0:
                            yield audio_buffer.getvalue()
                    except Exception as fallback_error:
                        print(f"   ❌ Fallback failed: {fallback_error}")
                        return
    
    async def _stream_audio_immediate(self, text: str, language_code: str, speaker: str, chunk_size: int, websocket=None):
        """Stream audio with immediate first chunk delivery - MAXIMUM SPEED."""
        try:
            # Check if client is still connected before starting
            if websocket and self._is_client_disconnected(websocket):
                print("   🔌 Client disconnected before immediate streaming - stopping")
                return
            
            # Split into very small chunks for immediate delivery
            chunks = self._split_text_for_immediate_streaming(text, chunk_size)
            print(f"   ⚡ Immediate streaming: {len(chunks)} chunks")
            
            if not chunks:
                return
            
            # FIRST CHUNK - IMMEDIATE DELIVERY
            first_chunk = chunks[0]
            print(f"   🎯 First chunk ({len(first_chunk)} chars) - IMMEDIATE")
            
            first_chunk_delivered = False
            async for audio_chunk in self._stream_audio_direct(first_chunk, language_code, speaker, websocket):
                # Check connection before yielding
                if websocket and self._is_client_disconnected(websocket):
                    print("   🔌 Client disconnected during first chunk - stopping")
                    return
                
                if not first_chunk_delivered:
                    print(f"   🚀 FIRST AUDIO DELIVERED!")
                    first_chunk_delivered = True
                yield audio_chunk
            
            # REMAINING CHUNKS - PARALLEL PROCESSING (only if client still connected)
            if len(chunks) > 1 and (not websocket or not self._is_client_disconnected(websocket)):
                print(f"   🔄 Processing {len(chunks)-1} remaining chunks in parallel")
                
                # Process remaining chunks in parallel
                remaining_chunks = chunks[1:]
                
                # Create parallel tasks for remaining chunks
                tasks = []
                for i, chunk in enumerate(remaining_chunks):
                    task = asyncio.create_task(
                        self._generate_chunk_fast(chunk, language_code, speaker, i+2)
                    )
                    tasks.append(task)
                
                # Yield results as they complete (order doesn't matter for audio streaming)
                for task in asyncio.as_completed(tasks):
                    # Check connection before processing each completed task
                    if websocket and self._is_client_disconnected(websocket):
                        print("   🔌 Client disconnected during parallel processing - stopping")
                        # Cancel remaining tasks
                        for remaining_task in tasks:
                            if not remaining_task.done():
                                remaining_task.cancel()
                        return
                    
                    try:
                        chunk_audio = await task
                        if chunk_audio and len(chunk_audio) > 0:
                            yield chunk_audio
                    except Exception as e:
                        print(f"   ⚠️ Parallel chunk failed: {e}")
                        continue
                        
            print(f"   ✅ Immediate streaming complete")
                            
        except Exception as e:
            error_msg = str(e)
            if self._is_normal_disconnection(error_msg):
                print(f"   🔌 Client disconnected during immediate streaming: {e}")
                return
            else:
                print(f"   ❌ Immediate streaming error: {e}")
                return
    
    async def _collect_audio_chunk(self, text: str, language_code: str, speaker: str, chunk_num: int) -> bytes:
        """Collect audio from a single chunk for parallel processing."""
        try:
            audio_buffer = await self._generate_audio_single(text, language_code, speaker)
            audio_bytes = audio_buffer.getvalue()
            if audio_bytes:
                print(f"   ✅ Chunk {chunk_num}: {len(audio_bytes)} bytes ready")
            return audio_bytes
        except Exception as e:
            print(f"   ❌ Chunk {chunk_num} failed: {e}")
            return b''
    
    def _split_text_for_streaming(self, text: str, max_chunk_size: int) -> list:
        """Split text optimized for streaming - prioritize first chunk quality."""
        chunks = []
        
        # Ensure first chunk is meaningful and complete
        words = text.split()
        if not words:
            return []
        
        # Build first chunk with complete sentences when possible
        first_chunk = ""
        remaining_text = text
        
        # Try to get a complete sentence for first chunk
        import re
        sentences = re.split(r'([.!?]+)', text)
        
        if len(sentences) >= 2:
            # Take first complete sentence(s) that fit
            for i in range(0, len(sentences) - 1, 2):
                sentence = sentences[i].strip()
                if i + 1 < len(sentences):
                    sentence += sentences[i + 1]
                
                if len(first_chunk + sentence) <= max_chunk_size:
                    first_chunk += sentence + " "
                else:
                    break
            
            if first_chunk.strip():
                chunks.append(first_chunk.strip())
                # Remove first chunk from remaining text
                remaining_text = text[len(first_chunk):].strip()
        
        # If no good first chunk found, use word-based splitting
        if not chunks:
            current_chunk = ""
            for word in words:
                if len(current_chunk + word) + 1 <= max_chunk_size:
                    current_chunk += " " + word if current_chunk else word
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                        remaining_text = text[len(current_chunk):].strip()
                    break
        
        # Split remaining text into chunks
        if remaining_text:
            remaining_chunks = self._split_text_fast(remaining_text, max_chunk_size)
            chunks.extend(remaining_chunks)
        
        return chunks
    
    def _clean_text_for_ultra_fast_streaming(self, text: str) -> str:
        """ULTRA-FAST text cleaning for immediate streaming."""
        import re
        
        # MINIMAL cleaning for maximum speed
        text = re.sub(r'[*#_`\[\]{}\\]', ' ', text)    # Remove markdown
        text = re.sub(r'\.{3,}', '.', text)            # Fix ellipsis
        text = re.sub(r'[^\w\s.,!?;:\'-]', ' ', text)  # Keep essentials only
        text = re.sub(r'\s+', ' ', text)               # Single spaces
        
        # AGGRESSIVE truncation for streaming speed
        if len(text) > 5000:  # Much smaller limit for streaming
            text = text[:4800] + "."
            print(f"   ⚡ Truncated to 4800 chars for streaming speed")
        
        return text.strip()
    
    def _split_text_for_immediate_streaming(self, text: str, max_chunk_size: int) -> list:
        """Split text for immediate first chunk delivery."""
        chunks = []
        
        # PRIORITY: Get a meaningful first chunk FAST
        words = text.split()
        if not words:
            return []
        
        # Build first chunk - prioritize speed over perfection
        first_chunk = ""
        word_count = 0
        
        for word in words:
            if len(first_chunk + " " + word) <= max_chunk_size and word_count < 100:  # Max 100 words for first chunk
                first_chunk += " " + word if first_chunk else word
                word_count += 1
            else:
                break
        
        if first_chunk:
            chunks.append(first_chunk.strip())
            
            # Split remaining text into chunks
            remaining_text = text[len(first_chunk):].strip()
            if remaining_text:
                remaining_chunks = self._split_text_fast(remaining_text, max_chunk_size)
                chunks.extend(remaining_chunks)
        else:
            # Fallback: just split by words
            chunks = self._split_text_fast(text, max_chunk_size)
        
        return chunks
    
    async def _generate_chunk_fast(self, text: str, language_code: str, speaker: str, chunk_num: int) -> bytes:
        """Generate audio chunk as fast as possible."""
        try:
            print(f"   🔄 Chunk {chunk_num}: {len(text)} chars")
            audio_buffer = await self._generate_audio_single(text, language_code, speaker)
            audio_bytes = audio_buffer.getvalue()
            if audio_bytes:
                print(f"   ✅ Chunk {chunk_num}: {len(audio_bytes)} bytes ready")
            return audio_bytes
        except Exception as e:
            print(f"   ❌ Chunk {chunk_num} failed: {e}")
            return b''
    
    def _clean_text_for_tts_fast(self, text: str) -> str:
        """Fast text cleaning optimized for speed and TTS quality."""
        import re
        
        # Quick and aggressive cleaning for speed
        text = re.sub(r'[*#_`\[\]{}\\]', ' ', text)    # Remove markdown chars
        text = re.sub(r'\.{2,}', '.', text)            # Replace multiple dots
        text = re.sub(r'--+', ' ', text)               # Replace dashes
        text = re.sub(r'[^\w\s.,!?;:\'-]', ' ', text)  # Keep only essential chars
        text = re.sub(r'\s+', ' ', text)               # Single spaces
        
        # Truncate aggressively if too long for speed
        if len(text) > 8000:  # Hard limit for speed
            text = text[:7500] + "."
            print(f"   Truncated to 7500 chars for speed")
        
        return text.strip()
    
    def _clean_text_for_tts(self, text: str) -> str:
        """Clean text to make it more suitable for TTS."""
        import re
        
        # Remove markdown formatting
        text = re.sub(r'\*\*(.*?)\*\*', r'\\1', text)  # Remove bold
        text = re.sub(r'\*(.*?)\*', r'\\1', text)      # Remove italic
        text = re.sub(r'#{1,6}\s*', '', text)          # Remove headers
        
        # Handle ellipsis and multiple dots properly for TTS
        text = re.sub(r'\.{3,}', ' pause ', text)      # Replace ellipsis with pause
        text = re.sub(r'\.{2}', ' pause ', text)       # Replace double dots with pause
        
        # Handle other punctuation that might be spoken literally
        text = re.sub(r'--+', ' pause ', text)         # Replace dashes with pause
        text = re.sub(r'_+', ' ', text)                # Replace underscores with space
        text = re.sub(r'\*+', ' ', text)               # Remove remaining asterisks
        
        # Clean up special characters that cause TTS issues
        text = re.sub(r'[^\w\s.,!?;:\'-]', ' ', text)  # Replace problematic chars with space
        
        # Replace multiple spaces with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Clean up multiple punctuation
        text = re.sub(r'[.,!?;:]{2,}', '.', text)      # Replace multiple punctuation with period
        
        return text.strip()
    
    def _intelligent_truncate(self, text: str, max_length: int) -> str:
        """Intelligently truncate text preserving key content and natural flow."""
        if len(text) <= max_length:
            return text
        
        import re
        
        # First, try to get the most important content from the beginning
        # This preserves the main topic and context
        target_length = max_length - 50  # Leave buffer for proper ending
        
        # Split into paragraphs first
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        if paragraphs:
            # Take complete paragraphs that fit
            truncated = ""
            for paragraph in paragraphs:
                if len(truncated + paragraph) <= target_length:
                    truncated += paragraph + "\n\n"
                else:
                    # If this paragraph doesn't fit, try to fit part of it
                    remaining_space = target_length - len(truncated)
                    if remaining_space > 100:  # Only if we have meaningful space
                        partial = self._truncate_paragraph(paragraph, remaining_space)
                        if partial:
                            truncated += partial
                    break
        else:
            # No paragraph breaks, work with sentences
            sentences = re.split(r'([.!?]+)', text)
            truncated = ""
            
            for i in range(0, len(sentences) - 1, 2):
                sentence = sentences[i].strip()
                if i + 1 < len(sentences):
                    sentence += sentences[i + 1]
                
                if len(truncated + sentence) <= target_length:
                    truncated += sentence + " "
                else:
                    break
        
        # Clean up and add proper ending
        truncated = truncated.strip()
        if not truncated:
            # Fallback: just take first part at word boundary
            words = text.split()
            truncated = ""
            for word in words:
                if len(truncated + word) <= target_length:
                    truncated += word + " "
                else:
                    break
            truncated = truncated.strip()
        
        # Ensure proper ending
        if truncated and not truncated.endswith(('.', '!', '?')):
            # Remove incomplete sentence at the end
            last_sentence_end = max(
                truncated.rfind('.'),
                truncated.rfind('!'),
                truncated.rfind('?')
            )
            if last_sentence_end > len(truncated) * 0.7:  # Only if we don't lose too much
                truncated = truncated[:last_sentence_end + 1]
            else:
                truncated += "."
        
        return truncated
    
    def _truncate_paragraph(self, paragraph: str, max_length: int) -> str:
        """Truncate a single paragraph at sentence boundary."""
        import re
        sentences = re.split(r'([.!?]+)', paragraph)
        
        truncated = ""
        for i in range(0, len(sentences) - 1, 2):
            sentence = sentences[i].strip()
            if i + 1 < len(sentences):
                sentence += sentences[i + 1]
            
            if len(truncated + sentence) <= max_length - 10:
                truncated += sentence + " "
            else:
                break
        
        return truncated.strip()
    
    async def _generate_audio_single(self, text: str, language_code: str, speaker: str) -> io.BytesIO:
        """Generate audio for text with optimized streaming for speed."""
        try:
            # Reduced logging for speed
            async with self.async_client.text_to_speech_streaming.connect(model="bulbul:v2") as ws:
                await ws.configure(target_language_code=language_code, speaker=speaker)
                await ws.convert(text)
                await ws.flush()
                
                # Fast audio collection with minimal logging
                full_audio_bytes = b''
                async for message in ws:
                    if isinstance(message, AudioOutput):
                        audio_chunk = base64.b64decode(message.data.audio)
                        full_audio_bytes += audio_chunk
                
                return io.BytesIO(full_audio_bytes)
                
        except Exception as e:
            print(f"   ❌ TTS error: {e}")
            return io.BytesIO()
    
    async def _generate_audio_parallel_chunks(self, text: str, language_code: str, speaker: str, chunk_size: int) -> io.BytesIO:
        """Generate audio using parallel processing for maximum speed."""
        try:
            print(f"   Parallel processing with {chunk_size} char chunks")
            
            # Split into smaller chunks for faster parallel processing
            chunks = self._split_text_fast(text, chunk_size)
            print(f"   Processing {len(chunks)} chunks in parallel")
            
            # Limit concurrent connections to avoid overwhelming the API
            max_concurrent = min(4, len(chunks))  # Max 4 parallel connections
            
            # Process chunks in parallel batches
            all_audio_bytes = b''
            
            for i in range(0, len(chunks), max_concurrent):
                batch = chunks[i:i + max_concurrent]
                print(f"   Batch {i//max_concurrent + 1}: processing {len(batch)} chunks")
                
                # Create tasks for parallel processing
                tasks = []
                for j, chunk in enumerate(batch):
                    task = asyncio.create_task(
                        self._generate_audio_single(chunk, language_code, speaker)
                    )
                    tasks.append(task)
                
                # Wait for all tasks in this batch to complete
                try:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Combine results in order
                    for j, result in enumerate(results):
                        if isinstance(result, Exception):
                            print(f"   ⚠️ Chunk {i+j+1} failed: {result}")
                            continue
                        
                        if result and result.getbuffer().nbytes > 0:
                            all_audio_bytes += result.getvalue()
                            print(f"   ✅ Chunk {i+j+1}: {result.getbuffer().nbytes} bytes")
                        else:
                            print(f"   ⚠️ Chunk {i+j+1}: No audio generated")
                
                except Exception as e:
                    print(f"   ❌ Batch {i//max_concurrent + 1} error: {e}")
                    continue
            
            print(f"✅ Parallel TTS complete: {len(all_audio_bytes)} bytes")
            return io.BytesIO(all_audio_bytes)
            
        except Exception as e:
            print(f"❌ Error in parallel processing: {e}")
            return io.BytesIO()
    
    def _split_text_fast(self, text: str, max_chunk_size: int) -> list:
        """Fast text splitting optimized for speed over perfect boundaries."""
        chunks = []
        
        # Simple splitting for speed - prioritize speed over perfect sentence boundaries
        words = text.split()
        current_chunk = ""
        
        for word in words:
            if len(current_chunk) + len(word) + 1 <= max_chunk_size:
                current_chunk += " " + word if current_chunk else word
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = word
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _split_text_into_smart_chunks(self, text: str, max_chunk_size: int) -> list:
        """Split text into chunks that preserve sentence boundaries and context."""
        import re
        
        # First split by paragraphs to maintain structure
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            # If paragraph is too long, split it by sentences
            if len(paragraph) > max_chunk_size:
                sentences = self._split_into_sentences(paragraph)
                
                for sentence in sentences:
                    # If adding this sentence exceeds limit, start new chunk
                    if current_chunk and len(current_chunk) + len(sentence) + 2 > max_chunk_size:
                        if current_chunk.strip():
                            chunks.append(current_chunk.strip())
                        current_chunk = sentence
                    else:
                        if current_chunk:
                            current_chunk += " " + sentence
                        else:
                            current_chunk = sentence
            else:
                # If adding this paragraph exceeds limit, start new chunk
                if current_chunk and len(current_chunk) + len(paragraph) + 2 > max_chunk_size:
                    if current_chunk.strip():
                        chunks.append(current_chunk.strip())
                    current_chunk = paragraph
                else:
                    if current_chunk:
                        current_chunk += "\n\n" + paragraph
                    else:
                        current_chunk = paragraph
        
        # Add the last chunk if it has content
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _is_client_disconnected(self, websocket) -> bool:
        """Check if WebSocket client is disconnected."""
        return not is_client_connected(websocket)
    
    def _is_normal_disconnection(self, error_msg: str) -> bool:
        """Check if error message indicates a normal client disconnection."""
        try:
            # Try to create an exception from the error message to use our utility
            if "1000" in str(error_msg) or "1001" in str(error_msg):
                return True
            
            # Check for common disconnection phrases
            error_msg = str(error_msg).lower()
            disconnection_phrases = [
                "connection closed",
                "client disconnected", 
                "going away",
                "connection lost"
            ]
            
            return any(phrase in error_msg for phrase in disconnection_phrases)
        except Exception:
            return False

    def _split_into_sentences(self, text: str) -> list:
        """Split text into sentences preserving punctuation."""
        import re
        
        # Split on sentence endings, keeping the punctuation
        sentences = re.split(r'([.!?]+)', text)
        
        # Recombine sentences with their punctuation
        result = []
        for i in range(0, len(sentences) - 1, 2):
            sentence = sentences[i].strip()
            if i + 1 < len(sentences):
                sentence += sentences[i + 1]
            if sentence.strip():
                result.append(sentence.strip())
        
        return result
    
