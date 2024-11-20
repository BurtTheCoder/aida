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
            self.porcupine = pvporcupine.create(
                access_key=settings.PICOVOICE_API_KEY,
                keywords=["jarvis"],
                sensitivities=[0.5]
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