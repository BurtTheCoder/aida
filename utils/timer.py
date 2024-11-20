# utils/timer.py
import threading
import asyncio
import logging
from config.settings import settings

class InactivityTimer:
    def __init__(self):
        self.inactivity_timer = None
        self.warning_timer = None
        self.warning_callback = None
        self.timeout_callback = None
        
    def start(self):
        """Start the inactivity timer"""
        self.reset()
        
    def reset(self):
        """Reset the timer"""
        self._cancel_timers()
        
        self.inactivity_timer = threading.Timer(
            settings.INACTIVITY_TIMEOUT,
            self._timeout
        )
        
        self.warning_timer = threading.Timer(
            settings.WARNING_PROMPT_TIME,
            self._warning
        )
        
        self.inactivity_timer.start()
        self.warning_timer.start()
        
    def stop(self):
        """Stop the timer"""
        self._cancel_timers()
        
    def _cancel_timers(self):
        """Cancel active timers"""
        if self.inactivity_timer:
            self.inactivity_timer.cancel()
        if self.warning_timer:
            self.warning_timer.cancel()
            
    def _warning(self):
        """Handle warning event"""
        logging.info("Inactivity warning triggered")
        if self.warning_callback:
            asyncio.create_task(self.warning_callback())
            
    def _timeout(self):
        """Handle timeout event"""
        logging.info("Inactivity timeout triggered")
        if self.timeout_callback:
            asyncio.create_task(self.timeout_callback())