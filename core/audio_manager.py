# core/audio_manager.py
import pygame
import pyaudio
import asyncio
from pathlib import Path
from typing import Optional, Generator
from config.settings import settings
from utils import logging
from elevenlabs import stream as elevenlabs_stream

class AudioManager:
    def __init__(self):
        self.pa = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None
        self.is_speaking = asyncio.Event()
        self.mixer_initialized = False
        self._check_audio_devices()

    def _check_audio_devices(self):
            """Check available audio devices"""
            try:
                info = self.pa.get_host_api_info_by_index(0)
                numdevices = info.get('deviceCount')

                logging.debug(f"Found {numdevices} audio devices:")

                for i in range(0, numdevices):
                    device_info = self.pa.get_device_info_by_host_api_device_index(0, i)
                    if device_info.get('maxInputChannels') > 0:  # If it's an input device
                        logging.debug(f"Input Device {i}: {device_info.get('name')}")

            except Exception as e:
                logging.error(f"Error checking audio devices: {e}")

    async def init_playback(self):
        """Initialize audio playback"""
        try:
            pygame.mixer.init()
            self.mixer_initialized = True
        except Exception as e:
            logging.error(f"Error initializing audio mixer: {e}")
            self.mixer_initialized = False

    async def play_audio_stream(self, audio_stream: Generator) -> bool:
        """Play audio directly from stream"""
        try:
            self.is_speaking.set()
            elevenlabs_stream(audio_stream)  # This handles the streaming playback
            return True
        except Exception as e:
            logging.error(f"Error playing audio stream: {e}")
            return False
        finally:
            self.is_speaking.clear()

    async def play_audio(self, audio_path: Path) -> bool:
        """Play audio from file (kept for compatibility)"""
        if not self.mixer_initialized:
            logging.error("Audio mixer not initialized")
            return False

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

    def get_input_stream(self, sample_rate: int, channels: int, frames_per_buffer: int):
            """Get audio input stream"""
            try:
                logging.debug(f"Creating input stream (rate={sample_rate}, channels={channels})")
                stream = self.pa.open(
                    format=pyaudio.paInt16,
                    channels=channels,
                    rate=sample_rate,
                    input=True,
                    frames_per_buffer=frames_per_buffer
                )
                logging.debug("Input stream created successfully")
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
        if self.mixer_initialized:
            pygame.mixer.quit()
