# services/memory_service.py
import os
from mem0 import Memory
from typing import List, Dict, Any, Optional
import json
import logging
from datetime import datetime

class Mem0Service:
    def __init__(self):
        # Configure mem0
        self.config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "host": "localhost",
                    "port": 6333,
                    "collection_name": "aida_memories"
                }
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-large"
                }
            }
        }

        try:
            self.memory = Memory.from_config(self.config)
        except Exception as e:
            logging.error(f"Error initializing mem0: {e}")
            raise

    async def store_interaction(self, user_input: str, assistant_response: str, user_id: str = "default_user"):
        """Store an interaction in memory"""
        try:
            current_time = datetime.now().isoformat()

            try:
                # Store user message
                self.memory.add(
                    user_input,  # Pass the text directly as first argument
                    user_id=user_id,
                    metadata={
                        "type": "user_message",
                        "app": "aida",
                        "timestamp": current_time
                    }
                )

                # Store assistant response
                self.memory.add(
                    assistant_response,  # Pass the text directly as first argument
                    user_id=user_id,
                    metadata={
                        "type": "assistant_response",
                        "app": "aida",
                        "timestamp": current_time
                    }
                )

                logging.info(f"Successfully stored interaction for user {user_id}")
            except Exception as e:
                logging.error(f"Error storing messages in memory: {str(e)}")
                raise

        except Exception as e:
            logging.error(f"Error storing interaction in memory: {str(e)}")

    async def get_relevant_memories(self, query: str, user_id: str = "default_user", limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant memories based on query"""
        try:
            memories = self.memory.search(query, user_id=user_id)

            # Format memories for use
            formatted_memories = []
            for memory in memories:
                try:
                    formatted_memories.append({
                        "text": memory if isinstance(memory, str) else str(memory),
                        "metadata": getattr(memory, 'metadata', {}),
                        "timestamp": getattr(memory, 'metadata', {}).get("timestamp")
                    })
                except Exception as e:
                    logging.error(f"Error formatting memory: {str(e)}")
                    continue

            return formatted_memories[:limit]

        except Exception as e:
            logging.error(f"Error retrieving memories: {str(e)}")
            return []

    async def get_user_context(self, user_id: str = "default_user", limit: int = 10) -> List[Dict[str, Any]]:
        """Get all memories for a user"""
        try:
            memories = self.memory.get_all(user_id=user_id)

            # Format memories for use
            formatted_memories = []
            for memory in memories:
                try:
                    formatted_memories.append({
                        "text": memory if isinstance(memory, str) else str(memory),
                        "metadata": getattr(memory, 'metadata', {}),
                        "timestamp": getattr(memory, 'metadata', {}).get("timestamp")
                    })
                except Exception as e:
                    logging.error(f"Error formatting memory: {str(e)}")
                    continue

            return formatted_memories[:limit]

        except Exception as e:
            logging.error(f"Error getting user context: {str(e)}")
            return []

    def clear_memories(self, user_id: str):
        """Clear all memories for a user"""
        try:
            self.memory.clear(user_id=user_id)
            logging.info(f"Cleared memories for user {user_id}")
        except Exception as e:
            logging.error(f"Error clearing memories: {str(e)}")
