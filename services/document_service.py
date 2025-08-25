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
from langchain_community.vectorstores import Chroma

import config

class DocumentService:
    """Service for processing documents and generating courses."""
    
    def __init__(self):
        self.document_processor = DocumentProcessor()
    
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
            extractor = PDFExtractor()
            raw_docs = extractor.extract_text_from_directory(config.DOCUMENTS_DIR)
            if not raw_docs:
                raise Exception("No text could be extracted from uploaded documents")

            logging.info("STEP 2: Chunking documents...")
            chunker = TextChunker(chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP)
            doc_chunks = chunker.chunk_documents(raw_docs)
            if not doc_chunks:
                raise Exception("No chunks could be created from documents")

            logging.info("STEP 3: Creating vector store...")
            vectorizer = Vectorizer(embedding_model=config.EMBEDDING_MODEL_NAME, api_key=config.OPENAI_API_KEY)
            vector_store = vectorizer.create_vector_store(doc_chunks)
            if not vector_store:
                raise Exception("Vector store could not be created")
            
            # Save vector store
            if os.path.exists(config.VECTORSTORE_DIR):
                shutil.rmtree(config.VECTORSTORE_DIR)
            vectorizer.save_vector_store(vector_store, config.VECTORSTORE_DIR)

            logging.info("STEP 4: Generating course...")
            course_generator = CourseGenerator()
            final_course = course_generator.generate_course(doc_chunks, vector_store.as_retriever(), course_title)
            
            if not final_course:
                raise Exception("Course generation failed")

            # Save course output
            logging.info("STEP 5: Saving course...")
            os.makedirs(config.COURSES_DIR, exist_ok=True)
            with open(config.OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump(final_course.dict(), f, indent=4, ensure_ascii=False)
            
            logging.info("Course generation completed successfully!")
            return final_course.dict()
            
        except Exception as e:
            logging.error(f"Error processing PDFs: {e}")
            raise e

class DocumentProcessor:
    """Helper class for document processing operations."""
    
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            model=config.EMBEDDING_MODEL_NAME, 
            openai_api_key=config.OPENAI_API_KEY
        )
    
    def get_vectorstore(self, recreate: bool = False, documents: List[Document] = None):
        """Get or create vectorstore."""
        if recreate:
            if os.path.exists(config.CHROMA_DB_PATH):
                shutil.rmtree(config.CHROMA_DB_PATH)
            if not documents:
                raise ValueError("Documents must be provided when recreating vectorstore")
            return Chroma.from_documents(
                documents=documents,
                embedding=self.embeddings,
                persist_directory=config.CHROMA_DB_PATH,
                collection_name=config.CHROMA_COLLECTION_NAME
            )
        else:
            if not os.path.exists(config.CHROMA_DB_PATH):
                return None
            return Chroma(
                persist_directory=config.CHROMA_DB_PATH,
                embedding_function=self.embeddings,
                collection_name=config.CHROMA_COLLECTION_NAME
            )
    
    def create_vectorstore_from_documents(self, documents: List[Document]):
        """Create a new vectorstore from documents."""
        return Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings,
            persist_directory=config.CHROMA_DB_PATH,
            collection_name=config.CHROMA_COLLECTION_NAME
        )
    
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
                course_data = json.load(f)
            
            return self.extract_course_documents(course_data)
            
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