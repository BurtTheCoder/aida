# services/tts_service.py
from elevenlabs.client import ElevenLabs
from elevenlabs import save
from pathlib import Path
from config.settings import settings
from utils import logging

class TTSService:
    def __init__(self):
        self.client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
        
    async def generate_speech(self, text: str, output_path: Path) -> bool:
        """Generate speech from text"""
        try:
            audio_stream = self.client.generate(
                text=text,
                voice="DsPSGqcqUCSgArVUBBGy",
                model="eleven_turbo_v2",
                optimize_streaming_latency=3
            )
            
            save(audio_stream, str(output_path))
            return True
            
        except Exception as e:
            logging.error(f"TTS error: {e}")
            return False