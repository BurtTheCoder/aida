# services/stt_service.py
import websockets
import asyncio
import json
import time
from typing import Optional, Dict, Any, Callable, Awaitable
from utils import logging
from config.settings import settings

class STTService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.transcript_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None
        self.connection_alive = asyncio.Event()
        self.keepalive_task: Optional[asyncio.Task] = None
        self.message_handler_task: Optional[asyncio.Task] = None
        self._connection_lock = asyncio.Lock()
        self._message_lock = asyncio.Lock()
        self._last_audio_time = 0
        self._reconnect_attempts = 0
        self.MAX_RECONNECT_ATTEMPTS = 5
        self.RECONNECT_DELAY = 2  # seconds

    async def initialize(self, transcript_callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> bool:
        """Initialize the STT service with callback"""
        try:
            self.transcript_callback = transcript_callback
            success = await self.connect()
            if success:
                self._reconnect_attempts = 0  # Reset reconnect attempts on successful connection
                return True
            return False
        except Exception as e:
            logging.error(f"Error initializing STT service: {e}")
            return False

    async def connect(self) -> bool:
        """Establish WebSocket connection with retry logic"""
        async with self._connection_lock:
            if self.websocket:
                await self.cleanup_connection()

            try:
                # Deepgram requires the Authorization header in this specific format
                headers = {
                    "Authorization": f"Token {self.api_key}",  # Make sure to add the comma
                    "Content-Type": "application/json"
                }

                logging.debug(f"Connecting to WebSocket URL: {settings.websocket_url}")

                self.websocket = await websockets.connect(
                    settings.websocket_url,
                    extra_headers=headers,
                    ping_interval=5,
                    ping_timeout=10,
                    close_timeout=5
                )

                # Verify connection
                try:
                    pong_waiter = await self.websocket.ping()
                    await asyncio.wait_for(pong_waiter, timeout=5)
                    logging.debug("WebSocket connection verified with ping/pong")
                except Exception as e:
                    logging.error(f"Failed to verify WebSocket connection: {e}")
                    return False

                self.connection_alive.set()

                # Start the message handler task
                if self.message_handler_task and not self.message_handler_task.done():
                    self.message_handler_task.cancel()
                self.message_handler_task = asyncio.create_task(self._handle_messages())

                # Start the keepalive task
                if self.keepalive_task and not self.keepalive_task.done():
                    self.keepalive_task.cancel()
                self.keepalive_task = asyncio.create_task(self._keep_alive())

                logging.info("WebSocket connection established successfully")
                return True

            except Exception as e:
                logging.error(f"WebSocket connection error: {e}")
                return False

    async def _keep_alive(self):
        """Send keepalive messages to maintain connection"""
        try:
            while self.connection_alive.is_set():
                try:
                    if self.websocket and not self.websocket.closed:
                        # Send ping
                        pong_waiter = await self.websocket.ping()
                        await asyncio.wait_for(pong_waiter, timeout=5)

                        # Send keepalive message if no recent audio
                        if time.time() - self._last_audio_time > 5:
                            keepalive_msg = json.dumps({"type": "KeepAlive"})
                            await self.websocket.send(keepalive_msg)

                    await asyncio.sleep(5)
                except Exception as e:
                    logging.error(f"Keepalive error: {e}")
                    await self._handle_connection_error()
                    break
        except asyncio.CancelledError:
            logging.debug("Keepalive task cancelled")
        except Exception as e:
            logging.error(f"Unhandled exception in keepalive task: {e}")

    async def _handle_messages(self):
        """Handle incoming WebSocket messages"""
        try:
            while self.connection_alive.is_set():
                try:
                    if not await self._check_connection():
                        continue

                    if self.websocket is None:
                        logging.error("Websocket is None")
                        await self._handle_connection_error()
                        continue

                    response = await self.websocket.recv()
                    result = json.loads(response)
                    await self._process_message(result)

                except websockets.exceptions.ConnectionClosed:
                    logging.warning("WebSocket connection closed")
                    await self._handle_connection_error()
                except json.JSONDecodeError as e:
                    logging.error(f"JSON decode error: {e}")
                except Exception as e:
                    logging.error(f"Error in message handling: {e}", exc_info=True)
                    await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logging.debug("Message handler task cancelled")
        except Exception as e:
            logging.error(f"Unhandled exception in message handler: {e}")

    async def _check_connection(self) -> bool:
        """Check websocket connection status"""
        if not self.websocket or self.websocket.closed:
            await asyncio.sleep(0.1)
            return False
        return True

    async def _process_message(self, result: Dict):
        """Process received websocket message"""
        msg_type = result.get('type')
        logging.debug(f"Received message type: {msg_type}")

        if msg_type == 'Results':
            await self._handle_transcript_result(result)
        elif msg_type == 'Error':
            logging.error(f"Received error from Deepgram: {result}")
        elif msg_type == 'Warning':
            logging.warning(f"Received warning from Deepgram: {result}")

    async def _handle_transcript_result(self, result: Dict):
        """Process transcript results from Deepgram"""
        channel_data = result.get('channel', {})
        alternatives = channel_data.get('alternatives', [])

        if alternatives:
            transcript = alternatives[0].get('transcript', '').strip()
            if transcript and self.transcript_callback:
                await self.transcript_callback({
                    'transcript': transcript,
                    'is_final': result.get('is_final', False),
                    'confidence': alternatives[0].get('confidence', 0.0)
                })
                logging.info(f"Processing transcript: '{transcript}' (final: {result.get('is_final', False)})")

    async def process_audio(self, audio_data: bytes) -> bool:
        """Process audio data"""
        if not self.connection_alive.is_set():
            logging.warning("Connection not alive, attempting reconnection")
            await self._handle_connection_error()
            return False

        try:
            if self.websocket and not self.websocket.closed:
                await self.websocket.send(audio_data)
                self._last_audio_time = time.time()
                return True

            # If we get here, the connection is closed
            logging.warning("WebSocket connection is closed")
            await self._handle_connection_error()
            return False

        except websockets.exceptions.ConnectionClosed:
            logging.warning("Connection closed while sending audio")
            await self._handle_connection_error()
            return False
        except Exception as e:
            logging.error(f"Error processing audio data: {e}")
            return False

    async def _handle_connection_error(self):
        """Handle connection errors with retry logic"""
        self.connection_alive.clear()

        if self._reconnect_attempts < self.MAX_RECONNECT_ATTEMPTS:
            self._reconnect_attempts += 1
            wait_time = self.RECONNECT_DELAY * self._reconnect_attempts
            logging.info(f"Attempting reconnection {self._reconnect_attempts}/{self.MAX_RECONNECT_ATTEMPTS} in {wait_time}s")

            await asyncio.sleep(wait_time)
            if await self.connect():
                logging.info("Reconnection successful")
                self._reconnect_attempts = 0
                return

        logging.error("Max reconnection attempts reached")

    async def cleanup_connection(self):
        """Clean up existing connection"""
        if self.websocket:
            try:
                # Send close message to server
                close_msg = json.dumps({"type": "CloseStream"})
                await self.websocket.send(close_msg)

                # Close the connection gracefully
                await self.websocket.close()
            except Exception as e:
                logging.error(f"Error closing WebSocket: {e}")
            finally:
                self.websocket = None
        self.connection_alive.clear()

    async def close(self):
        """Cleanup resources"""
        self.connection_alive.clear()

        # Cancel all background tasks
        tasks = [self.keepalive_task, self.message_handler_task]
        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logging.error(f"Error cancelling task: {e}")

        await self.cleanup_connection()
        logging.info("STT service closed")
