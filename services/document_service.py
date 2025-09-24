"""
Document Service - Handles PDF processing and course generation
"""

import os
import shutil
import json
import logging
from typing import List
from fastapi import UploadFile
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

import config

class DocumentService:
    """Service for processing documents and generating courses."""
    
    def __init__(self):
        self.document_processor = DocumentProcessor()
    
    async def process_pdfs_and_generate_course(self, pdf_files: List[UploadFile], course_title: str = None):
        """Process uploaded PDF files and generate course content."""
        return self.process_uploaded_pdfs(pdf_files, course_title)
    
    def process_uploaded_pdfs(self, pdf_files: List[UploadFile], course_title: str = None):
        """Process uploaded PDF files and generate course content."""
        try:
            # Clear and prepare documents directory
            if os.path.exists(config.DOCUMENTS_DIR):
                shutil.rmtree(config.DOCUMENTS_DIR)
            os.makedirs(config.DOCUMENTS_DIR, exist_ok=True)
            
            # Save uploaded PDFs
            saved_files = []
            for pdf_file in pdf_files:
                if not pdf_file.filename.lower().endswith('.pdf'):
                    raise ValueError(f"File {pdf_file.filename} is not a PDF")
                
                file_path = os.path.join(config.DOCUMENTS_DIR, pdf_file.filename)
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(pdf_file.file, buffer)
                saved_files.append(file_path)
                logging.info(f"Saved uploaded PDF: {pdf_file.filename}")
            
            # Import processing modules
            from core.course_generator import CourseGenerator
            from processors.pdf_extractor import PDFExtractor
            from processors.text_chunker import TextChunker
            from core.vectorizer import Vectorizer
            
            # Process documents
            logging.info("STEP 1: Extracting text from PDFs...")
            # Use DocumentProcessor method instead of direct PDFExtractor call
            raw_docs = self.document_processor.extract_text_from_directory(config.DOCUMENTS_DIR)
            if not raw_docs:
                raise Exception("No text could be extracted from uploaded documents")

            logging.info("STEP 2: Chunking documents...")
            # Use DocumentProcessor method for chunking too
            doc_chunks = self.document_processor.chunk_documents(raw_docs)
            if not doc_chunks:
                raise Exception("No chunks could be created from documents")

            logging.info("STEP 3: Creating vector store...")
            vectorizer = Vectorizer(embedding_model=config.EMBEDDING_MODEL_NAME, api_key=config.OPENAI_API_KEY)
            vector_store = vectorizer.create_vector_store(doc_chunks)
            if not vector_store:
                raise Exception("Vector store could not be created")
            
            # Save vector store - using versioned approach instead of deletion
            import uuid
            import datetime
            
            # Create a timestamped backup directory if old one exists
            if os.path.exists(config.VECTORSTORE_DIR):
                backup_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_dir = f"{config.VECTORSTORE_DIR}_backup_{backup_timestamp}"
                try:
                    # Try to rename instead of delete - much safer on Windows
                    os.rename(config.VECTORSTORE_DIR, backup_dir)
                    logging.info(f"Previous vectorstore backed up to {backup_dir}")
                except Exception as e:
                    # If rename fails, use a new directory with UUID
                    new_uuid = str(uuid.uuid4())[:8]
                    new_vector_dir = f"{config.VECTORSTORE_DIR}_{new_uuid}"
                    logging.warning(f"Could not backup old vectorstore: {e}, using new directory: {new_vector_dir}")
                    config.VECTORSTORE_DIR = new_vector_dir
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(config.VECTORSTORE_DIR), exist_ok=True)
            
            # Now save the vector store to clean directory
            vectorizer.save_vector_store(vector_store, config.VECTORSTORE_DIR)

            logging.info("STEP 4: Generating course...")
            course_generator = CourseGenerator()
            
            # Use retriever and immediately dispose of vector_store to prevent locks
            try:
                retriever = vector_store.as_retriever()
                final_course = course_generator.generate_course(doc_chunks, retriever, course_title)
            finally:
                # Clean up vector store connection to prevent file locks
                if hasattr(vector_store, '_client') and vector_store._client:
                    try:
                        vector_store._client.reset()
                        logging.info("   Vector store client connection cleaned up")
                    except Exception as cleanup_error:
                        logging.warning(f"   Vector store cleanup failed: {cleanup_error}")
                vector_store = None  # Release reference
            
            if not final_course:
                raise Exception("Course generation failed")

            # Save course output - append to existing courses
            logging.info("STEP 5: Saving course...")
            os.makedirs(config.COURSES_DIR, exist_ok=True)
            
             # Convert course to dictionary and validate structure
            course_dict = self._validate_and_prepare_course(final_course, course_title)
            
            # Load existing courses and append new course
            existing_courses = self._load_existing_courses()
            next_course_id = self._get_next_course_id(existing_courses)
            
            # Ensure unique course title
            course_dict = self._ensure_unique_title(course_dict, existing_courses)
            
           # Assing course id   
            course_dict['course_id'] = next_course_id
            
            # Append new course to existing courses
            existing_courses.append(course_dict)
            
            self._save_courses_to_file(existing_courses)
            
            logging.info(f"Course generation completed successfully! Course ID: {next_course_id}")
            logging.info(f"Total courses in database: {len(existing_courses)}")
            return course_dict
             
        except Exception as e:
            logging.error(f"Error processing PDFs: {e}")
            # Ensure cleanup on error to prevent file locks
            try:
                import gc
                gc.collect()
            except:
                pass
            raise e
    
    def _validate_and_prepare_course(self, course, course_title: str = None):
        """Validate and prepare course data for saving."""
        try:
            # Convert course to dictionary if it's a Pydantic model
            if hasattr(course, 'dict'):
                course_dict = course.dict()
            elif isinstance(course, dict):
                course_dict = course.copy()
            else:
                raise ValueError("Invalid course format")
            
            # Validate required fields
            required_fields = ['course_title', 'modules']
            for field in required_fields:
                if field not in course_dict:
                    raise ValueError(f"Missing required field: {field}")
            
            # Override title if provided
            if course_title:
                course_dict['course_title'] = course_title
            
            # Validate modules structure
            if not isinstance(course_dict['modules'], list):
                raise ValueError("Modules must be a list")
            
            for i, module in enumerate(course_dict['modules']):
                if not isinstance(module, dict):
                    raise ValueError(f"Module {i} must be a dictionary")
                
                # Ensure required module fields
                if 'week' not in module:
                    module['week'] = i + 1
                if 'title' not in module:
                    module['title'] = f"Module {i + 1}"
                if 'sub_topics' not in module:
                    module['sub_topics'] = []
                
                # Validate sub_topics
                if not isinstance(module['sub_topics'], list):
                    module['sub_topics'] = []
                
                for j, sub_topic in enumerate(module['sub_topics']):
                    if not isinstance(sub_topic, dict):
                        continue
                    if 'title' not in sub_topic:
                        sub_topic['title'] = f"Topic {j + 1}"
                    if 'content' not in sub_topic:
                        sub_topic['content'] = ""
            
            logging.info(f"Course validation successful: {course_dict['course_title']}")
            logging.info(f"Course has {len(course_dict['modules'])} modules")
            return course_dict
            
        except Exception as e:
            logging.error(f"Course validation failed: {e}")
            raise ValueError(f"Course validation failed: {e}")
    
    def _load_existing_courses(self):
        """Load existing courses from file and return as list."""
        existing_courses = []
        
        if os.path.exists(config.OUTPUT_JSON_PATH):
            try:
                with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                
                # Handle both single course and multi-course formats
                if isinstance(existing_data, dict) and 'course_title' in existing_data:
                    # Single course format - convert to list
                    existing_courses = [existing_data]
                    logging.info("Loaded single course format, converting to multi-course format")
                elif isinstance(existing_data, list):
                    # Multi-course format
                    existing_courses = existing_data
                    logging.info(f"Loaded {len(existing_courses)} existing courses")
                else:
                    logging.warning("Invalid course data format, starting fresh")
                    existing_courses = []
                    
            except Exception as e:
                logging.warning(f"Could not load existing courses: {e}")
                existing_courses = []
        else:
            logging.info("No existing course file found, starting fresh")
        
        return existing_courses
    
    def _get_next_course_id(self, existing_courses):
        """Get the next available course ID."""
        if not existing_courses:
            return 1
        
        # Find the maximum course ID
        max_id = 0
        for course in existing_courses:
            course_id = course.get('course_id', 0)
            if isinstance(course_id, int) and course_id > max_id:
                max_id = course_id
        
        return max_id + 1
    
    def _ensure_unique_title(self, course_dict, existing_courses):
        """Ensure the course title is unique by appending a number if necessary."""
        original_title = course_dict['course_title']
        title = original_title
        counter = 1
        
        # Check if title already exists
        existing_titles = [course.get('course_title', '') for course in existing_courses]
        
        while title in existing_titles:
            counter += 1
            title = f"{original_title} ({counter})"
        
        if title != original_title:
            logging.info(f"Course title changed from '{original_title}' to '{title}' to ensure uniqueness")
            course_dict['course_title'] = title
        
        return course_dict
    
    def _save_courses_to_file(self, courses):
        """Save courses to file with proper formatting and validation."""
        try:
            # Validate that courses is a list
            if not isinstance(courses, list):
                raise ValueError("Courses must be a list")
            
            # Validate each course has required fields
            for i, course in enumerate(courses):
                if not isinstance(course, dict):
                    raise ValueError(f"Course {i} must be a dictionary")
                if 'course_id' not in course:
                    raise ValueError(f"Course {i} missing course_id")
                if 'course_title' not in course:
                    raise ValueError(f"Course {i} missing course_title")
                if 'modules' not in course:
                    raise ValueError(f"Course {i} missing modules")
            
            # Always save as array format for consistency
            with open(config.OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump(courses, f, indent=4, ensure_ascii=False)
            
            logging.info(f"Successfully saved {len(courses)} courses to {config.OUTPUT_JSON_PATH}")
            
        except Exception as e:
            logging.error(f"Failed to save courses: {e}")
            raise ValueError(f"Failed to save courses: {e}")


class DocumentProcessor:
    """Helper class for document processing operations."""
    
    def __init__(self):
        from processors.pdf_extractor import PDFExtractor
        from processors.text_chunker import TextChunker
        
        self.embeddings = OpenAIEmbeddings(
            model=config.EMBEDDING_MODEL_NAME, 
            openai_api_key=config.OPENAI_API_KEY
        )
        self.pdf_extractor = PDFExtractor()
        self.text_chunker = TextChunker(chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP)
        
    def extract_text_from_directory(self, directory_path: str):
        """Extract text from all PDFs in a directory using PDFExtractor."""
        return self.pdf_extractor.extract_text_from_directory(directory_path)
        
    def chunk_documents(self, documents):
        """Split documents into chunks using TextChunker."""
        # Initialize TextChunker with config values if not already done
        if not hasattr(self, 'text_chunker') or self.text_chunker is None:
            self.text_chunker = TextChunker(chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP)
            
        return self.text_chunker.chunk_documents(documents)
    
    def get_vectorstore(self, recreate: bool = False, documents: List[Document] = None):
        """Get or create vectorstore with proper cleanup handling."""
        import time
        import gc
        from pathlib import Path
        
        # Aggressive cleanup to prevent locks
        self._cleanup_existing_connections()
        gc.collect()
        time.sleep(0.2)
        
        if recreate:
            chroma_path = Path(config.CHROMA_DB_PATH)
            if chroma_path.exists():
                # Aggressive retry removal with per-file handling for Windows
                max_attempts = 5
                for attempt in range(max_attempts):
                    try:
                        # Try different approaches with increasing aggressiveness
                        if attempt == 0:
                            # Standard removal first
                            shutil.rmtree(chroma_path)
                            break
                        elif attempt == 1:
                            # Short delay and retry
                            time.sleep(1)
                            shutil.rmtree(chroma_path)
                            break
                        elif attempt >= 2:
                            # File-by-file deletion as last resort
                            self._safe_remove_directory(chroma_path)
                            break
                    except PermissionError as e:
                        if attempt == max_attempts - 1:
                            logging.warning(f"Could not fully remove ChromaDB directory after {max_attempts} attempts. Some files may remain: {e}")
                        else:
                            logging.debug(f"Removal attempt {attempt+1} failed, retrying with different approach: {e}")
                        time.sleep(0.5 * (attempt + 1))  # Increasing delay with each retry
                    except Exception as e:
                        logging.warning(f"Error while removing ChromaDB directory: {e}")
                        break
                
            # Create parent directories if they don't exist
            chroma_path.parent.mkdir(parents=True, exist_ok=True)
                    
            if not documents:
                raise ValueError("Documents must be provided when recreating vectorstore")
                
            try:
                # Create fresh vectorstore with updated parameters for new ChromaDB
                vectorstore = Chroma.from_documents(
                    documents=documents,
                    embedding=self.embeddings,
                    persist_directory=str(chroma_path),
                    collection_name=config.CHROMA_COLLECTION_NAME,
                    collection_metadata={"hnsw:space": "cosine"}
                )
                return vectorstore
            except Exception as e:
                logging.error(f"Failed to create ChromaDB: {e}")
                raise
        else:
            if not os.path.exists(config.CHROMA_DB_PATH):
                return None
                
            try:
                # Open existing with explicit client settings
                # Updated ChromaDB client creation
                vectorstore = Chroma(
                    persist_directory=config.CHROMA_DB_PATH,
                    embedding_function=self.embeddings,
                    collection_name=config.CHROMA_COLLECTION_NAME,
                    collection_metadata={"hnsw:space": "cosine"}
                )
                return vectorstore
            except Exception as e:
                logging.error(f"Failed to open ChromaDB: {e}")
                raise
    
    def create_vectorstore_from_documents(self, documents: List[Document]):
        """Create a new vectorstore from documents with proper cleanup."""
        # Clean up any existing connections first
        self._cleanup_existing_connections()
        
        # Updated ChromaDB client creation
        return Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings,
            persist_directory=config.CHROMA_DB_PATH,
            collection_name=config.CHROMA_COLLECTION_NAME,
            collection_metadata={"hnsw:space": "cosine"}
        )
    
    def _cleanup_existing_connections(self):
        """Clean up any existing ChromaDB connections to prevent file locks."""
        try:
            # Force garbage collection to clean up connections
            import gc
            gc.collect()
            
            # Small delay to ensure cleanup
            import time
            time.sleep(0.1)
            
            logging.debug("   Cleaned up existing connections")
        except Exception as e:
            logging.debug(f"   Connection cleanup warning: {e}")
    
    def _safe_remove_directory(self, directory_path):
        """Safely remove a directory file by file - last resort for locked files on Windows."""
        from pathlib import Path
        import time
        import gc
        
        directory = Path(directory_path)
        if not directory.exists():
            return
            
        # Force garbage collection to release file handles
        gc.collect()
        time.sleep(0.5)
        
        # First try to remove files
        for item in directory.glob('**/*'):
            if item.is_file():
                try:
                    item.unlink()
                    logging.debug(f"Removed file: {item}")
                except Exception as e:
                    logging.debug(f"Could not remove file {item}: {e}")
        
        # Then try to remove empty directories from bottom up
        for item in sorted([d for d in directory.glob('**/*') if d.is_dir()], reverse=True):
            try:
                item.rmdir()
                logging.debug(f"Removed directory: {item}")
            except Exception as e:
                logging.debug(f"Could not remove directory {item}: {e}")
        
        # Finally try to remove the root directory
        try:
            directory.rmdir()
            logging.info(f"Removed directory: {directory}")
        except Exception as e:
            logging.warning(f"Could not remove root directory {directory}: {e}")
    
    def dispose_vectorstore(self, vectorstore):
        """Properly dispose of a vectorstore to prevent file locks."""
        if not vectorstore:
            return
            
        try:
            # Try to reset the client connection if it exists
            if hasattr(vectorstore, '_client') and vectorstore._client:
                vectorstore._client.reset()
                logging.info("   ChromaDB client connection disposed")
        except Exception as e:
            logging.warning(f"   Vectorstore disposal warning: {e}")
        finally:
            # Force cleanup
            vectorstore = None
            import gc
            gc.collect()
    
    def split_documents(self, documents: List[Document]) -> List[Document]:
        """Split documents into chunks."""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.MAX_CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
        )
        return text_splitter.split_documents(documents)
    
    def load_course_content_as_documents(self, course_json_path: str) -> List[Document]:
        """Load generated course content from JSON file and convert to Document objects."""
        if not os.path.exists(course_json_path):
            return []
        
        try:
            with open(course_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            all_documents = []
            
            # Handle both single course and multi-course formats
            if isinstance(data, dict) and 'course_title' in data:
                # Single course format
                all_documents.extend(self.extract_course_documents(data))
            elif isinstance(data, list):
                # Multi-course format - process all courses
                for course_data in data:
                    if isinstance(course_data, dict):
                        all_documents.extend(self.extract_course_documents(course_data))
            else:
                print("⚠️ Invalid course data format")
                return []
            
            return all_documents            
        except Exception as e:
            print(f"Error loading course content: {e}")
            return []
    
    def extract_course_documents(self, course_data: dict) -> List[Document]:
        """Extract documents from course data."""
        documents = []
        
        # Add course title and overview
        if course_data.get("course_title"):
            documents.append(Document(
                page_content=f"Course Title: {course_data['course_title']}",
                metadata={"source": "course_overview", "type": "title"}
            ))
        
        # Add module and sub-topic content
        for module in course_data.get("modules", []):
            module_content = f"Week {module.get('week', 'N/A')}: {module.get('title', 'Untitled Module')}"
            documents.append(Document(
                page_content=module_content,
                metadata={"source": "course_module", "week": module.get('week'), "type": "module"}
            ))
            
            for sub_topic in module.get("sub_topics", []):
                if sub_topic.get("content"):
                    sub_topic_content = f"Topic: {sub_topic.get('title', 'Untitled Topic')}\n\n{sub_topic['content']}"
                    documents.append(Document(
                        page_content=sub_topic_content,
                        metadata={
                            "source": "course_content", 
                            "week": module.get('week'),
                            "topic": sub_topic.get('title'),
                            "type": "content"
                        }
                    ))
        
        return documents