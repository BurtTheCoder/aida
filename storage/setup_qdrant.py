# setup_qdrant.py
import asyncio
from qdrant_client import QdrantClient
from qdrant_client.http import models
from utils import logging

async def setup_qdrant():
    try:
        # Initialize Qdrant client
        client = QdrantClient(host="localhost", port=6333)

        # Configuration for Mem0 collection
        collection_name = "aida_memories"
        vector_size = 3072  # For text-embedding-3-large

        # Check if collection exists
        collections = client.get_collections()
        existing_collections = [collection.name for collection in collections.collections]

        if collection_name not in existing_collections:
            # Create collection with appropriate configuration
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE
                ),
                optimizers_config=models.OptimizersConfigDiff(
                    indexing_threshold=20000,  # Optimize for larger datasets
                    memmap_threshold=50000
                ),
                on_disk_payload=True  # Store payload on disk for better memory usage
            )

            # Create indexes for efficient searching
            client.create_payload_index(
                collection_name=collection_name,
                field_name="user_id",
                field_schema=models.PayloadSchemaType.KEYWORD
            )

            client.create_payload_index(
                collection_name=collection_name,
                field_name="timestamp",
                field_schema=models.PayloadSchemaType.DATETIME
            )

            logging.info(f"Created collection '{collection_name}' with indexes")
        else:
            logging.info(f"Collection '{collection_name}' already exists")

        # Verify collection
        collection_info = client.get_collection(collection_name)
        logging.info(f"Collection info: {collection_info}")

        return True

    except Exception as e:
        logging.error(f"Error setting up Qdrant: {e}")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(setup_qdrant())
