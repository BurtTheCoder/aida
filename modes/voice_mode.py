# modes/voice_mode.py
import asyncio
from utils import logging
from core.assistant import AidaAssistant
from core.audio_manager import AudioManager
from services.wake_word import WakeWordDetector
from services.tts_service import TTSService
from services.stt_service import STTService
from utils.timer import InactivityTimer
from config.settings import settings
from typing import Dict, Any

class VoiceMode:
    def __init__(self, assistant: AidaAssistant):
        self.assistant = assistant
        self.audio_manager = AudioManager()
        self.wake_word_detector = WakeWordDetector()
        self.tts_service = TTSService()
        self.stt_service = STTService(api_key=settings.DEEPGRAM_API_KEY)
        self.timer = InactivityTimer()
        self.shutdown_event = asyncio.Event()
        self.wake_word_queue = asyncio.Queue()
        self.silence_threshold = 100
        self.max_retries = 3
        self.is_listening = False
        self.processing_response = False

    async def run(self):
        """Run voice mode"""
        try:
            logging.debug("Initializing voice mode...")

            # Initialize audio manager
            await self.audio_manager.init_playback()
            logging.debug("Audio manager initialized")

            # Ensure wake word detector is initialized
            if not self.wake_word_detector.initialize():
                logging.error("Failed to initialize wake word detector")
                return

            logging.debug("Wake word detector initialized")

            while not self.shutdown_event.is_set():
                try:
                    logging.debug("Waiting for wake word...")
                    # Wait for wake word
                    await self.listen_for_wake_word()
                    logging.debug("Wake word detected, starting conversation")

                    # Handle conversation
                    await self.handle_conversation()

                except Exception as e:
                    logging.error(f"Error in conversation loop: {e}")
                    await asyncio.sleep(1)  # Prevent rapid retries

        except Exception as e:
            logging.error(f"Error in voice mode: {e}")

    async def listen_for_wake_word(self):
        """Listen for wake word activation"""
        logging.debug("Starting wake word detection")
        # Initialize porcupine before accessing properties
        if not self.wake_word_detector.initialize():
            logging.error("Failed to initialize wake word detector")
            return

        # Check if porcupine is initialized before accessing properties
        if not self.wake_word_detector.porcupine:
            logging.error("Porcupine not initialized")
            return

        stream = self.audio_manager.get_input_stream(
            self.wake_word_detector.porcupine.sample_rate,
            settings.CHANNELS,
            self.wake_word_detector.porcupine.frame_length
        )

        if not stream:
            logging.error("Failed to get audio input stream for wake word detection")
            return

        try:
            while not self.shutdown_event.is_set():
                try:
                    audio_frame = stream.read(
                        self.wake_word_detector.porcupine.frame_length,
                        exception_on_overflow=False
                    )
                    if self.wake_word_detector.process_audio(audio_frame):
                        logging.info("Wake word detected!")
                        break
                except Exception as e:
                    logging.error(f"Error processing audio frame: {e}")
                    break
        finally:
            logging.debug("Cleaning up wake word detection")
            stream.stop_stream()
            stream.close()

    async def handle_conversation(self):
        """Handle continuation of conversation after wake word detection."""
        stream = None
        try:
            logging.debug("Starting conversation handler")
            self.is_listening = True

            # Initialize STT with the transcript callback
            init_attempts = 3
            for attempt in range(init_attempts):
                if await self.stt_service.initialize(transcript_callback=self._handle_transcript):
                    break
                if attempt < init_attempts - 1:
                    logging.warning(f"STT initialization attempt {attempt + 1} failed, retrying...")
                    await asyncio.sleep(1)
                else:
                    logging.error("Failed to initialize STT service after multiple attempts")
                    return

            # Get audio stream
            stream = self.audio_manager.get_input_stream(
                sample_rate=16000,
                channels=1,
                frames_per_buffer=1024
            )
            if not stream:
                logging.error("Failed to get audio input stream")
                return

            # Confirm readiness
            await self.speak("Listening now, tell me how I can assist.")
            silence_counter = 0
            processing_response = False
            logging.debug("Entering main audio processing loop...")

            while not self.shutdown_event.is_set() and self.is_listening:
                try:
                    # If we're processing a response, send empty frames to keep connection alive
                    if processing_response:
                        await self.stt_service.process_audio(b'\x00' * 2048)
                        await asyncio.sleep(0.1)
                        continue

                    frames = stream.read(1024, exception_on_overflow=False)
                    audio_level = max(abs(
                        int.from_bytes(frames[i:i+2], 'little', signed=True))
                        for i in range(0, len(frames), 2)
                    )
                    logging.debug(f"Audio Level: {audio_level}")

                    if audio_level > 200:
                        silence_counter = 0
                    else:
                        silence_counter += 1

                    if silence_counter > 100:
                        logging.info("Silence detected, ending session")
                        self.is_listening = False
                        break

                    # Send audio to STT service
                    if not await self.stt_service.process_audio(frames):
                        logging.warning("Failed to process audio frame")
                        await asyncio.sleep(0.1)
                        continue

                    await asyncio.sleep(0.001)

                except Exception as e:
                    logging.error(f"Error processing audio frame: {e}")
                    break

        except Exception as e:
            logging.error(f"Error in conversation handler: {e}")
        finally:
            self.is_listening = False
            if stream:
                stream.stop_stream()
                stream.close()
            await self.stt_service.close()

    async def _handle_transcript(self, result: Dict[str, Any]):
        """Handle incoming transcripts"""
        try:
            logging.debug(f"Received transcript result: {result}")
            if result.get('is_final'):
                transcript = result.get('transcript', '').strip()
                if transcript:
                    logging.info(f"Processing final transcript: {transcript}")

                    # Set processing flag
                    self.processing_response = True

                    try:
                        response = await self.assistant.process_input(transcript)
                        if response:
                            logging.info(f"Assistant response: {response}")
                            await self.speak(response)
                    finally:
                        # Clear processing flag
                        self.processing_response = False

        except Exception as e:
            logging.error(f"Error handling transcript: {e}")
            self.processing_response = False

    async def speak(self, text: str):
        """Convert text to speech and play it"""
        try:
            # Generate streaming audio
            audio_stream = self.tts_service.client.generate(
                text=text,
                voice=self.tts_service.voice_id,
                model=self.tts_service.model,
                stream=True
            )
            await self.audio_manager.play_audio_stream(audio_stream)
        except Exception as e:
            logging.error(f"Error in speech generation: {e}")

    async def cleanup(self):
        """Clean up resources"""
        self.shutdown_event.set()
        self.timer.stop()
        await self.audio_manager.cleanup()
        self.wake_word_detector.cleanup()
        if self.stt_service:
            await self.stt_service.close()
