"""
LLM Service - Handles OpenAI language model interactions
"""

from openai import AsyncOpenAI
import config

class LLMService:
    """Service for OpenAI LLM interactions."""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    
    async def get_general_response(self, query: str, target_language: str = "English") -> str:
        """Get a general response from the LLM."""
        messages = [
            {
                "role": "system", 
                "content": f"You are a helpful AI assistant. Answer the user's question concisely and in {target_language}."
            },
            {"role": "user", "content": query}
        ]
        
        try:
            response = await self.client.chat.completions.create(
                model=config.LLM_MODEL_NAME, 
                messages=messages, 
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error getting general LLM response: {e}")
            return "I am sorry, I couldn't process that request at the moment."
    
    async def translate_text(self, text: str, target_language: str) -> str:
        """Translate text using the LLM."""
        if target_language.lower() == "english":
            return text
            
        messages = [
            {
                "role": "system", 
                "content": f"You are an expert translation assistant. Translate the following text into {target_language}. Respond with only the translated text."
            },
            {"role": "user", "content": text}
        ]
        
        try:
            response = await self.client.chat.completions.create(
                model=config.LLM_MODEL_NAME, 
                messages=messages, 
                temperature=0.0
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error during LLM translation: {e}")
            return text