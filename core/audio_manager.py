# core/audio_manager.py
import pygame
import pyaudio
import asyncio
from pathlib import Path
from typing import Optional
from config.settings import settings
from utils import logging

class AudioManager:
    def __init__(self):
        self.pa = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None
        self.is_speaking = asyncio.Event()
        
    async def init_playback(self):
        """Initialize audio playback"""
        pygame.mixer.init()
        
    async def play_audio(self, audio_path: Path) -> bool:
        """Play audio file"""
        try:
            self.is_speaking.set()
            pygame.mixer.music.load(str(audio_path))
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.1)
            return True
            
        except Exception as e:
            logging.error(f"Error playing audio: {e}")
            return False
        finally:
            self.is_speaking.clear()
            pygame.mixer.music.unload()
            
    def get_input_stream(self, sample_rate: int, channels: int, frames_per_buffer: int) -> Optional[pyaudio.Stream]:
        """Get audio input stream"""
        try:
            stream = self.pa.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=sample_rate,
                input=True,
                frames_per_buffer=frames_per_buffer
            )
            return stream
        except Exception as e:
            logging.error(f"Error creating input stream: {e}")
            return None
            
    async def cleanup(self):
        """Cleanup audio resources"""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.pa:
            self.pa.terminate()
        pygame.mixer.quit()