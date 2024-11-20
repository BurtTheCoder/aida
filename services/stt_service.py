# services/stt_service.py
import json
import websockets
import logging
from typing import Optional, Dict, Any, AsyncGenerator
from config.settings import settings

class STTService:
    """Speech-to-text service using Deepgram"""
    def __init__(self):
        self.api_key = settings.DEEPGRAM_API_KEY
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        
    async def connect(self) -> bool:
        """Establish connection to Deepgram"""
        try:
            headers = {"Authorization": f"Token {self.api_key}"}
            self.websocket = await websockets.connect(
                settings.websocket_url,
                extra_headers=headers
            )
            return True
        except Exception as e:
            logging.error(f"Failed to connect to Deepgram: {e}")
            return False
            
    async def process_audio(self, audio_data: bytes) -> Optional[Dict[str, Any]]:
        """Process audio data and return transcription"""
        if not self.websocket:
            return None
            
        try:
            await self.websocket.send(audio_data)
            response = await self.websocket.recv()
            result = json.loads(response)
            
            if result.get('type') == 'Results':
                return {
                    'transcript': result['channel']['alternatives'][0]['transcript'],
                    'is_final': result.get('is_final', False)
                }
            return None
            
        except Exception as e:
            logging.error(f"Error processing audio: {e}")
            return None
            
    async def stream_transcription(self, audio_stream: AsyncGenerator[bytes, None]):
        """Stream audio data and yield transcriptions"""
        if not await self.connect():
            return
            
        try:
            async for audio_chunk in audio_stream:
                result = await self.process_audio(audio_chunk)
                if result and result['transcript'].strip():
                    yield result
                    
        except Exception as e:
            logging.error(f"Error in transcription stream: {e}")
        finally:
            await self.close()
            
    async def close(self):
        """Close the connection"""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None