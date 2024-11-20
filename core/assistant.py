# core/assistant.py
from services.claude_service import ClaudeService
from services.memory_service import Mem0Service
from services.conversation_cache import ConversationCache
from tools.web_search import WebSearchService
from tools.memory_tools import MemoryTools
from utils import logging
from typing import List, Dict, Any, Set
from datetime import datetime
import asyncio

class AidaAssistant:
    def __init__(self, user_id: str = "default_user"):
        self.claude_service = ClaudeService()
        self.web_search = WebSearchService()
        self.memory = Mem0Service()
        self.conversation_cache = ConversationCache(max_size=10)
        self.memory_tools = MemoryTools(self.memory)
        self.user_id = user_id
        self.background_tasks: Set[asyncio.Task] = set()

    async def process_input(self, user_input: str) -> str:
        """Process user input with recent context"""
        try:
            # Get recent conversation context
            recent_context = await self.conversation_cache.get_recent_context(self.user_id)

            # Create contextualized input
            contextualized_input = ""
            if recent_context:
                contextualized_input = (
                    "Recent conversation context:\n"
                    f"{recent_context}\n\n"
                    f"Current input: {user_input}"
                )
            else:
                contextualized_input = user_input

            # Process with Claude
            response = await self.claude_service.handle_message_with_tools(
                contextualized_input,
                self.web_search,
                self.memory_tools,
                self.user_id
            )

            # Store interaction in background
            self._store_interaction_background(user_input, response)

            return response

        except Exception as e:
            logging.error(f"Error processing input: {e}", exc_info=True)
            return "I apologize, but I encountered an error processing your request."

    def _store_interaction_background(self, user_input: str, response: str):
        """Store interaction in background without blocking"""
        async def _store():
            try:
                # Store in cache and memory concurrently
                await asyncio.gather(
                    self.conversation_cache.add_interaction(
                        self.user_id,
                        user_input,
                        response
                    ),
                    self.memory.store_interaction(
                        user_input,
                        response,
                        self.user_id
                    )
                )
            except Exception as e:
                logging.error(f"Background storage error: {e}")

        # Create task and add to background tasks set
        task = asyncio.create_task(_store())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    async def manage_memories(self, command: str, **kwargs) -> str:
        """Administrative memory management commands"""
        try:
            if command == "prune":
                days = kwargs.get('days', 30)
                await self.memory.prune_old_memories(self.user_id, days)
                return f"Pruned memories older than {days} days."
            elif command == "clear":
                await self.memory.clear_memories(self.user_id)  # Make this async
                return "Cleared all memories."
            elif command == "stats":
                stats = await self.memory.get_memory_stats(self.user_id)
                return stats
            return "Invalid memory management command."
        except Exception as e:
            logging.error(f"Error managing memories: {e}", exc_info=True)
            return f"Error managing memories: {str(e)}"

    async def cleanup(self):
        """Cleanup resources and wait for background tasks to complete"""
        try:
            # Wait for all background tasks to complete with timeout
            if self.background_tasks:
                done, pending = await asyncio.wait(
                    self.background_tasks,
                    timeout=5.0  # 5 second timeout
                )

                # Cancel any pending tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        logging.error(f"Error in background task during cleanup: {e}")

            # Clear the background tasks set
            self.background_tasks.clear()

        except Exception as e:
            logging.error(f"Error during assistant cleanup: {e}")
