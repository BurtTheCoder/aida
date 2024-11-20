# utils/cleanup.py
from utils import logging
from pathlib import Path
import time
from config.settings import settings

async def cleanup_audio_files():
    """Clean up old audio files"""
    try:
        if settings.AUDIO_DIR.exists():
            for file in settings.AUDIO_DIR.glob("*.mp3"):
                if time.time() - file.stat().st_mtime > 3600:
                    file.unlink()
    except Exception as e:
        logging.error(f"Error cleaning up audio files: {e}")
