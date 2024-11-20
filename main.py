# main.py
import asyncio
from utils import logging
from pathlib import Path
from config.settings import settings
from utils.logging import setup_logging
from modes.voice_mode import VoiceMode
from modes.text_mode import TextMode
from core.assistant import AidaAssistant
import argparse

def setup_args():
    """Set up command line argument parsing"""
    parser = argparse.ArgumentParser(description='Aida AI Assistant')
    parser.add_argument(
        '--mode',
        choices=['voice', 'text'],
        default='voice',
        help='Mode of operation: voice or text'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    parser.add_argument(
        '--no-tts',
        action='store_true',
        help='Disable text-to-speech in text mode'
    )
    parser.add_argument(
        '--user-id',
        default='default_user',
        help='User ID for memory persistence'
    )
    return parser.parse_args()

async def main():
    """Main program entry point"""
    try:
        args = setup_args()
        setup_logging(debug=args.debug)

        # Initialize assistant
        assistant = AidaAssistant(user_id=args.user_id)

        try:
            if args.mode == 'text':
                mode = TextMode(assistant, use_tts=not args.no_tts)
            else:
                mode = VoiceMode(assistant)

            await mode.run()

        except KeyboardInterrupt:
            logging.info("Received keyboard interrupt, shutting down...")
        except Exception as e:
            logging.error(f"Unexpected error in main loop: {e}", exc_info=True)
        finally:
            await mode.cleanup()

    except Exception as e:
        logging.error(f"Critical error during startup: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        settings.AUDIO_DIR.mkdir(exist_ok=True)
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Program terminated by user")
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
