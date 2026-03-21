"""
Book Translator - Utility Functions
"""

from book_translator.utils.language_detection import (
    detect_language,
    detect_language_markers,
    is_likely_translated,
)
from book_translator.utils.logging import AppLogger, LogBuffer, debug_print, get_logger
from book_translator.utils.text_processing import (
    clean_translation_response,
    normalize_text,
    split_into_chunks,
)
from book_translator.utils.validators import (
    validate_file,
    validate_language,
    validate_model_name,
)

__all__ = [
    "detect_language_markers",
    "detect_language",
    "is_likely_translated",
    "split_into_chunks",
    "clean_translation_response",
    "normalize_text",
    "validate_file",
    "validate_language",
    "validate_model_name",
    "LogBuffer",
    "AppLogger",
    "get_logger",
    "debug_print",
]
