# core/assistant.py
from services.claude_service import ClaudeService
from tools.web_search import WebSearchService

class AidaAssistant:
    def __init__(self):
        self.claude_service = ClaudeService()
        self.web_search = WebSearchService()
        
    async def process_input(self, user_input: str) -> str:
        return await self.claude_service.handle_message_with_tools(
            user_input,
            self.web_search
        )