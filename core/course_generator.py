"""
Course Generator - Handles curriculum and content generation
"""

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_core.documents import Document
from typing import List
import logging
import config
from models.schemas import CourseLMS

class CourseGenerator:
    """Generates complete courses with curriculum and content."""
    
    def __init__(self):
        self.curriculum_model = ChatOpenAI(
            model=config.CURRICULUM_GENERATION_MODEL, 
            temperature=0.2, 
            openai_api_key=config.OPENAI_API_KEY
        )
        self.content_model = ChatOpenAI(
            model=config.CONTENT_GENERATION_MODEL, 
            temperature=0.5, 
            openai_api_key=config.OPENAI_API_KEY
        )
        self.curriculum_parser = JsonOutputParser(pydantic_object=CourseLMS)
        self.content_parser = StrOutputParser()
    
    def generate_course(self, documents: List[Document], retriever, course_title: str = None) -> CourseLMS:
        """Generate a complete course with curriculum and content."""
        try:
            # Step 1: Generate curriculum structure
            logging.info("Generating curriculum structure...")
            curriculum = self._generate_curriculum(documents, course_title)
            
            if not curriculum:
                raise Exception("Curriculum generation failed")
            
            # Step 2: Generate content for each topic
            logging.info("Generating detailed content...")
            final_course = self._generate_content(curriculum, retriever)
            
            return final_course
            
        except Exception as e:
            logging.error(f"Course generation failed: {e}")
            raise e
    
    def _generate_curriculum(self, documents: List[Document], course_title: str = None) -> CourseLMS:
        """Generate the curriculum structure with intelligent chunking for large documents."""
        if not documents:
            logging.error("Cannot generate curriculum: No documents provided")
            return None
            
        # Calculate approximate tokens for each document
        def estimate_tokens(text):
            # Rough approximation: 1 token ≈ 4 characters for English text
            return len(text) // 4
        
        # Smart document sampling to stay within token limits
        total_tokens = 0
        max_tokens = 100000  # Keep safely under the 128K limit
        selected_docs = []
        sampling_rate = 1.0
        
        # First, count total estimated tokens
        total_estimated = sum(estimate_tokens(doc.page_content) for doc in documents)
        logging.info(f"Estimated total tokens in all documents: {total_estimated}")
        
        # If we're over the limit, we need to sample or truncate
        if total_estimated > max_tokens:
            # Determine sampling rate to stay under limit
            sampling_rate = max_tokens / total_estimated
            logging.info(f"Using sampling rate of {sampling_rate:.2f} to reduce token count")
            
        # Smart document processing strategies
        if len(documents) > 100 or total_estimated > max_tokens * 1.5:
            # Strategy 1: For very large documents, extract summaries and key sections
            logging.info(f"Document set too large ({len(documents)} chunks). Using intelligent sampling...")
            
            # Group documents by similarity or source if possible
            if all(hasattr(doc, 'metadata') and 'source' in doc.metadata for doc in documents):
                # Group by source and sample from each group
                from collections import defaultdict
                source_groups = defaultdict(list)
                for doc in documents:
                    source_groups[doc.metadata['source']].append(doc)
                
                # Take representative samples from each source
                for source, docs in source_groups.items():
                    # Take docs from beginning, middle and end of each source
                    if len(docs) <= 6:
                        selected_docs.extend(docs)  # Take all if small enough
                    else:
                        # Sample strategically from beginning, middle, end
                        selected_docs.extend(docs[:2])  # First 2
                        selected_docs.extend(docs[len(docs)//2-1:len(docs)//2+1])  # Middle 2
                        selected_docs.extend(docs[-2:])  # Last 2
                        
                        # Add some random samples from the rest
                        import random
                        remaining = [d for d in docs if d not in selected_docs]
                        sample_size = min(int(len(remaining) * sampling_rate * 0.5), 20)
                        selected_docs.extend(random.sample(remaining, sample_size))
            else:
                # No metadata available - use simple sampling
                import random
                sample_size = min(int(len(documents) * sampling_rate), 100)
                selected_docs = random.sample(documents, sample_size)
                # Always include first and last few documents
                if documents[0] not in selected_docs:
                    selected_docs.insert(0, documents[0])
                if documents[-1] not in selected_docs:
                    selected_docs.append(documents[-1])
        else:
            # For smaller document sets, we can use all docs or simple truncation
            if total_estimated <= max_tokens:
                selected_docs = documents
            else:
                # Simple truncation strategy - prioritize beginning and end content
                front_docs = documents[:len(documents)//3]  # First third
                end_docs = documents[-len(documents)//3:]   # Last third
                
                # Then sample from the middle
                middle_docs = documents[len(documents)//3:-len(documents)//3]
                sample_size = min(max_tokens - estimate_tokens(
                    '\n'.join([d.page_content for d in (front_docs + end_docs)])
                ), len(middle_docs))
                
                import random
                middle_sample = random.sample(middle_docs, min(sample_size, len(middle_docs)))
                selected_docs = front_docs + middle_sample + end_docs
        
        # Combine selected documents with section markers
        context_str = "\n---\n".join([doc.page_content for doc in selected_docs])
        
        # Log the final token count
        final_token_estimate = estimate_tokens(context_str)
        logging.info(f"Final context has approximately {final_token_estimate} tokens from {len(selected_docs)} document chunks")
        
        template = """
        You are an expert instructional designer tasked with creating a university-level course curriculum.
        Analyze the provided context from various documents and generate a logical, week-by-week learning path.

        CONTEXT:
        {context}

        INSTRUCTIONS:
        1. Create a comprehensive course structure with a clear title.
        2. Organize the content into weekly modules (between 8-12 weeks).
        3. For each week, define a clear module title and 3-5 specific sub-topics to be covered.
        4. Ensure the learning path is logical and progressive.
        5. Focus on the most important concepts and skills from the provided content.
        6. If the context seems incomplete, focus on what's available and create a coherent structure.
        
        {format_instructions}
        """
        
        prompt = ChatPromptTemplate.from_template(
            template,
            partial_variables={"format_instructions": self.curriculum_parser.get_format_instructions()}
        )
        
        try:
            chain = prompt | self.curriculum_model | self.curriculum_parser
            result = chain.invoke({"context": context_str})
            
            logging.info(f"Raw curriculum result type: {type(result)}")
            logging.info(f"Raw curriculum result: {result}")
            
            # Handle case where result might be a dict instead of CourseLMS object
            if isinstance(result, dict):
                logging.info("Converting dict result to CourseLMS object")
                curriculum = CourseLMS(**result)
            else:
                curriculum = result
            
            # Validate that curriculum has modules
            if not hasattr(curriculum, 'modules') or not curriculum.modules:
                logging.error("Generated curriculum has no modules")
                return None
            
            # Override title if provided
            if course_title and hasattr(curriculum, 'course_title'):
                curriculum.course_title = course_title
            
            logging.info(f"Generated curriculum with {len(curriculum.modules)} modules")
            return curriculum
            
        except Exception as e:
            logging.error(f"Error generating curriculum: {e}")
            import traceback
            logging.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _generate_content(self, curriculum: CourseLMS, retriever) -> CourseLMS:
        """Generate detailed content for each topic in the curriculum."""
        if not retriever:
            raise ValueError("Retriever must be provided for content generation")
        
        template = """
        You are an expert university professor. Write detailed, clear, and engaging lecture content
        for the given topic based *only* on the provided context.

        CONTEXT:
        {context}

        TOPIC:
        {topic}

        INSTRUCTIONS:
        - Explain the topic thoroughly using the provided context.
        - Use examples from the context if available.
        - Structure the content with clear headings and paragraphs.
        - The tone should be academic and authoritative, yet accessible.
        - Provide comprehensive coverage of the topic.
        """
        
        prompt = ChatPromptTemplate.from_template(template)
        
        # Build RAG chain for content generation
        def get_context(topic_dict):
            topic = topic_dict['topic']
            docs = retriever.get_relevant_documents(topic)
            return {"context": "\n---\n".join(doc.page_content for doc in docs), "topic": topic}
        
        content_chain = (
            RunnablePassthrough()
            | get_context
            | prompt
            | self.content_model
            | self.content_parser
        )
        
        # Generate content for each sub-topic
        for module in curriculum.modules:
            logging.info(f"Generating content for Week {module.week}: {module.title}")
            
            for sub_topic in module.sub_topics:
                try:
                    logging.info(f"  Generating content for: {sub_topic.title}")
                    
                    content = content_chain.invoke({"topic": sub_topic.title})
                    sub_topic.content = content
                    
                    logging.info(f"  Content generated successfully for: {sub_topic.title}")
                    
                except Exception as e:
                    logging.error(f"  Failed to generate content for {sub_topic.title}: {e}")
                    sub_topic.content = f"Content generation failed for this topic. Error: {str(e)}"
        
        logging.info("Content generation completed for all topics")
        return curriculum