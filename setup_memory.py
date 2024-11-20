# setup_memory.py
import asyncio
import sys
from pathlib import Path

# Add the project root directory to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from storage.setup_qdrant import setup_qdrant
from storage.qdrant_manager import QdrantManager
from utils.logger import info, error

async def setup_memory_system():
    try:
        # Setup Qdrant
        qdrant_success = await setup_qdrant()
        if not qdrant_success:
            raise RuntimeError("Failed to setup Qdrant")

        # Initialize and verify Qdrant manager
        qdrant_manager = QdrantManager()
        if not qdrant_manager.health_check():
            raise RuntimeError("Qdrant health check failed")

        # Get initial statistics
        stats = qdrant_manager.get_collection_stats()
        info(f"Qdrant collection statistics: {stats}")

        info("Memory system setup completed successfully")
        return True

    except Exception as e:
        error(f"Error setting up memory system: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(setup_memory_system())
