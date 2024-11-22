# services/stt_service.py
import websockets
import asyncio
import json
import time
from typing import Optional, Dict, Any, AsyncGenerator, Callable, List
from utils import logging
from config.settings import settings

class STTService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.transcript_callback: Optional[Callable] = None
        self.connection_alive = asyncio.Event()
        self.keepalive_task: Optional[asyncio.Task] = None
        self.message_handler_task: Optional[asyncio.Task] = None
        self.current_utterance = []
        self._connection_lock = asyncio.Lock()
        self._message_lock = asyncio.Lock()
        self._audio_buffer: List[bytes] = []
        self._buffer_processor_task: Optional[asyncio.Task] = None
        self._last_audio_time = 0

    async def initialize(self, transcript_callback: Callable = None):
        """Initialize the STT service with optional callback"""
        try:
            self.transcript_callback = transcript_callback
            await self.connect()
            self._buffer_processor_task = asyncio.create_task(self._process_audio_buffer())
            return True
        except Exception as e:
            logging.error(f"Error initializing STT service: {e}")
            return False

    async def connect(self) -> bool:
        """Establish WebSocket connection"""
        async with self._connection_lock:
            if self.websocket:
                await self.cleanup_connection()

            headers = {"Authorization": f"Token {self.api_key}"}

            try:
                self.websocket = await websockets.connect(
                    settings.websocket_url,
                    extra_headers=headers,
                    ping_interval=5,  # Add ping/pong for connection health
                    ping_timeout=10
                )
                self.connection_alive.set()

                # Cancel existing tasks if they exist
                if self.keepalive_task and not self.keepalive_task.done():
                    self.keepalive_task.cancel()
                if self.message_handler_task and not self.message_handler_task.done():
                    self.message_handler_task.cancel()

                # Start new tasks
                self.keepalive_task = asyncio.create_task(self._keep_alive())
                self.message_handler_task = asyncio.create_task(self._handle_messages())

                logging.info("WebSocket connection established successfully")
                return True

            except Exception as e:
                logging.error(f"WebSocket connection error: {e}")
                return False

    async def _keep_alive(self):
        """Send keepalive messages"""
        try:
            while self.connection_alive.is_set():
                try:
                    if self.websocket and not self.websocket.closed:
                        # Send both keepalive and empty audio chunk
                        await self.websocket.send(json.dumps({"type": "KeepAlive"}))
                        if time.time() - self._last_audio_time > 5:  # If no audio for 5 seconds
                            await self.websocket.send(b'\x00' * 640)  # Send silent audio frame
                    await asyncio.sleep(5)
                except Exception as e:
                    logging.error(f"Keepalive error: {e}")
                    await self._handle_connection_error()
                    break
        except asyncio.CancelledError:
            logging.debug("Keepalive task cancelled")

    async def _process_audio_buffer(self):
        """Process buffered audio data"""
        try:
            while self.connection_alive.is_set():
                if self._audio_buffer:
                    try:
                        if self.websocket and not self.websocket.closed:
                            data = self._audio_buffer.pop(0)
                            await self.websocket.send(data)
                            self._last_audio_time = time.time()
                    except Exception as e:
                        logging.error(f"Error sending buffered audio: {e}")
                        await self._handle_connection_error()
                await asyncio.sleep(0.001)  # Small sleep to prevent CPU spinning
        except asyncio.CancelledError:
            logging.debug("Buffer processor task cancelled")

    async def _handle_connection_error(self):
        """Handle connection errors and attempt reconnection"""
        self.connection_alive.clear()
        await self.connect()

    async def cleanup_connection(self):
        """Clean up existing connection"""
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
            self.websocket = None
        self.connection_alive.clear()

    async def _handle_messages(self):
        """Handle incoming WebSocket messages"""
        try:
            while self.connection_alive.is_set():
                try:
                    if not self.websocket or self.websocket.closed:
                        await asyncio.sleep(0.1)
                        continue

                    async with self._message_lock:
                        response = await self.websocket.recv()
                        result = json.loads(response)

                        if result.get('type') == 'Results':
                            await self._process_transcript(result)

                except websockets.exceptions.ConnectionClosed:
                    logging.warning("WebSocket connection closed")
                    await self._handle_connection_error()
                except Exception as e:
                    logging.error(f"Error in message handling: {e}")
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logging.debug("Message handler task cancelled")

    async def _process_transcript(self, result: Dict):
        """Process transcript result"""
        try:
            transcript = result.get('channel', {}).get('alternatives', [{}])[0].get('transcript', '')
            if transcript.strip():
                is_final = result.get('is_final', False)

                if is_final:
                    self.current_utterance.append(transcript)
                    full_transcript = " ".join(self.current_utterance)

                    if self.transcript_callback:
                        await self.transcript_callback({
                            'transcript': full_transcript,
                            'is_final': True,
                            'confidence': result.get('channel', {}).get('alternatives', [{}])[0].get('confidence', 0.0)
                        })

                    self.current_utterance = []
                else:
                    if self.transcript_callback:
                        await self.transcript_callback({
                            'transcript': transcript,
                            'is_final': False,
                            'confidence': result.get('channel', {}).get('alternatives', [{}])[0].get('confidence', 0.0)
                        })
        except Exception as e:
            logging.error(f"Error processing transcript: {e}")

    async def process_audio(self, audio_data: bytes) -> bool:
        """Process audio data"""
        if not self.connection_alive.is_set():
            await self._handle_connection_error()
            return False

        try:
            # Add to buffer instead of sending directly
            self._audio_buffer.append(audio_data)

            # Prevent buffer from growing too large
            if len(self._audio_buffer) > 100:  # Adjust this value as needed
                self._audio_buffer = self._audio_buffer[-50:]  # Keep last 50 chunks

            return True
        except Exception as e:
            logging.error(f"Error processing audio data: {e}")
            return False

    async def close(self):
        """Cleanup WebSocket resources"""
        self.connection_alive.clear()

        # Cancel all background tasks
        for task in [self.keepalive_task, self.message_handler_task, self._buffer_processor_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Clear audio buffer
        self._audio_buffer.clear()

        await self.cleanup_connection()
        logging.info("STT service closed")

    def _handle_error(self, error: Any, **kwargs):
        """Handle connection errors"""
        logging.error(f"Deepgram error: {error}")

    def _handle_metadata(self, metadata: Any, **kwargs):
        """Handle connection metadata"""
        logging.debug(f"Deepgram metadata: {metadata}")

    async def _handle_transcript(self, result: Dict[str, Any]):
        """Handle incoming transcripts"""
        try:
            if result['is_final']:
                logging.info(f"Processing final transcript: {result['transcript']}")
                response = await self.assistant.process_input(result['transcript'])
                await self.speak(response)
        except Exception as e:
            logging.error(f"Error handling transcript: {e}", exc_info=True)
