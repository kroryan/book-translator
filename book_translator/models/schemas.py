"""
Request/Response Schemas
========================
Pydantic-like validation schemas for API requests and responses.
"""
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class TranslateRequest:
    """Request schema for translation endpoint."""
    source_language: str
    target_language: str
    model: str
    genre: str = "unknown"
    
    def validate(self) -> List[str]:
        """Validate the request and return list of errors."""
        errors = []
        if not self.source_language:
            errors.append("source_language is required")
        if not self.target_language:
            errors.append("target_language is required")
        if not self.model:
            errors.append("model is required")
        return errors


@dataclass
class TranslationResponse:
    """Response schema for translation operations."""
    success: bool
    translation_id: Optional[int] = None
    message: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        result = {'success': self.success}
        if self.translation_id is not None:
            result['translation_id'] = self.translation_id
        if self.message:
            result['message'] = self.message
        if self.error:
            result['error'] = self.error
        return result


@dataclass
class ModelInfo:
    """Information about an available Ollama model."""
    name: str
    size: Optional[int] = None
    modified_at: Optional[str] = None
    digest: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'size': self.size,
            'modified_at': self.modified_at,
        }


@dataclass
class HealthStatus:
    """Health check response."""
    status: str
    ollama_connected: bool
    database_connected: bool
    version: str
    
    def to_dict(self) -> dict:
        return {
            'status': self.status,
            'ollama_connected': self.ollama_connected,
            'database_connected': self.database_connected,
            'version': self.version,
        }


@dataclass
class MetricsData:
    """Application metrics."""
    total_requests: int = 0
    successful_translations: int = 0
    failed_translations: int = 0
    average_translation_time: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    
    def to_dict(self) -> dict:
        return {
            'total_requests': self.total_requests,
            'successful_translations': self.successful_translations,
            'failed_translations': self.failed_translations,
            'average_translation_time': self.average_translation_time,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'success_rate': (self.successful_translations / self.total_requests * 100) if self.total_requests > 0 else 0,
        }
