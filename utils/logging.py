# utils/logging.py
from .logger import debug, info, warning, error, critical, set_debug_mode as _set_debug_mode

def setup_logging(debug: bool = False):
    """Configure logging level"""
    _set_debug_mode(debug)

# Export for compatibility
__all__ = ['debug', 'info', 'warning', 'error', 'critical', 'setup_logging']
