# tools/memory_tools.py
from typing import Dict, Any, Optional, List
from utils import logging
from services.memory_service import Mem0Service
from datetime import datetime

class MemoryTools:
    def __init__(self, memory_service: Mem0Service):
        self.memory = memory_service

    def _format_memory_context(self, memories: List[Dict[str, Any]]) -> str:
        """Format memories into readable context"""
        if not memories:
            return "No relevant memories found."

        formatted_parts = []
        for memory in memories:
            timestamp = memory.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp)
                    timestamp = dt.strftime("%Y-%m-%d %H:%M")
                except ValueError:
                    timestamp = "Unknown time"

            text = memory.get('text', '').strip()
            if text:
                # Check if the text already contains User/Assistant format
                if not (text.startswith("User:") or text.startswith("Assistant:")):
                    formatted_parts.append(f"[{timestamp}] {text}")
                else:
                    formatted_parts.append(f"[{timestamp}]\n{text}")

        return "\n\n".join(formatted_parts) if formatted_parts else "No relevant memories found."

    async def search_memories(self, query: str, user_id: str = "default_user", limit: int = 5) -> Dict[str, Any]:
        """Search through user memories with error handling"""
        try:
            memories = await self.memory.get_relevant_memories(query, user_id, limit)
            formatted_results = self._format_memory_context(memories)
            return {
                "query": query,
                "results": memories,
                "formatted_results": formatted_results,
                "count": len(memories),
                "status": "success"
            }
        except Exception as e:
            logging.error(f"Memory search error: {e}")
            return {
                "query": query,
                "results": [],
                "formatted_results": "Error retrieving memories.",
                "count": 0,
                "status": "error",
                "error": str(e)
            }

    async def get_context(self, user_id: str = "default_user") -> Dict[str, Any]:
        """Get user context from memories"""
        try:
            memories = await self.memory.get_user_context(user_id)
            return {
                "user_id": user_id,
                "context": memories,
                "formatted_context": self._format_memory_context(memories)
            }
        except Exception as e:
            logging.error(f"Context retrieval error: {e}")
            return {
                "error": str(e),
                "user_id": user_id,
                "context": [],
                "formatted_context": "No context available."
            }

    async def tag_memory(self, query: str, tag: str, user_id: str = "default_user") -> Dict[str, Any]:
        """Tag matching memories"""
        try:
            await self.memory.tag_memories(user_id, query, tag)
            # Get tagged memories to return
            tagged_memories = await self.memory.search_by_tag(user_id, tag)
            return {
                "success": True,
                "message": f"Tagged memories matching '{query}' with '{tag}'",
                "tagged_memories": tagged_memories,
                "formatted_memories": self._format_memory_context(tagged_memories)
            }
        except Exception as e:
            logging.error(f"Memory tagging error: {e}")
            return {
                "error": str(e),
                "success": False,
                "tagged_memories": [],
                "formatted_memories": "No memories tagged."
            }
