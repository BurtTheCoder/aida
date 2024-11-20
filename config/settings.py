# config/settings.py
import os
from pathlib import Path
from dotenv import load_dotenv

class Settings:
    def __init__(self):
        load_dotenv()
        
        # Timeouts and delays
        self.INACTIVITY_TIMEOUT = 300
        self.WARNING_PROMPT_TIME = 250
        self.RECONNECT_DELAY = 2
        self.MAX_RECONNECT_ATTEMPTS = 5
        
        # API Keys
        self.ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
        self.DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
        self.PICOVOICE_API_KEY = os.getenv("PICOVOICE_API_KEY")
        self.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
        self.PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
        
        # Paths
        self.AUDIO_DIR = Path("audio")
        self.AUDIO_DIR.mkdir(exist_ok=True)
        
        # Audio settings
        self.SAMPLE_RATE = 16000
        self.CHANNELS = 1
        self.FRAME_SIZE = 1024
        
    @property
    def websocket_url(self) -> str:
        return "wss://api.deepgram.com/v1/listen?encoding=linear16&sample_rate=16000&channels=1&interim_results=true&utterance_end_ms=1000"

settings = Settings()  # Singleton instance