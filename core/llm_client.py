from openai import OpenAI
from typing import Optional, List, Dict, Any
import json
import os
from dotenv import load_dotenv

load_dotenv()


class LLMClient:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        )
        self.model = os.getenv("OPENAI_MODEL", "gpt-4")
        self.conversation_history: List[Dict[str, str]] = []
        
    def set_system_prompt(self, prompt: str):
        self.conversation_history = [{"role": "system", "content": prompt}]
        
    def chat(self, user_input: str) -> str:
        self.conversation_history.append({"role": "user", "content": user_input})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.conversation_history,
                temperature=0.3,
                max_tokens=2000
            )
            
            assistant_message = response.choices[0].message.content
            self.conversation_history.append({"role": "assistant", "content": assistant_message})
            return assistant_message
        except Exception as e:
            return f"Error communicating with LLM: {str(e)}"
            
    def chat_with_json_response(self, user_input: str) -> Optional[Dict[str, Any]]:
        self.conversation_history.append({"role": "user", "content": user_input})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.conversation_history,
                temperature=0.1,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            assistant_message = response.choices[0].message.content
            self.conversation_history.append({"role": "assistant", "content": assistant_message})
            return json.loads(assistant_message)
        except Exception as e:
            print(f"Error in JSON response: {str(e)}")
            return None
            
    def clear_history(self):
        if self.conversation_history and self.conversation_history[0]["role"] == "system":
            system_prompt = self.conversation_history[0]
            self.conversation_history = [system_prompt]
        else:
            self.conversation_history = []
            
    def get_history(self) -> List[Dict[str, str]]:
        return self.conversation_history.copy()
