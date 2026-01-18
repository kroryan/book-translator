"""
Logging Utilities
=================
Centralized logging configuration and utilities.
"""
import os
import re
import logging
import threading
from collections import deque
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import List, Dict, Optional
from book_translator.config import config


class LogBuffer:
    """Thread-safe circular buffer for storing logs for frontend visibility."""
    
    def __init__(self, max_size: int = None):
        self.buffer = deque(maxlen=max_size or config.logging.log_buffer_size)
        self.lock = threading.Lock()
        self.last_id = 0
    
    def add(self, level: str, source: str, message: str) -> Dict:
        """Add a log entry to the buffer."""
        with self.lock:
            self.last_id += 1
            entry = {
                'id': self.last_id,
                'timestamp': datetime.now().strftime('%H:%M:%S.%f')[:-3],
                'level': level,
                'source': source,
                'message': message
            }
            self.buffer.append(entry)
            return entry
    
    def get_all(self) -> List[Dict]:
        """Get all log entries."""
        with self.lock:
            return list(self.buffer)
    
    def get_since(self, since_id: int) -> List[Dict]:
        """Get log entries since a specific ID."""
        with self.lock:
            return [e for e in self.buffer if e['id'] > since_id]
    
    def clear(self):
        """Clear the buffer."""
        with self.lock:
            self.buffer.clear()
            self.last_id = 0


# Global log buffer instance
log_buffer = LogBuffer()


class ANSIStripFormatter(logging.Formatter):
    """Formatter that strips ANSI codes for file output."""
    
    ANSI_PATTERN = re.compile(r'\033\[[0-9;]*m')
    
    def format(self, record):
        message = super().format(record)
        return self.ANSI_PATTERN.sub('', message)


class AppLogger:
    """Application logger with multiple handlers."""
    
    def __init__(self, log_dir: str = None):
        self.log_dir = log_dir or config.paths.log_folder
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Create loggers
        self.app_logger = self._setup_logger('book_translator.app', 'app.log')
        self.translation_logger = self._setup_logger('book_translator.translation', 'translations.log')
        self.api_logger = self._setup_logger('book_translator.api', 'api.log')
        self.db_logger = self._setup_logger('book_translator.database', 'database.log')
    
    def _setup_logger(self, name: str, filename: str) -> logging.Logger:
        """Set up a logger with file and console handlers."""
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG if config.logging.verbose_debug else logging.INFO)
        
        # Prevent duplicate handlers
        if logger.handlers:
            return logger
        
        # File handler with ANSI stripping
        file_path = os.path.join(self.log_dir, filename)
        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=config.logging.log_file_max_bytes,
            backupCount=config.logging.log_file_backup_count
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(ANSIStripFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(file_handler)
        
        # Console handler (with colors)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG if config.logging.verbose_debug else logging.INFO)
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        ))
        logger.addHandler(console_handler)
        
        return logger


# Global logger instance
_logger_instance: Optional[AppLogger] = None


def get_logger() -> AppLogger:
    """Get or create the global logger instance."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = AppLogger()
    return _logger_instance


def debug_print(message: str, level: str = 'INFO', source: str = 'DEBUG'):
    """
    Print to console and add to log buffer for frontend visibility.
    
    Args:
        message: The message to log
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        source: Source identifier
    """
    # Strip ANSI codes for the buffer
    clean_message = re.sub(r'\033\[[0-9;]*m', '', message)
    log_buffer.add(level, source, clean_message)
    
    # Print to console with colors if verbose
    if config.logging.verbose_debug:
        print(message)
