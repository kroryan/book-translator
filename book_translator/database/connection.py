"""
Database Connection Manager
===========================
Handles SQLite database connections with proper context management.
"""
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Generator

from book_translator.config import config
from book_translator.utils.logging import get_logger, debug_print


class Database:
    """
    Thread-safe SQLite database manager.
    
    Uses connection pooling and context managers for safe access.
    """
    
    _instance: Optional['Database'] = None
    _lock = threading.Lock()
    
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or Path(config.paths.db_path)
        self.logger = get_logger().db_logger
        self._local = threading.local()
        self._initialized = False
        
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def get_instance(cls, db_path: Path = None) -> 'Database':
        """Get singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(db_path)
            return cls._instance
    
    @property
    def connection(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = self._create_connection()
        return self._local.connection
    
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=config.security.db_timeout
        )
        conn.row_factory = sqlite3.Row
        
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        conn.execute("PRAGMA foreign_keys=ON")
        
        return conn
    
    def initialize(self) -> None:
        """Initialize database schema."""
        if self._initialized:
            return
        
        with self._lock:
            if self._initialized:
                return
            
            self._create_tables()
            self._create_indexes()
            self._initialized = True
            
            self.logger.info(f"Database initialized: {self.db_path}")
    
    def _create_tables(self) -> None:
        """Create database tables."""
        with self.connection:
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS translations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_filename TEXT NOT NULL,
                    translated_filename TEXT,
                    source_language TEXT NOT NULL,
                    target_language TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    progress REAL DEFAULT 0,
                    stage TEXT DEFAULT 'waiting',
                    original_text TEXT,
                    machine_translation TEXT,
                    translated_text TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    file_size INTEGER,
                    chunk_count INTEGER,
                    processing_time REAL,
                    CONSTRAINT valid_status CHECK (
                        status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')
                    ),
                    CONSTRAINT valid_progress CHECK (progress >= 0 AND progress <= 100)
                )
            """)
            
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS translation_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    translation_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    original_text TEXT NOT NULL,
                    machine_translation TEXT,
                    final_translation TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (translation_id) REFERENCES translations(id) ON DELETE CASCADE,
                    UNIQUE(translation_id, chunk_index)
                )
            """)
    
    def _create_indexes(self) -> None:
        """Create database indexes for performance."""
        with self.connection:
            # Translations indexes
            self.connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_translations_status 
                ON translations(status)
            """)
            self.connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_translations_created_at 
                ON translations(created_at DESC)
            """)
            self.connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_translations_filename 
                ON translations(original_filename)
            """)
            
            # Chunks indexes
            self.connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_translation_id 
                ON translation_chunks(translation_id, chunk_index)
            """)
    
    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database transactions."""
        conn = self.connection
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Transaction rolled back: {e}")
            raise
    
    def execute(
        self, 
        query: str, 
        params: tuple = None
    ) -> sqlite3.Cursor:
        """Execute a query."""
        try:
            if params:
                return self.connection.execute(query, params)
            return self.connection.execute(query)
        except sqlite3.Error as e:
            self.logger.error(f"Database error: {e}")
            raise
    
    def executemany(
        self, 
        query: str, 
        params_list: list
    ) -> sqlite3.Cursor:
        """Execute a query with multiple parameter sets."""
        try:
            return self.connection.executemany(query, params_list)
        except sqlite3.Error as e:
            self.logger.error(f"Database error: {e}")
            raise
    
    def fetchone(
        self, 
        query: str, 
        params: tuple = None
    ) -> Optional[sqlite3.Row]:
        """Execute query and fetch one result."""
        cursor = self.execute(query, params)
        return cursor.fetchone()
    
    def fetchall(
        self, 
        query: str, 
        params: tuple = None
    ) -> list:
        """Execute query and fetch all results."""
        cursor = self.execute(query, params)
        return cursor.fetchall()
    
    def close(self) -> None:
        """Close thread-local connection."""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
    
    def vacuum(self) -> None:
        """Optimize database by running VACUUM."""
        self.connection.execute("VACUUM")
        self.logger.info("Database vacuumed")


# Global accessor
_database: Optional[Database] = None


def get_database() -> Database:
    """Get database singleton."""
    global _database
    if _database is None:
        _database = Database.get_instance()
        _database.initialize()
    return _database


def reset_database() -> None:
    """Reset database singleton (for testing)."""
    global _database
    if _database:
        _database.close()
    _database = None
