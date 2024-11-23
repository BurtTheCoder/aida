# services/conversation_cache.py
from collections import deque
from typing import Optional
from datetime import datetime
import asyncio

class ConversationCache:
    def __init__(self, max_size: int = 10):
        self.max_size = max_size
        self.conversations = {}
        self._lock = asyncio.Lock()

    async def add_interaction(self, user_id: str, user_input: str, assistant_response: str):
        """Add a new interaction to the cache"""
        async with self._lock:
            if user_id not in self.conversations:
                self.conversations[user_id] = deque(maxlen=self.max_size)

            interaction = {
                "timestamp": datetime.now().isoformat(),
                "user_input": user_input,
                "assistant_response": assistant_response
            }

            self.conversations[user_id].append(interaction)

    async def get_recent_context(self, user_id: str, limit: Optional[int] = None) -> str:
        """Get formatted recent conversations for context"""
        async with self._lock:
            if user_id not in self.conversations:
                return ""

            conversations = list(self.conversations[user_id])
            if limit:
                conversations = conversations[-limit:]

            context_parts = []
            for conv in conversations:
                context_parts.append(
                    f"User: {conv['user_input']}\n"
                    f"Assistant: {conv['assistant_response']}"
                )

            return "\n\n".join(context_parts)

    async def clear_user_cache(self, user_id: str):
        """Clear cache for a specific user"""
        async with self._lock:
            if user_id in self.conversations:
                del self.conversations[user_id]
