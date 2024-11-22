# services/tts_service.py
from elevenlabs import play, stream
from elevenlabs.client import ElevenLabs, AsyncElevenLabs
from pathlib import Path
from config.settings import settings
from utils import logging
import asyncio
from typing import Optional, Union, AsyncGenerator

class TTSService:
    def __init__(self):
        # Initialize both sync and async clients
        self.client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
        self.async_client = AsyncElevenLabs(api_key=settings.ELEVENLABS_API_KEY)

        # Voice settings
        self.voice_id = "DsPSGqcqUCSgArVUBBGy"  # Your chosen voice ID
        self.model = "eleven_turbo_v2"

    async def generate_speech(self, text: str, output_path: Optional[Path] = None, stream_audio: bool = False) -> Union[bool, AsyncGenerator]:
        """Generate speech from text with optional streaming"""
        try:
            if stream_audio:
                # Return a stream for real-time playback
                audio_stream = self.client.generate(
                    text=text,
                    voice=self.voice_id,
                    model=self.model,
                    stream=True
                )
                return audio_stream
            else:
                # Generate and save audio file
                audio = self.client.generate(
                    text=text,
                    voice=self.voice_id,
                    model=self.model,
                )

                if output_path:
                    # If path provided, save the audio
                    with open(output_path, 'wb') as f:
                        f.write(audio)

                # Return the audio data directly
                return audio

        except Exception as e:
            logging.error(f"TTS error: {e}")
            return False

    async def play_speech(self, text: str, stream_audio: bool = True) -> bool:
        """Generate and play speech directly"""
        try:
            if stream_audio:
                # Stream generation and playback
                audio_stream = await self.generate_speech(text, stream_audio=True)
                stream(audio_stream)
            else:
                # Generate full audio and play
                audio = await self.generate_speech(text)
                play(audio)
            return True

        except Exception as e:
            logging.error(f"Error playing speech: {e}")
            return False

    async def get_voice_settings(self) -> dict:
        """Get current voice settings"""
        try:
            settings = await self.async_client.voices.get_settings(self.voice_id)
            return settings
        except Exception as e:
            logging.error(f"Error getting voice settings: {e}")
            return {}
