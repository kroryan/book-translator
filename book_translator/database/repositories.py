"""
Database Repositories
=====================
Data access patterns for translation entities.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any

from book_translator.database.connection import Database, get_database
from book_translator.config.constants import TranslationStatus
from book_translator.utils.logging import get_logger


class TranslationRepository:
    """
    Repository for translation records.
    
    Provides CRUD operations and queries for translations.
    """
    
    def __init__(self, database: Database = None):
        self.db = database or get_database()
        self.logger = get_logger().db_logger
    
    def create(
        self,
        original_filename: str,
        source_language: str,
        target_language: str,
        model_name: str,
        original_text: str = None,
        file_size: int = None
    ) -> int:
        """Create a new translation record."""
        with self.db.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO translations (
                    original_filename, source_language, target_language,
                    model_name, status, stage, original_text, file_size
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                original_filename, source_language, target_language,
                model_name, TranslationStatus.PENDING.value, 'waiting',
                original_text, file_size
            ))
            
            translation_id = cursor.lastrowid
            self.logger.info(f"Created translation {translation_id}")
            return translation_id
    
    def get_by_id(self, translation_id: int) -> Optional[Dict[str, Any]]:
        """Get translation by ID."""
        row = self.db.fetchone(
            "SELECT * FROM translations WHERE id = ?",
            (translation_id,)
        )
        return dict(row) if row else None
    
    def get_all(
        self,
        status: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get all translations with optional filtering."""
        if status:
            rows = self.db.fetchall("""
                SELECT * FROM translations 
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (status, limit, offset))
        else:
            rows = self.db.fetchall("""
                SELECT * FROM translations 
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
        
        return [dict(row) for row in rows]
    
    def update_progress(
        self,
        translation_id: int,
        progress: float,
        stage: str,
        machine_translation: str = None,
        translated_text: str = None
    ) -> None:
        """Update translation progress."""
        with self.db.transaction() as conn:
            if translated_text:
                conn.execute("""
                    UPDATE translations SET
                        progress = ?,
                        stage = ?,
                        status = ?,
                        machine_translation = ?,
                        translated_text = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    progress, stage, TranslationStatus.PROCESSING.value,
                    machine_translation, translated_text, translation_id
                ))
            elif machine_translation:
                conn.execute("""
                    UPDATE translations SET
                        progress = ?,
                        stage = ?,
                        status = ?,
                        machine_translation = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    progress, stage, TranslationStatus.PROCESSING.value,
                    machine_translation, translation_id
                ))
            else:
                conn.execute("""
                    UPDATE translations SET
                        progress = ?,
                        stage = ?,
                        status = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (progress, stage, TranslationStatus.PROCESSING.value, translation_id))
    
    def mark_completed(
        self,
        translation_id: int,
        translated_text: str,
        translated_filename: str,
        processing_time: float = None,
        chunk_count: int = None
    ) -> None:
        """Mark translation as completed."""
        with self.db.transaction() as conn:
            conn.execute("""
                UPDATE translations SET
                    status = ?,
                    progress = 100,
                    stage = 'completed',
                    translated_text = ?,
                    translated_filename = ?,
                    processing_time = ?,
                    chunk_count = ?,
                    completed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                TranslationStatus.COMPLETED.value,
                translated_text, translated_filename,
                processing_time, chunk_count, translation_id
            ))
            
            self.logger.info(f"Translation {translation_id} completed")
    
    def mark_failed(
        self,
        translation_id: int,
        error_message: str
    ) -> None:
        """Mark translation as failed."""
        with self.db.transaction() as conn:
            conn.execute("""
                UPDATE translations SET
                    status = ?,
                    error_message = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (TranslationStatus.FAILED.value, error_message, translation_id))
            
            self.logger.error(f"Translation {translation_id} failed: {error_message}")
    
    def mark_cancelled(self, translation_id: int) -> None:
        """Mark translation as cancelled."""
        with self.db.transaction() as conn:
            conn.execute("""
                UPDATE translations SET
                    status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (TranslationStatus.CANCELLED.value, translation_id))
            
            self.logger.info(f"Translation {translation_id} cancelled")
    
    def delete(self, translation_id: int) -> bool:
        """Delete a translation."""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM translations WHERE id = ?",
                (translation_id,)
            )
            deleted = cursor.rowcount > 0
            
            if deleted:
                self.logger.info(f"Translation {translation_id} deleted")
            
            return deleted
    
    def get_stats(self) -> Dict[str, Any]:
        """Get translation statistics."""
        stats = {}
        
        # Count by status
        rows = self.db.fetchall("""
            SELECT status, COUNT(*) as count
            FROM translations
            GROUP BY status
        """)
        stats['by_status'] = {row['status']: row['count'] for row in rows}
        
        # Total count
        row = self.db.fetchone("SELECT COUNT(*) as total FROM translations")
        stats['total'] = row['total'] if row else 0
        
        # Average processing time
        row = self.db.fetchone("""
            SELECT AVG(processing_time) as avg_time
            FROM translations
            WHERE status = 'completed' AND processing_time IS NOT NULL
        """)
        stats['avg_processing_time'] = row['avg_time'] if row else None
        
        return stats


class TranslationChunkRepository:
    """Repository for translation chunks."""
    
    def __init__(self, database: Database = None):
        self.db = database or get_database()
    
    def save_chunk(
        self,
        translation_id: int,
        chunk_index: int,
        original_text: str,
        machine_translation: str = None,
        final_translation: str = None
    ) -> int:
        """Save or update a translation chunk."""
        with self.db.transaction() as conn:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO translation_chunks (
                    translation_id, chunk_index, original_text,
                    machine_translation, final_translation
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                translation_id, chunk_index, original_text,
                machine_translation, final_translation
            ))
            return cursor.lastrowid
    
    def get_chunks(self, translation_id: int) -> List[Dict[str, Any]]:
        """Get all chunks for a translation."""
        rows = self.db.fetchall("""
            SELECT * FROM translation_chunks
            WHERE translation_id = ?
            ORDER BY chunk_index
        """, (translation_id,))
        return [dict(row) for row in rows]
    
    def delete_chunks(self, translation_id: int) -> None:
        """Delete all chunks for a translation."""
        with self.db.transaction() as conn:
            conn.execute(
                "DELETE FROM translation_chunks WHERE translation_id = ?",
                (translation_id,)
            )


# Global accessor
_translation_repo: Optional[TranslationRepository] = None


def get_translation_repository() -> TranslationRepository:
    """Get translation repository singleton."""
    global _translation_repo
    if _translation_repo is None:
        _translation_repo = TranslationRepository()
    return _translation_repo
