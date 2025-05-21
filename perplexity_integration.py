from typing import Dict, Any, Optional
import os
from dotenv import load_dotenv
from perplexity_cmugpt.search_class_one import PerplexityAPI  # Changed from relative import

class CMUPerplexitySearch:
    def __init__(self):
        load_dotenv()
        api_key = os.getenv('PERPLEXITY_API_KEY')
        if not api_key:
            raise ValueError("PERPLEXITY_API_KEY not found in environment variables")
        
        self.api = PerplexityAPI(api_key)
        
    def search(self, query: str) -> Dict[str, Any]:
        try:
            # Format query to ensure CMU context
            cmu_query = f"At Carnegie Mellon University, {query}"
            
            # Get response from Perplexity
            response = self.api.send_message(user_message=cmu_query)
            
            if not response or 'choices' not in response:
                return {
                    "search_query": query,
                    "answer": "I apologize, but I couldn't find any information about that.",
                    "error": "No response from Perplexity API"
                }
            
            # Extract the actual answer from the response
            answer = response['choices'][0]['message']['content']
            
            return {
                "search_query": query,
                "answer": answer,
                "source": "Perplexity AI"
            }
            
        except Exception as e:
            return {
                "search_query": query,
                "answer": "I apologize, but I encountered an error while searching.",
                "error": str(e)
            }