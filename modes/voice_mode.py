# modes/voice_mode.py
import asyncio
from utils import logging
import json
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

    async def run(self):
            """Run voice mode"""
            try:
                logging.debug("Initializing voice mode...")

                # Initialize audio manager
                await self.audio_manager.init_playback()
                logging.debug("Audio manager initialized")

                while not self.shutdown_event.is_set():
                    try:
                        logging.debug("Waiting for wake word...")
                        # Wait for wake word
                        await self.listen_for_wake_word()
                        logging.debug("Wake word detected, starting conversation")

                        # Handle conversation (greeting is now only in handle_conversation)
                        await self.handle_conversation()

                    except Exception as e:
                        logging.error(f"Error in conversation loop: {e}")
                        await asyncio.sleep(1)  # Prevent rapid retries

            except Exception as e:
                logging.error(f"Error in voice mode: {e}")

    async def listen_for_wake_word(self):
        """Listen for wake word activation"""
        if not self.wake_word_detector.initialize():
            logging.error("Failed to initialize wake word detector")
            return

        logging.debug("Wake word detector initialized, listening...")
        stream = self.audio_manager.get_input_stream(
            self.wake_word_detector.porcupine.sample_rate,
            settings.CHANNELS,
            self.wake_word_detector.porcupine.frame_length
        )

        if not stream:
            logging.error("Failed to get audio input stream")
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
        """Handle conversation after wake word detection"""
        logging.debug("Starting conversation handler")
        stream = None
        max_retries = 3
        retry_delay = 2

        # Add initial greeting
        await self.speak("Hello! How can I help you?")

        for attempt in range(max_retries):
            try:
                # Initialize STT with callback
                logging.debug("Initializing STT service...")
                if not await self.stt_service.initialize(
                    transcript_callback=self._handle_transcript
                ):
                    logging.error("Failed to initialize STT service")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        continue
                    return

                logging.debug("Getting audio input stream...")
                stream = self.audio_manager.get_input_stream(
                    settings.SAMPLE_RATE,
                    settings.CHANNELS,
                    settings.FRAME_SIZE
                )

                if not stream:
                    logging.error("Failed to get audio input stream")
                    return

                logging.debug("Starting conversation loop")
                silence_counter = 0
                while not self.shutdown_event.is_set():
                    try:
                        if not self.audio_manager.is_speaking.is_set():
                            frames = stream.read(settings.FRAME_SIZE, exception_on_overflow=False)
                            if frames:
                                # Add debug logging for audio levels
                                audio_level = max(abs(int.from_bytes(frames[i:i+2], 'little', signed=True))
                                            for i in range(0, len(frames), 2))
                                if audio_level > 500:  # Adjust this threshold as needed
                                    logging.debug(f"Audio input level: {audio_level}")
                                    silence_counter = 0
                                else:
                                    silence_counter += 1

                                success = await self.stt_service.process_audio(frames)
                                if not success:
                                    logging.warning("Failed to process audio frame")
                                    silence_counter += 1

                                # If too much silence, log a debug message
                                if silence_counter > 100:  # Adjust this threshold as needed
                                    logging.debug("No significant audio input detected")
                                    silence_counter = 0

                        await asyncio.sleep(0.01)
                    except Exception as e:
                        logging.error(f"Error in conversation loop: {e}")
                        break

                # If we get here, try to reconnect
                if attempt < max_retries - 1:
                    logging.info("Attempting to reconnect...")
                    await asyncio.sleep(retry_delay)
                    continue
                break

            except Exception as e:
                logging.error(f"Error in conversation handler: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    break
            finally:
                if stream:
                    stream.stop_stream()
                    stream.close()
                if self.stt_service:
                    await self.stt_service.close()

    async def _handle_transcript(self, result: Dict[str, Any]):
        """Handle incoming transcripts"""
        try:
            if result['is_final']:
                logging.debug(f"Processing final transcript: {result['transcript']}")
                response = await self.assistant.process_input(result['transcript'])
                await self.speak(response)
        except Exception as e:
            logging.error(f"Error handling transcript: {e}")

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
