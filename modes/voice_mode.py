# modes/voice_mode.py
import asyncio
from utils import logging
import json
from core.assistant import AidaAssistant
from core.audio_manager import AudioManager
from core.websocket_client import WebSocketClient
from services.wake_word import WakeWordDetector
from services.tts_service import TTSService
from utils.timer import InactivityTimer
from config.settings import settings

class VoiceMode:
    def __init__(self, assistant: AidaAssistant):
        self.assistant = assistant
        self.audio_manager = AudioManager()
        self.websocket_client = WebSocketClient()
        self.wake_word_detector = WakeWordDetector()
        self.tts_service = TTSService()
        self.timer = InactivityTimer()

        self.shutdown_event = asyncio.Event()
        self.wake_word_queue = asyncio.Queue()

    async def run(self):
        """Run voice mode"""
        try:
            while not self.shutdown_event.is_set():
                # Wait for wake word
                await self.listen_for_wake_word()

                # Greet user
                await self.speak("Hello! How can I help you?")

                # Handle conversation
                await self.handle_conversation()

        except Exception as e:
            logging.error(f"Error in voice mode: {e}")

    async def listen_for_wake_word(self):
        """Listen for wake word activation"""
        if not self.wake_word_detector.initialize():
            return

        stream = self.audio_manager.get_input_stream(
            self.wake_word_detector.porcupine.sample_rate,
            settings.CHANNELS,
            self.wake_word_detector.porcupine.frame_length
        )

        try:
            while not self.shutdown_event.is_set():
                audio_frame = stream.read(self.wake_word_detector.porcupine.frame_length)
                if self.wake_word_detector.process_audio(audio_frame):
                    logging.info("Wake word detected!")
                    break
        finally:
            stream.stop_stream()
            stream.close()

    async def handle_conversation(self):
        """Handle conversation after wake word detection"""
        if not await self.websocket_client.connect():
            return

        stream = self.audio_manager.get_input_stream(
            settings.SAMPLE_RATE,
            settings.CHANNELS,
            settings.FRAME_SIZE
        )

        current_utterance = []
        self.timer.start()

        try:
            while not self.shutdown_event.is_set() and self.websocket_client.connection_alive.is_set():
                if not self.audio_manager.is_speaking.is_set():
                    frames = stream.read(settings.FRAME_SIZE, exception_on_overflow=False)

                    if frames:
                        await self.websocket_client.websocket.send(frames)

                        try:
                            response = await asyncio.wait_for(
                                self.websocket_client.websocket.recv(),
                                timeout=0.1
                            )

                            result = json.loads(response)
                            if result.get('type') == 'Results':
                                transcript = result['channel']['alternatives'][0]['transcript']

                                if transcript.strip() and result.get('is_final', False):
                                    current_utterance.append(transcript)
                                    full_transcript = " ".join(current_utterance)

                                    response_text = await self.assistant.process_input(full_transcript)
                                    await self.speak(response_text)

                                    current_utterance = []
                                    self.timer.reset()

                        except asyncio.TimeoutError:
                            pass

                await asyncio.sleep(0.01)

        finally:
            stream.stop_stream()
            stream.close()

    async def speak(self, text: str):
        """Convert text to speech and play it"""
        try:
            output_path = settings.AUDIO_DIR / "response.mp3"
            if await self.tts_service.generate_speech(text, output_path):
                await self.audio_manager.play_audio(output_path)
        except Exception as e:
            logging.error(f"Error in speech generation: {e}")

    async def cleanup(self):
        """Clean up resources"""
        self.shutdown_event.set()
        self.timer.stop()
        await self.audio_manager.cleanup()
        await self.websocket_client.cleanup()
        self.wake_word_detector.cleanup()
