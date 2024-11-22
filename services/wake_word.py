# services/wake_word.py
import pvporcupine
import struct
from typing import Optional, Tuple
from config.settings import settings
from utils import logging

class WakeWordDetector:
    def __init__(self):
        self.porcupine = None

    def initialize(self) -> bool:
        """Initialize wake word detector"""
        try:
            logging.debug("Testing Picovoice API key...")
            if not settings.PICOVOICE_API_KEY:
                logging.error("Picovoice API key not found")
                return False

            # Test key validity
            test_result = pvporcupine.create(
                access_key=settings.PICOVOICE_API_KEY,
                keywords=["jarvis"]
            )
            test_result.delete()

            # If we get here, key is valid
            logging.debug("Picovoice API key is valid")

            self.porcupine = pvporcupine.create(
                access_key=settings.PICOVOICE_API_KEY,
                keywords=["jarvis"],
                sensitivities=[1.0]  # Maximum sensitivity
            )
            return True
        except Exception as e:
            logging.error(f"Wake word initialization error: {e}")
            return False

    def process_audio(self, audio_frame: bytes) -> bool:
        """Process audio frame for wake word detection"""
        try:
            pcm = struct.unpack_from("h" * self.porcupine.frame_length, audio_frame)
            keyword_index = self.porcupine.process(pcm)
            return keyword_index >= 0
        except Exception as e:
            logging.error(f"Wake word processing error: {e}")
            return False

    def cleanup(self):
        """Cleanup wake word detector"""
        if self.porcupine:
            self.porcupine.delete()
