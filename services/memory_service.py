# services/memory_service.py
import os
from mem0 import Memory
import asyncio
from typing import List, Dict, Any, Optional
import json
from utils import logging
from datetime import datetime, timedelta
import uuid
from pathlib import Path
from storage.qdrant_manager import QdrantManager

class Mem0Service:
    def __init__(self):
        # Initialize Qdrant manager
        self.qdrant_manager = QdrantManager()

        # Verify Qdrant health
        if not self.qdrant_manager.health_check():
            raise RuntimeError("Qdrant is not available")

        # Configure mem0 with supported settings only
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
            try:
                collection_stats = self.qdrant_manager.get_collection_stats()
                vectors_count = collection_stats.get("vectors_count")

                if vectors_count is not None and vectors_count > 10000:
                    self.qdrant_manager.optimize_collection()
                    logging.info("Collection optimization triggered")
            except Exception as e:
                logging.warning(f"Could not check collection statistics: {e}")

        except Exception as e:
            logging.error(f"Error initializing mem0: {e}")
            raise

    async def store_interaction(self, user_input: str, assistant_response: str, user_id: str = "default_user"):
        """Store an interaction in memory with enhanced metadata"""
        try:
            if not user_input or not assistant_response:
                return

            current_time = datetime.now().isoformat()
            conversation_id = str(uuid.uuid4())

            # Create the interaction payload
            interaction = {
                "user_message": user_input.strip(),
                "assistant_response": assistant_response.strip(),
                "timestamp": current_time
            }

            # Create metadata
            metadata = {
                "type": "conversation",
                "app": "aida",
                "timestamp": current_time,
                "message_type": "interaction",
                "conversation_id": conversation_id,
                "user_id": user_id
            }

            # Store in background
            def _store():
                try:
                    self.memory.add(
                        json.dumps(interaction),
                        user_id=user_id,
                        metadata=metadata
                    )
                    logging.info(f"Successfully stored interaction for user {user_id}")
                except Exception as e:
                    logging.error(f"Error storing in memory: {str(e)}")

            # Run storage operation in thread pool
            await asyncio.get_event_loop().run_in_executor(None, _store)

        except Exception as e:
            logging.error(f"Error preparing memory storage: {str(e)}")

    async def get_relevant_memories(
        self,
        query: str,
        user_id: str = "default_user",
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant memories combining recent and semantically relevant results"""
        try:
            # Get recent memories
            recent_memories = self.memory.get_all(
                user_id=user_id,
                limit=3,
            )

            # Get semantically relevant memories
            relevant_memories = self.memory.search(
                query,
                user_id=user_id,
                limit=limit
            )

            # Process and merge memories
            processed_memories = []

            # Process recent memories
            for memory in recent_memories:
                processed = await self._process_memory_result(memory)
                if processed:
                    processed_memories.append(processed)

            # Process relevant memories
            for memory in relevant_memories:
                processed = await self._process_memory_result(memory)
                if processed:
                    processed_memories.append(processed)

            # Remove duplicates and sort by timestamp
            seen = set()
            unique_memories = []
            for memory in processed_memories:
                memory_id = f"{memory['timestamp']}_{memory['text']}"
                if memory_id not in seen:
                    seen.add(memory_id)
                    unique_memories.append(memory)

            # Sort by timestamp
            sorted_memories = sorted(
                unique_memories,
                key=lambda x: x['timestamp'],
                reverse=True
            )

            return sorted_memories[:limit]

        except Exception as e:
            logging.error(f"Error retrieving memories: {str(e)}")
            return []

    def _merge_memories(self, recent: List[Any], relevant: List[Any]) -> List[Any]:
        """Merge and deduplicate memories while preserving order"""
        try:
            seen = set()
            merged = []

            for memory in recent + relevant:
                try:
                    memory_id = getattr(memory, 'id', str(memory))
                    if memory_id not in seen:
                        seen.add(memory_id)
                        merged.append(memory)
                except Exception as e:
                    logging.error(f"Error processing memory in merge: {str(e)}")
                    continue

            return merged
        except Exception as e:
            logging.error(f"Error merging memories: {str(e)}")
            return []

    def _format_memories(self, memories: List[Any]) -> List[Dict[str, Any]]:
        """Format memories for use with safe processing"""
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

    async def _process_memory_result(self, memory_obj: Any) -> Dict[str, Any]:
        """Safely process memory objects"""
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

    async def get_user_context(self, user_id: str = "default_user", limit: int = 10) -> List[Dict[str, Any]]:
        """Get all memories for a user with enhanced formatting"""
        try:
            # Get all memories without sorting parameters
            memories = self.memory.get_all(
                user_id=user_id,
                limit=limit
            )

            # Sort memories by timestamp manually
            memories = sorted(
                memories,
                key=lambda x: getattr(x, 'metadata', {}).get('timestamp', ''),
                reverse=True
            )

            return self._format_memories(memories)

        except Exception as e:
            logging.error(f"Error getting user context: {str(e)}")
            return []

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
