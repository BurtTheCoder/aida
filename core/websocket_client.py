# core/websocket_client.py
import websockets
import asyncio
import json
from typing import Optional
from config.settings import settings
from utils import logging

class WebSocketClient:
    def __init__(self):
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.connection_alive = asyncio.Event()
        self.keepalive_task: Optional[asyncio.Task] = None
        
    async def connect(self) -> bool:
        """Establish WebSocket connection"""
        headers = {"Authorization": f"Token {settings.DEEPGRAM_API_KEY}"}
        
        try:
            self.websocket = await websockets.connect(
                settings.websocket_url,
                extra_headers=headers
            )
            self.connection_alive.set()
            self.keepalive_task = asyncio.create_task(self._keep_alive())
            return True
            
        except Exception as e:
            logging.error(f"WebSocket connection error: {e}")
            return False
            
    async def _keep_alive(self):
        """Send keepalive messages"""
        while self.connection_alive.is_set():
            try:
                await self.websocket.send(json.dumps({"type": "KeepAlive"}))
                await asyncio.sleep(9)
            except Exception as e:
                logging.error(f"Keepalive error: {e}")
                break
                
    async def cleanup(self):
        """Cleanup WebSocket resources"""
        self.connection_alive.clear()
        if self.keepalive_task:
            self.keepalive_task.cancel()
        if self.websocket:
            await self.websocket.close()