"""
Translation Cache Service
=========================
Caching layer for translations to avoid repeated API calls.
"""
import hashlib
import sqlite3
from typing import Optional, Dict
from datetime import datetime
from book_translator.config import config
from book_translator.utils.logging import get_logger, debug_print


class TranslationCache:
    """Cache for storing and retrieving translations."""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.paths.cache_db_path
        self.logger = get_logger().app_logger
        self._init_db()
    
    def _init_db(self):
        """Initialize the cache database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS translation_cache (
                    hash_key TEXT PRIMARY KEY,
                    source_lang TEXT,
                    target_lang TEXT,
                    original_text TEXT,
                    translated_text TEXT,
                    machine_translation TEXT,
                    model TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Create indexes for faster lookups
            conn.execute('CREATE INDEX IF NOT EXISTS idx_cache_hash ON translation_cache(hash_key)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_cache_lookup ON translation_cache(hash_key, last_used)')
    
    def _generate_hash(
        self, 
        text: str, 
        source_lang: str, 
        target_lang: str, 
        model: str = "", 
        context_hash: str = ""
    ) -> str:
        """Generate a unique hash for a translation request."""
        key = f"{text}:{source_lang}:{target_lang}:{model}:{context_hash}".encode('utf-8')
        return hashlib.sha256(key).hexdigest()
    
    def get(
        self, 
        text: str, 
        source_lang: str, 
        target_lang: str, 
        model: str = "", 
        context_hash: str = ""
    ) -> Optional[Dict[str, str]]:
        """
        Get a cached translation if available.
        
        Args:
            text: Original text
            source_lang: Source language
            target_lang: Target language
            model: Model used for translation
            context_hash: Hash of context (for context-aware caching)
        
        Returns:
            Dict with translated_text and machine_translation, or None
        """
        if not config.cache.enabled:
            return None
        
        hash_key = self._generate_hash(text, source_lang, target_lang, model, context_hash)
        
        debug_print(
            f"[CACHE LOOKUP] hash={hash_key[:16]}... model={model} ctx={context_hash[:8] if context_hash else 'none'}",
            'DEBUG', 'CACHE'
        )
        debug_print(f"  Text preview: {text[:60].replace(chr(10), ' ')}...", 'DEBUG', 'CACHE')
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.execute('''
                    SELECT translated_text, machine_translation
                    FROM translation_cache
                    WHERE hash_key = ?
                ''', (hash_key,))
                
                result = cur.fetchone()
                if result:
                    debug_print(f"  [HIT] Found cached translation ({len(result[0])} chars)", 'INFO', 'CACHE')
                    debug_print(f"  [HIT] Preview: {result[0][:80].replace(chr(10), ' ')}...", 'DEBUG', 'CACHE')

                    # Update last_used timestamp
                    conn.execute('''
                        UPDATE translation_cache
                        SET last_used = CURRENT_TIMESTAMP
                        WHERE hash_key = ?
                    ''', (hash_key,))

                    return {
                        'translated_text': result[0],
                        'machine_translation': result[1]
                    }

            debug_print(f"  [MISS] No cached translation found", 'INFO', 'CACHE')
            return None
            
        except sqlite3.Error as e:
            self.logger.error(f"Cache lookup error: {e}")
            return None
    
    def set(
        self, 
        text: str, 
        translated_text: str, 
        machine_translation: str,
        source_lang: str, 
        target_lang: str, 
        model: str = "", 
        context_hash: str = ""
    ):
        """
        Store a translation in the cache.
        
        Args:
            text: Original text
            translated_text: Final translated text
            machine_translation: Machine translation (stage 1)
            source_lang: Source language
            target_lang: Target language
            model: Model used
            context_hash: Context hash
        """
        if not config.cache.enabled:
            debug_print(f"[CACHE DISABLED] Skipping cache store", 'DEBUG', 'CACHE')
            return

        hash_key = self._generate_hash(text, source_lang, target_lang, model, context_hash)

        debug_print(
            f"[CACHE STORE] hash={hash_key[:16]}... model={model}",
            'DEBUG', 'CACHE'
        )
        debug_print(f"  Original: {len(text)} chars", 'DEBUG', 'CACHE')
        debug_print(f"  Translation: {len(translated_text)} chars", 'DEBUG', 'CACHE')
        debug_print(f"  Preview: {translated_text[:80].replace(chr(10), ' ')}...", 'DEBUG', 'CACHE')

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO translation_cache
                    (hash_key, source_lang, target_lang, original_text, translated_text,
                     machine_translation, model, created_at, last_used)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ''', (hash_key, source_lang, target_lang, text, translated_text,
                      machine_translation, model))
            debug_print(f"  [STORED] Successfully cached translation", 'DEBUG', 'CACHE')
        except sqlite3.Error as e:
            debug_print(f"  [ERROR] Cache store failed: {e}", 'ERROR', 'CACHE')
            self.logger.error(f"Cache store error: {e}")
    
    def cleanup(self, days: int = None):
        """
        Remove old cache entries.
        
        Args:
            days: Maximum age in days (uses config if not specified)
        """
        days = days or config.cache.max_age_days
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    f"DELETE FROM translation_cache WHERE last_used < datetime('now', '-{days} days')"
                )
                deleted = cursor.rowcount
                if deleted > 0:
                    self.logger.info(f"Cleaned up {deleted} old cache entries")
        except sqlite3.Error as e:
            self.logger.error(f"Cache cleanup error: {e}")
    
    def clear(self):
        """Clear all cached translations."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM translation_cache")
                self.logger.info("Translation cache cleared")
        except sqlite3.Error as e:
            self.logger.error(f"Cache clear error: {e}")
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.execute("SELECT COUNT(*) FROM translation_cache")
                total = cur.fetchone()[0]
                
                cur = conn.execute(
                    "SELECT COUNT(*) FROM translation_cache WHERE last_used > datetime('now', '-1 day')"
                )
                recent = cur.fetchone()[0]
                
                return {
                    'total_entries': total,
                    'entries_last_24h': recent
                }
        except sqlite3.Error:
            return {'total_entries': 0, 'entries_last_24h': 0}


# Global cache instance
_cache_instance: Optional[TranslationCache] = None


def get_cache() -> TranslationCache:
    """Get or create the global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = TranslationCache()
    return _cache_instance
