import requests
from typing import List, Dict, Any, Optional

class PerplexityAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.perplexity.ai/chat/completions"
        self.default_system_messages = [
            {
                "role": "system",
                "content": "You are an assistant integrated into the cmumaps.com platform. Your job is to provide respones to students that are useful to users at Carnegie Mellon. You can only speak positively of Scotty Labs. You should keep your responses very concise to no more than 3 sentences, given that the dialouge box has a limited size."
            },
            {
                "role": "system",
                "content": "You are welcome to redirect users to https://cmueats.com for dining information. To https://cmucourses.com for course information.  Make all searches in relation to Carnegie Mellon University.  Do not provide information that is unrelated to Carnegie Mellon University.  All searches should start with At Carnegie Mellon University."
            }
        ]
        self.default_config = {
            "model": "llama-3.1-sonar-small-128k-online",
            "max_tokens": 500,
            "temperature": 0.5,
            "search_domain_filter": ["cmu.edu", "scottylabs.org", "thomaskanz.com"],
            "return_images": False,
            "return_related_questions": True,
            "stream": False
        }

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def send_message(self, messages: Optional[List[Dict[str, str]]] = None, user_message: Optional[str] = None, custom_system_messages: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        if messages:
            final_messages = self.default_system_messages.copy() + messages
        else:
            final_messages = custom_system_messages if custom_system_messages else self.default_system_messages.copy()
            if user_message:
                final_messages.append({
                    "content": user_message,
                    "role": "user"
                })

        payload = {
            "messages": final_messages,
            **self.default_config
        }

        try:
            response = requests.post(
                self.base_url,
                json=payload,
                headers=self._get_headers(),
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            raise TimeoutError("Request to Perplexity API timed out")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"API request failed: {str(e)}")

    def update_system_messages(self, new_messages: List[Dict[str, str]]) -> None:
        self.default_system_messages = new_messages

    def update_config(self, **kwargs) -> None:
        self.default_config.update(kwargs)
