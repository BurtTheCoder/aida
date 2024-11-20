# qdrant_manager.py
from qdrant_client import QdrantClient
from qdrant_client.http import models
from utils import logging
from typing import Optional, Dict, Any
from datetime import datetime

class QdrantManager:
    def __init__(self, host: str = "localhost", port: int = 6333):
        self.client = QdrantClient(host=host, port=port)
        self.collection_name = "aida_memories"

    def health_check(self) -> bool:
        """Check if Qdrant is running and collection is available"""
        try:
            collections = self.client.get_collections()
            return self.collection_name in [c.name for c in collections.collections]
        except Exception as e:
            logging.error(f"Qdrant health check failed: {e}")
            return False

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            return {
                "vectors_count": collection_info.vectors_count,
                "indexed_vectors_count": collection_info.indexed_vectors_count,
                "points_count": collection_info.points_count,
                "segments_count": collection_info.segments_count,
                "status": collection_info.status
            }
        except Exception as e:
            logging.error(f"Error getting collection stats: {e}")
            return {}

    def optimize_collection(self):
        """Optimize collection for better performance"""
        try:
            self.client.optimize_index(
                collection_name=self.collection_name,
                optimize_threshold=10000  # Adjust based on your needs
            )
            logging.info("Collection optimization triggered")
        except Exception as e:
            logging.error(f"Error optimizing collection: {e}")
