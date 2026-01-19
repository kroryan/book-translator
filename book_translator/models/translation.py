"""
Translation Data Models
=======================
Core data structures for translations.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from book_translator.config.constants import TranslationStatus


@dataclass
class TranslationChunk:
    """Represents a single chunk of text to be translated."""
    id: int
    translation_id: int
    chunk_number: int
    original_text: str
    machine_translation: Optional[str] = None
    translated_text: Optional[str] = None
    status: TranslationStatus = TranslationStatus.PENDING
    error_message: Optional[str] = None
    attempts: int = 0


@dataclass
class Translation:
    """Represents a complete translation job."""
    id: Optional[int] = None
    filename: str = ""
    source_lang: str = ""
    target_lang: str = ""
    model: str = ""
    status: TranslationStatus = TranslationStatus.PENDING
    progress: float = 0.0
    current_chunk: int = 0
    total_chunks: int = 0
    original_text: Optional[str] = None
    machine_translation: Optional[str] = None
    translated_text: Optional[str] = None
    detected_language: Optional[str] = None
    genre: str = "unknown"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'filename': self.filename,
            'source_lang': self.source_lang,
            'target_lang': self.target_lang,
            'model': self.model,
            'status': self.status.value if isinstance(self.status, TranslationStatus) else self.status,
            'progress': self.progress,
            'current_chunk': self.current_chunk,
            'total_chunks': self.total_chunks,
            'detected_language': self.detected_language,
            'genre': self.genre,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'error_message': self.error_message,
        }


@dataclass
class TranslationResult:
    """Result of a translation operation."""
    success: bool
    translated_text: Optional[str] = None
    machine_translation: Optional[str] = None
    error_message: Optional[str] = None
    chunks_processed: int = 0
    total_chunks: int = 0


@dataclass
class TranslationProgress:
    """Progress update during translation."""
    progress: float
    stage: str
    original_text: str = ""
    machine_translation: str = ""
    translated_text: str = ""
    current_chunk: int = 0
    total_chunks: int = 0
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for SSE events."""
        result = {
            'progress': self.progress,
            'stage': self.stage,
            'current_chunk': self.current_chunk,
            'total_chunks': self.total_chunks,
        }
        if self.original_text:
            result['original_text'] = self.original_text
        if self.machine_translation:
            result['machine_translation'] = self.machine_translation
        if self.translated_text:
            result['translated_text'] = self.translated_text
        if self.error:
            result['error'] = self.error
        return result


@dataclass
class CachedTranslation:
    """A cached translation entry."""
    hash_key: str
    source_lang: str
    target_lang: str
    original_text: str
    translated_text: str
    machine_translation: str
    created_at: datetime
    last_used: datetime
