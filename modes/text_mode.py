# modes/text_mode.py
from core.assistant import AidaAssistant
from utils import logging
import asyncio
from services.tts_service import TTSService
from core.audio_manager import AudioManager
from config.settings import settings

class TextMode:
    def __init__(self, assistant: AidaAssistant, use_tts: bool = True):
        self.assistant = assistant
        self.use_tts = use_tts
        self.tts_service = TTSService() if use_tts else None
        self.audio_manager = AudioManager() if use_tts else None
        self.shutdown_event = asyncio.Event()

    async def run(self):
        """Run text mode"""
        try:
            print("\nAida: Hello! How can I help you?")
            print("Commands: 'exit' or 'quit' to exit, 'help' for help")
            print("------------------------------------------\n")

            while not self.shutdown_event.is_set():
                try:
                    user_input = input("You: ").strip()
                    if not user_input:
                        continue

                    if user_input.lower() in ['exit', 'quit']:
                        break

                    if user_input.lower() == 'help':
                        self.show_help()
                        continue

                    print("Processing...")
                    response = await self.assistant.process_input(user_input)
                    print(f"\nAida: {response}\n")

                    if self.use_tts:
                        await self.speak(response)

                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logging.error(f"Error processing input: {e}")
                    print("Aida: I encountered an error. Please try again.")

        except Exception as e:
            logging.error(f"Error in text mode: {e}")

    def show_help(self):
        """Show help message"""
        print("\nCommands:")
        print("  'exit' or 'quit' - Exit the program")
        print("  'help' - Show this help message")
        print("------------------------------------------\n")

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
        if self.audio_manager:
            await self.audio_manager.cleanup()