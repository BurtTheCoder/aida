# core/assistant.py
from services.claude_service import ClaudeService
from services.memory_service import Mem0Service
from tools.web_search import WebSearchService
import logging

class AidaAssistant:
    def __init__(self, user_id: str = "default_user"):
        self.claude_service = ClaudeService()
        self.web_search = WebSearchService()
        self.memory = Mem0Service()
        self.user_id = user_id

    async def process_input(self, user_input: str) -> str:
        try:
            # Get relevant memories for context
            relevant_memories = await self.memory.get_relevant_memories(user_input, self.user_id)

            # Format memories as context
            memory_context = "\n".join([
                f"Previous interaction: {memory['text']}"
                for memory in relevant_memories
            ])

            # Add memory context to input if available
            contextualized_input = (
                f"Context from previous interactions:\n{memory_context}\n\n"
                f"Current input: {user_input}"
            ) if memory_context else user_input

            # Process input with Claude
            response = await self.claude_service.handle_message_with_tools(
                contextualized_input,
                self.web_search
            )

            # Store interaction in memory
            await self.memory.store_interaction(
                user_input,
                response,
                self.user_id
            )

            return response

        except Exception as e:
            logging.error(f"Error processing input: {e}")
            return "I apologize, but I encountered an error processing your request."

    async def get_user_context(self) -> str:
        """Get formatted user context from memory"""
        try:
            memories = await self.memory.get_user_context(self.user_id)
            return "\n".join([
                f"Memory: {memory['text']}"
                for memory in memories
            ])
        except Exception as e:
            logging.error(f"Error getting user context: {e}")
            return "Unable to retrieve memory context."
