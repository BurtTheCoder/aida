# services/memory_service.py
from mem0 import Memory
import asyncio
from typing import List, Dict, Any, Optional
import json
from utils import logging
from datetime import datetime, timedelta
import uuid
from pathlib import Path
from storage.qdrant_manager import QdrantManager
from cachetools import TTLCache
import time

class Mem0Service:
    def __init__(self):
        # Initialize caches
        self._memory_cache = TTLCache(maxsize=100, ttl=300)  # 5 minute TTL
        self._context_cache = TTLCache(maxsize=50, ttl=600)  # 10 minute TTL

        # Initialize batch processing
        self._batch_queue = []
        self._batch_size = 5
        self._last_batch_time = time.time()
        self._batch_lock = asyncio.Lock()

        # Initialize Qdrant manager
        self.qdrant_manager = QdrantManager()

        # Verify Qdrant health
        if not self.qdrant_manager.health_check():
            raise RuntimeError("Qdrant is not available")

        # Configure mem0
        self.config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "host": "localhost",
                    "port": 6333,
                    "collection_name": "aida_memories",
                    "on_disk": True
                }
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-large"
                }
            },
            "custom_prompt": """
            Please extract key information and relationships from the following interactions.
            Focus on personal information, preferences, facts, and relationships.

            Examples:
            Input: "I like pizza but I'm allergic to cheese"
            Output: {{"facts": ["Likes pizza", "Allergic to cheese"]}}

            Input: "My name is John and I live in New York"
            Output: {{"facts": ["Name: John", "Location: New York"]}}

            Input: "I enjoy hiking with my friend Sarah on weekends"
            Output: {{"facts": ["Enjoys hiking", "Friend: Sarah", "Activity timing: weekends"]}}

            Return facts and relationships in JSON format as shown above.
            """
        }

        try:
            self.memory = Memory.from_config(self.config)
            logging.info("Mem0 service initialized successfully")

            # Check collection statistics and optimize if needed
            self._check_and_optimize_collection()
        except Exception as e:
            logging.error(f"Error initializing mem0: {e}")
            raise

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def cleanup(self):
        """Cleanup resources"""
        try:
            # Process any remaining batch items
            if self._batch_queue:
                await self._process_batch()

            # Clear caches
            self._memory_cache.clear()
            self._context_cache.clear()

            logging.info("Memory service cleanup completed")
        except Exception as e:
            logging.error(f"Error during memory service cleanup: {e}")

    def _check_and_optimize_collection(self):
        """Check collection statistics and optimize if needed"""
        try:
            collection_stats = self.qdrant_manager.get_collection_stats()
            vectors_count = collection_stats.get("vectors_count")

            if vectors_count is not None and vectors_count > 10000:
                self.qdrant_manager.optimize_collection()
                logging.info("Collection optimization triggered")
        except Exception as e:
            logging.warning(f"Could not check collection statistics: {e}")

    def _monitor_cache_sizes(self):
        """Monitor cache sizes for debugging"""
        logging.debug(
            f"Cache sizes - Memory: {len(self._memory_cache)}, "
            f"Context: {len(self._context_cache)}"
        )

    async def store_interaction(self, user_input: str, response: str, user_id: str):
        """Queue interaction for batch storage"""
        async with self._batch_lock:
            store_start = time.time()

            self._batch_queue.append({
                'user_input': user_input,
                'response': response,
                'user_id': user_id,
                'timestamp': datetime.now().isoformat()
            })

            logging.debug(f"Queued interaction for storage in: {time.time() - store_start:.2f}s")

            # Process batch if size threshold reached or time threshold exceeded
            if len(self._batch_queue) >= self._batch_size or \
               time.time() - self._last_batch_time > 30:  # Force batch after 30 seconds
                await self._process_batch()

    async def _process_batch(self):
        """Process queued interactions in batch"""
        if not self._batch_queue:
            return

        try:
            batch_start = time.time()
            batch = self._batch_queue.copy()
            self._batch_queue.clear()
            self._last_batch_time = time.time()

            # Group batch items by user_id for more efficient processing
            user_batches: Dict[str, List[Dict]] = {}
            for item in batch:
                user_id = item['user_id']
                if user_id not in user_batches:
                    user_batches[user_id] = []
                user_batches[user_id].append(item)

            # Process each user's batch in parallel with timeout
            tasks = []
            for user_id, user_items in user_batches.items():
                tasks.extend([
                    self._store_single_interaction(item)
                    for item in user_items
                ])

            # Use wait_for instead of timeout context
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=30.0)

            logging.debug(
                f"Processed batch of {len(batch)} items "
                f"for {len(user_batches)} users in: {time.time() - batch_start:.2f}s"
            )

        except asyncio.TimeoutError:
            logging.error("Batch processing timed out")
            self._batch_queue.extend(batch)  # Restore batch for retry
        except Exception as e:
            logging.error(f"Batch processing error: {e}")
            self._batch_queue.extend(batch)

    async def _store_single_interaction(self, item: Dict[str, Any]):
        """Store a single interaction in memory"""
        try:
            # Add retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    interaction = {
                        "user_message": item['user_input'].strip(),
                        "assistant_response": item['response'].strip(),
                        "timestamp": item['timestamp']
                    }

                    metadata = {
                        "type": "conversation",
                        "app": "aida",
                        "timestamp": item['timestamp'],
                        "message_type": "interaction",
                        "conversation_id": str(uuid.uuid4()),
                        "user_id": item['user_id']
                    }

                    # Use wait_for instead of timeout context
                    await asyncio.wait_for(
                        self._do_store(interaction, metadata, item['user_id']),
                        timeout=5.0
                    )

                    # Invalidate relevant caches
                    self._invalidate_caches(item['user_id'])

                    logging.info(f"Successfully stored interaction for user {item['user_id']}")
                    return

                except asyncio.TimeoutError:
                    if attempt == max_retries - 1:
                        raise
                    logging.warning(f"Timeout on attempt {attempt + 1}/{max_retries} for storing interaction")
                    await asyncio.sleep(1)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    logging.warning(f"Retry {attempt + 1}/{max_retries} for storing interaction: {e}")
                    await asyncio.sleep(1)

        except Exception as e:
            logging.error(f"Error storing single interaction: {e}")
            raise

    async def _do_store(self, interaction: Dict, metadata: Dict, user_id: str):
        """Actual storage operation"""
        self.memory.add(
            json.dumps(interaction),
            user_id=user_id,
            metadata=metadata
        )

    def _invalidate_caches(self, user_id: str):
        """Invalidate caches for a user"""
        # Remove all cached items for this user
        keys_to_remove = [k for k in self._memory_cache.keys() if k.startswith(f"{user_id}:")]
        for k in keys_to_remove:
            self._memory_cache.pop(k, None)

        # Remove context cache
        self._context_cache.pop(user_id, None)

    async def get_relevant_memories(
        self,
        query: str,
        user_id: str = "default_user",
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant memories with caching and optimization"""
        cache_key = f"{user_id}:{query}"

        # Check cache first
        if cache_key in self._memory_cache:
            logging.debug("Returning cached memories")
            return self._memory_cache[cache_key]

        try:
            # Use generator for memory efficient processing
            async def memory_generator():
                # Get recent memories
                for memory in self.memory.get_all(user_id=user_id, limit=3):
                    yield memory

                # Get semantically relevant memories
                for memory in self.memory.search(query, user_id=user_id, limit=limit):
                    yield memory

            # Process memories efficiently
            processed_memories = []
            seen = set()
            async for memory in memory_generator():
                processed = await self._process_memory_result(memory)
                if processed:
                    memory_id = f"{processed['timestamp']}_{processed['text']}"
                    if memory_id not in seen:
                        seen.add(memory_id)
                        processed_memories.append(processed)

                        # Early exit if we have enough memories
                        if len(processed_memories) >= limit:
                            break

            # Sort by timestamp
            sorted_memories = sorted(
                processed_memories,
                key=lambda x: x['timestamp'],
                reverse=True
            )[:limit]

            # Cache the results
            self._memory_cache[cache_key] = sorted_memories
            return sorted_memories

        except Exception as e:
            logging.error(f"Error retrieving memories: {str(e)}")
            return []

    async def get_user_context(self, user_id: str = "default_user", limit: int = 10) -> List[Dict[str, Any]]:
        """Get user context with caching"""
        if user_id in self._context_cache:
            return self._context_cache[user_id]

        try:
            memories = self.memory.get_all(
                user_id=user_id,
                limit=limit
            )

            # Sort memories by timestamp
            memories = sorted(
                memories,
                key=lambda x: getattr(x, 'metadata', {}).get('timestamp', ''),
                reverse=True
            )

            formatted_memories = self._format_memories(memories)
            self._context_cache[user_id] = formatted_memories
            return formatted_memories

        except Exception as e:
            logging.error(f"Error getting user context: {str(e)}")
            return []

    async def _process_memory_result(self, memory_obj: Any) -> Optional[Dict[str, Any]]:
        """Process memory objects safely"""
        try:
            if hasattr(memory_obj, 'payload'):
                # Try to parse JSON payload
                try:
                    payload = json.loads(memory_obj.payload)
                    if isinstance(payload, dict):
                        text = f"User: {payload.get('user_message', '')}\nAssistant: {payload.get('assistant_response', '')}"
                    else:
                        text = str(memory_obj.payload)
                except json.JSONDecodeError:
                    text = str(memory_obj.payload)

                metadata = getattr(memory_obj, 'metadata', {})
                return {
                    "text": text,
                    "metadata": metadata,
                    "timestamp": metadata.get('timestamp', ''),
                    "type": metadata.get('type', 'unknown')
                }
            else:
                # Handle string or other types
                return {
                    "text": str(memory_obj),
                    "metadata": {},
                    "timestamp": datetime.now().isoformat(),
                    "type": "unknown"
                }
        except Exception as e:
            logging.error(f"Error processing memory result: {str(e)}")
            return None

    def _format_memories(self, memories: List[Any]) -> List[Dict[str, Any]]:
        """Format memories for use"""
        formatted_memories = []
        for memory in memories:
            try:
                processed_memory = self._process_memory_result(memory)
                if processed_memory:
                    formatted_memories.append(processed_memory)
            except Exception as e:
                logging.error(f"Error formatting memory: {str(e)}")
                continue
        return formatted_memories

    async def prune_old_memories(self, user_id: str, days_old: int = 30):
        """Remove memories older than specified days"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            self.memory.delete(
                user_id=user_id,
                filter_condition={
                    "timestamp": {"$lt": cutoff_date.isoformat()}
                }
            )
            logging.info(f"Pruned memories older than {days_old} days for user {user_id}")
        except Exception as e:
            logging.error(f"Error pruning memories: {str(e)}")

    async def tag_memories(self, user_id: str, query: str, tag: str):
        """Add tags to matching memories"""
        try:
            memories = self.memory.search(query, user_id=user_id)
            for memory in memories:
                metadata = getattr(memory, 'metadata', {})
                tags = metadata.get('tags', [])
                if tag not in tags:
                    tags.append(tag)
                    metadata['tags'] = tags
                    self.memory.update(memory.id, metadata=metadata)
            logging.info(f"Tagged memories with '{tag}' for user {user_id}")
        except Exception as e:
            logging.error(f"Error tagging memories: {str(e)}")

    async def search_by_tag(self, user_id: str, tag: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve memories by tag"""
        try:
            memories = self.memory.search(
                "",  # Empty query to match all
                user_id=user_id,
                filter_condition={"tags": tag},
                limit=limit
            )
            return self._format_memories(memories)
        except Exception as e:
            logging.error(f"Error searching memories by tag: {str(e)}")
            return []

    def clear_memories(self, user_id: str):
        """Clear all memories for a user"""
        try:
            self.memory.delete_all(user_id=user_id)
            # Clear all caches for this user
            self._invalidate_caches(user_id)
            logging.info(f"Cleared all memories for user {user_id}")
        except Exception as e:
            logging.error(f"Error clearing memories: {str(e)}")

    async def get_memory_stats(self, user_id: str) -> Dict[str, Any]:
        """Get statistics about stored memories"""
        try:
            all_memories = self.memory.get_all(user_id=user_id)
            memory_count = len(all_memories)

            # Calculate date range
            timestamps = [
                datetime.fromisoformat(getattr(m, 'metadata', {}).get('timestamp', datetime.now().isoformat()))
                for m in all_memories
                if getattr(m, 'metadata', {}).get('timestamp')
            ]

            stats = {
                "total_memories": memory_count,
                "first_memory": min(timestamps).isoformat() if timestamps else None,
                "last_memory": max(timestamps).isoformat() if timestamps else None,
                "types": {}
            }

            # Count memory types
            for memory in all_memories:
                memory_type = getattr(memory, 'metadata', {}).get('type', 'unknown')
                stats["types"][memory_type] = stats["types"].get(memory_type, 0) + 1

            return stats

        except Exception as e:
            logging.error(f"Error getting memory stats: {str(e)}")
            return {"error": str(e)}
