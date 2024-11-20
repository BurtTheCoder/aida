# utils/logging.py
import logging

# Configure logger
logger = logging.getLogger('aida')

def setup_logging(debug: bool = False):
    """Configure logging"""
    level = logging.DEBUG if debug else logging.INFO

    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Configure logger
    logger.setLevel(level)
    logger.addHandler(console_handler)

    # Clear any existing handlers to prevent duplicate logs
    logger.handlers = [console_handler]

# Export logger functions for convenience
debug = logger.debug
info = logger.info
warning = logger.warning
error = logger.error
critical = logger.critical
