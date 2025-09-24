"""
Vectorizer - Handles vector embeddings and vector store operations
"""

import os
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from typing import List
import logging

class Vectorizer:
    """Handles the creation, saving, and loading of vector embeddings and the vector store."""

    def __init__(self, embedding_model: str, api_key: str):
        self.embeddings = OpenAIEmbeddings(model=embedding_model, openai_api_key=api_key)

    def create_vector_store(self, chunks: List[Document]):
        """Creates a FAISS vector store from a list of document chunks."""
        if not chunks:
            logging.error("Cannot create vector store: No chunks provided")
            return None
            
        logging.info("Creating new vector store from chunks...")
        try:
            vector_store = FAISS.from_documents(chunks, self.embeddings)
            logging.info("Vector store created successfully")
            return vector_store
        except Exception as e:
            logging.error(f"Failed to create vector store: {e}")
            return None

    def save_vector_store(self, vector_store, path: str):
        """Saves the FAISS vector store to a local path with Windows file lock handling."""
        if not vector_store:
            logging.error("Cannot save: Invalid vector store provided")
            return
        
        # CRITICAL: For FAISS vector stores, we need to manually detach any resources
        # that might cause file locks before saving
        if hasattr(vector_store, 'docstore'):
            # Force docstore to release resources 
            if hasattr(vector_store.docstore, '_dict'):
                # Make copy of keys to avoid modification during iteration
                keys = list(vector_store.docstore._dict.keys())
                for key in keys:
                    # Clean any potential file handles in document content
                    if hasattr(vector_store.docstore._dict[key], 'page_content'):
                        vector_store.docstore._dict[key].page_content = \
                            str(vector_store.docstore._dict[key].page_content)
            
        import time
        import gc
        max_attempts = 3
        attempt = 0
        
        while attempt < max_attempts:
            attempt += 1
            try:
                # First ensure vector store is properly persisted and flushed
                if hasattr(vector_store, 'persist'):
                    try:
                        vector_store.persist()
                    except Exception as persist_error:
                        logging.warning(f"Vector store persist warning (non-fatal): {persist_error}")
                
                # Double garbage collection to release handles
                gc.collect()
                time.sleep(0.5)  # Critical pause to let OS release locks
                gc.collect()  # Second collection pass
                
                # Create directory and save
                os.makedirs(path, exist_ok=True)
                
                # CRITICAL: On Windows, we need to properly disconnect before saving
                # This is a workaround for the file lock issue
                if hasattr(vector_store, '_client') and vector_store._client:
                    try:
                        # Try to disconnect any client connections
                        if hasattr(vector_store._client, '_conn'):
                            try:
                                vector_store._client._conn.close()
                            except:
                                pass
                    except Exception as client_error:
                        logging.warning(f"Client cleanup warning: {client_error}")
                
                # Now save
                vector_store.save_local(path)
                logging.info(f"Vector store saved successfully to {path}")
                return
                
            except PermissionError as pe:
                if attempt < max_attempts:
                    wait_time = 2 * attempt  # Stronger progressive backoff
                    logging.warning(f"File access error, retrying in {wait_time}s: {pe}")
                    time.sleep(wait_time)
                    # Force more GC
                    gc.collect()
                else:
                    logging.error(f"Failed to save vector store after {max_attempts} attempts: {pe}")
                    raise
            except Exception as e:
                logging.error(f"Failed to save vector store: {e}")
                raise

    @staticmethod
    def load_vector_store(path: str, embeddings):
        """Loads a FAISS vector store from a local path."""
        if not os.path.exists(path):
            logging.error(f"Cannot load vector store: Path does not exist at {path}")
            return None
        try:
            vector_store = FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)
            logging.info(f"Vector store loaded successfully from {path}")
            return vector_store
        except Exception as e:
            logging.error(f"Failed to load vector store: {e}")
            return None