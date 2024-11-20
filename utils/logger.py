# utils/logger.py
import logging as python_logging
import sys

# Create and configure the logger
_logger = python_logging.getLogger('aida')

# Only add handler if none exists and not already configured
if not _logger.handlers and not _logger.parent.handlers:
    _handler = python_logging.StreamHandler(sys.stdout)
    _formatter = python_logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    _handler.setFormatter(_formatter)
    _logger.addHandler(_handler)
    _logger.setLevel(python_logging.INFO)

    # Prevent propagation to avoid duplicate logs
    _logger.propagate = False

# Export logging functions
debug = _logger.debug
info = _logger.info
warning = _logger.warning
error = _logger.error
critical = _logger.critical

def set_debug_mode(enabled: bool = False):
    """Set debug mode"""
    _logger.setLevel(python_logging.DEBUG if enabled else python_logging.INFO)
