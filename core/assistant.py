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
import time

class AidaAssistant:
    def __init__(self, user_id: str = "default_user"):
        self.claude_service = ClaudeService()
        self.web_search = WebSearchService()
        self.memory = Mem0Service()
        self.conversation_cache = ConversationCache(max_size=5)  # Reduced from 10
        self.memory_tools = MemoryTools(self.memory)
        self.user_id = user_id
        self.background_tasks: Set[asyncio.Task] = set()
        self.processing_complete = asyncio.Event()

    async def process_input(self, user_input: str) -> str:
        start_time = time.time()
        self.processing_complete.clear()

        try:
            logging.debug("Starting input processing")

            # Get context with timeout
            try:
                context_task = asyncio.create_task(
                    self.conversation_cache.get_recent_context(self.user_id)
                )
                recent_context = await asyncio.wait_for(context_task, timeout=3.0)
            except asyncio.TimeoutError:
                logging.warning("Context retrieval timed out, proceeding without context")
                recent_context = ""

            logging.debug(f"Memory retrieval took: {time.time() - start_time:.2f}s")

            # Create contextualized input
            claude_start_time = time.time()
            contextualized_input = (
                f"Recent conversation context:\n{recent_context}\n\n"
                f"Current input: {user_input}"
            ) if recent_context else user_input

            # Process with Claude (with increased timeout)
            try:
                response_task = asyncio.create_task(
                    self.claude_service.handle_message_with_tools(
                        contextualized_input,
                        self.web_search,
                        self.memory_tools,
                        self.user_id
                    )
                )
                response = await asyncio.wait_for(response_task, timeout=60.0)  # Increased from 10s to 20s
            except asyncio.TimeoutError:
                logging.warning("Claude processing timed out")
                return "I apologize, but I'm taking longer than expected to process your request. Would you like me to try again with a simpler query?"

            logging.debug(f"Claude processing took: {time.time() - claude_start_time:.2f}s")

            # Verify response isn't empty
            if not response or not response.strip():
                logging.error("Empty response received from Claude")
                return "I apologize, but I received an empty response. Please try again."

            # Store interaction in background with verification
            store_start_time = time.time()
            store_task = asyncio.create_task(self._store_interaction_background(user_input, response))
            try:
                await asyncio.wait_for(store_task, timeout=5.0)
            except asyncio.TimeoutError:
                logging.warning("Storage operation timed out, continuing with response")

            logging.debug(f"Background storage initiated: {time.time() - store_start_time:.2f}s")

            total_time = time.time() - start_time
            logging.debug(f"Total processing time: {total_time:.2f}s")

            self.processing_complete.set()
            return response

        except Exception as e:
            self.processing_complete.set()
            logging.error(f"Error processing input: {e}", exc_info=True)
            return "I apologize, but I encountered an error processing your request. Please try again."

    async def _store_interaction_background(self, user_input: str, response: str):
        """Store interaction in background without blocking"""
        async def _store():
            store_start = time.time()
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
                logging.debug(f"Background storage completed in: {time.time() - store_start:.2f}s")
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
