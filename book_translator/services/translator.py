"""
Book Translator Service
=======================
Main translation service with two-stage translation approach.
"""
import time
import hashlib
from typing import Generator, Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from book_translator.config import config
from book_translator.config.constants import TranslationStatus
from book_translator.models.translation import TranslationProgress
from book_translator.services.ollama_client import OllamaClient, get_ollama_client
from book_translator.services.cache_service import TranslationCache, get_cache
from book_translator.services.terminology import TerminologyManager
from book_translator.utils.logging import get_logger, debug_print
from book_translator.utils.text_processing import (
    split_into_chunks,
    clean_translation_response,
    normalize_text
)
from book_translator.utils.language_detection import is_likely_translated


@dataclass
class ChunkResult:
    """Result of translating a single chunk."""
    chunk_index: int
    original: str
    translation: str
    success: bool
    error: Optional[str] = None
    from_cache: bool = False


class BookTranslator:
    """
    Two-stage book translator.
    
    Stage 1: Primary translation
    Stage 2: Reflection and improvement
    """
    
    def __init__(
        self, 
        model_name: str = None, 
        chunk_size: int = None,
        ollama_client: OllamaClient = None,
        cache: TranslationCache = None
    ):
        self.model_name = model_name or config.ollama.default_model
        self.chunk_size = chunk_size or config.translation.chunk_size
        self.client = ollama_client or get_ollama_client()
        self.cache = cache or get_cache()
        self.terminology = TerminologyManager()
        self.logger = get_logger().translation_logger
    
    def _build_stage1_prompt(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        previous_chunk: str = "",
        genre: str = "general"
    ) -> str:
        """Build prompt for stage 1 (primary translation)."""
        context_section = ""
        if previous_chunk:
            context_preview = previous_chunk[-200:] if len(previous_chunk) > 200 else previous_chunk
            context_section = f"""
CONTEXT (previous translation for continuity):
{context_preview}
---
"""
        
        terminology_section = self.terminology.get_context_for_prompt()
        if terminology_section:
            terminology_section = f"\n{terminology_section}\n"
        
        return f"""You are a professional literary translator. Translate the following {source_lang} text to {target_lang}.

GENRE: {genre}

REQUIREMENTS:
- Maintain the author's style, tone, and voice
- Preserve paragraph structure and formatting
- Keep proper nouns consistent
- Ensure natural, fluent {target_lang}
{terminology_section}{context_section}
TEXT TO TRANSLATE:
{text}

IMPORTANT: Return ONLY the translation, no explanations or notes."""
    
    def _build_stage2_prompt(
        self,
        original: str,
        draft: str,
        source_lang: str,
        target_lang: str,
        genre: str = "general"
    ) -> str:
        """Build prompt for stage 2 (reflection and improvement)."""
        return f"""You are a professional literary editor. Review and improve this {target_lang} translation.

GENRE: {genre}

ORIGINAL ({source_lang}):
{original}

DRAFT TRANSLATION ({target_lang}):
{draft}

REVIEW CRITERIA:
1. Accuracy - Does it convey the original meaning?
2. Fluency - Does it read naturally in {target_lang}?
3. Style - Does it preserve the author's voice?
4. Consistency - Are terms and names consistent?

Provide the IMPROVED translation only. If the draft is good, return it unchanged.
Return ONLY the final translation, no explanations."""
    
    def _translate_chunk_stage1(
        self,
        chunk: str,
        source_lang: str,
        target_lang: str,
        previous_chunk: str = "",
        genre: str = "general"
    ) -> str:
        """Translate a single chunk (stage 1)."""
        prompt = self._build_stage1_prompt(
            chunk, source_lang, target_lang, previous_chunk, genre
        )
        
        for attempt in range(config.translation.max_retries):
            response = self.client.generate(prompt, model=self.model_name)
            
            if response.success and response.text:
                cleaned = clean_translation_response(response.text, previous_chunk)
                
                # Validate translation
                if is_likely_translated(chunk, cleaned, source_lang, target_lang):
                    return cleaned
                else:
                    self.logger.warning(f"Translation validation failed, attempt {attempt + 1}")
            else:
                self.logger.error(f"Generation failed: {response.error}")
            
            if attempt < config.translation.max_retries - 1:
                time.sleep(config.translation.retry_delay * (attempt + 1))
        
        return f"[TRANSLATION_FAILED: {chunk[:50]}...]"
    
    def _translate_chunk_stage2(
        self,
        original: str,
        draft: str,
        source_lang: str,
        target_lang: str,
        genre: str = "general"
    ) -> str:
        """Improve a translation (stage 2)."""
        prompt = self._build_stage2_prompt(original, draft, source_lang, target_lang, genre)
        
        for attempt in range(config.translation.max_retries):
            response = self.client.generate(prompt, model=self.model_name)
            
            if response.success and response.text:
                cleaned = clean_translation_response(response.text, "")
                
                if is_likely_translated(original, cleaned, source_lang, target_lang):
                    return cleaned
                else:
                    self.logger.warning(f"Stage 2 validation failed, using draft")
                    return draft
            else:
                self.logger.error(f"Stage 2 generation failed: {response.error}")
            
            if attempt < config.translation.max_retries - 1:
                time.sleep(config.translation.retry_delay * (attempt + 1))
        
        # Fall back to draft if stage 2 fails
        return draft
    
    def _get_context_hash(self, previous_chunk: str) -> str:
        """Generate context hash for cache differentiation."""
        if not previous_chunk:
            return ""
        return hashlib.sha256(previous_chunk.encode('utf-8')).hexdigest()[:config.cache.context_hash_length]
    
    def translate_text(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        translation_id: int = None,
        genre: str = "general"
    ) -> Generator[TranslationProgress, None, None]:
        """
        Translate text using the two-stage approach.
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            translation_id: Optional ID for database tracking
            genre: Genre of the text
        
        Yields:
            TranslationProgress updates
        """
        # Normalize and split text
        text = normalize_text(text)
        chunks = split_into_chunks(text)
        total_chunks = len(chunks)
        
        self.logger.info(f"Starting translation: {total_chunks} chunks, {source_lang} -> {target_lang}")
        
        if config.logging.verbose_debug:
            debug_print(f"📚 Starting translation: {total_chunks} chunks", 'INFO', 'TRANS')
        
        # Stage 1: Primary translations
        draft_translations: List[str] = []
        
        for i, chunk in enumerate(chunks):
            chunk_num = i + 1
            previous_chunk = draft_translations[-1] if draft_translations else ""
            context_hash = self._get_context_hash(previous_chunk)
            
            if config.logging.verbose_debug:
                debug_print(f"📝 Stage 1: Chunk {chunk_num}/{total_chunks}", 'INFO', 'TRANS')
            
            # Check cache
            cached = self.cache.get(
                chunk, source_lang, target_lang, 
                f"{self.model_name}_stage1", context_hash
            )
            
            if cached and not cached['translated_text'].startswith('[TRANSLATION_FAILED'):
                draft = cached['machine_translation'] or cached['translated_text']
                if is_likely_translated(chunk, draft, source_lang, target_lang):
                    draft_translations.append(draft)
                    
                    yield TranslationProgress(
                        progress=(chunk_num / (total_chunks * 2)) * 100,
                        stage='primary_translation',
                        original_text='\n\n'.join(chunks),
                        machine_translation='\n\n'.join(draft_translations),
                        current_chunk=chunk_num,
                        total_chunks=total_chunks * 2
                    )
                    continue
            
            # Translate
            draft = self._translate_chunk_stage1(
                chunk, source_lang, target_lang, previous_chunk, genre
            )
            
            if not draft.startswith('[TRANSLATION_FAILED'):
                # Cache successful translation
                self.cache.set(
                    chunk, draft, draft,
                    source_lang, target_lang,
                    f"{self.model_name}_stage1", context_hash
                )
            
            draft_translations.append(draft)
            
            yield TranslationProgress(
                progress=(chunk_num / (total_chunks * 2)) * 100,
                stage='primary_translation',
                original_text='\n\n'.join(chunks),
                machine_translation='\n\n'.join(draft_translations),
                current_chunk=chunk_num,
                total_chunks=total_chunks * 2
            )
            
            # Delay between chunks
            if config.translation.chunk_delay > 0:
                time.sleep(config.translation.chunk_delay)
        
        # Stage 2: Reflection and improvement
        final_translations: List[str] = []
        
        for i, (chunk, draft) in enumerate(zip(chunks, draft_translations)):
            chunk_num = i + 1
            previous_final = final_translations[-1] if final_translations else ""
            context_hash = self._get_context_hash(previous_final)
            
            if config.logging.verbose_debug:
                debug_print(f"✨ Stage 2: Chunk {chunk_num}/{total_chunks}", 'INFO', 'TRANS')
            
            # Check cache for stage 2
            cached = self.cache.get(
                chunk, source_lang, target_lang,
                f"{self.model_name}_stage2", context_hash
            )
            
            if cached and not cached['translated_text'].startswith('[TRANSLATION_FAILED'):
                final = cached['translated_text']
                if is_likely_translated(chunk, final, source_lang, target_lang):
                    final_translations.append(final)
                    
                    yield TranslationProgress(
                        progress=((chunk_num + total_chunks) / (total_chunks * 2)) * 100,
                        stage='reflection_improvement',
                        original_text='\n\n'.join(chunks),
                        machine_translation='\n\n'.join(draft_translations),
                        translated_text='\n\n'.join(final_translations),
                        current_chunk=chunk_num + total_chunks,
                        total_chunks=total_chunks * 2
                    )
                    continue
            
            # Skip stage 2 if stage 1 failed
            if draft.startswith('[TRANSLATION_FAILED'):
                final_translations.append(draft)
            else:
                # Improve translation
                final = self._translate_chunk_stage2(
                    chunk, draft, source_lang, target_lang, genre
                )
                
                # Cache successful translation
                if not final.startswith('[TRANSLATION_FAILED'):
                    self.cache.set(
                        chunk, final, draft,
                        source_lang, target_lang,
                        f"{self.model_name}_stage2", context_hash
                    )
                
                final_translations.append(final)
            
            yield TranslationProgress(
                progress=((chunk_num + total_chunks) / (total_chunks * 2)) * 100,
                stage='reflection_improvement',
                original_text='\n\n'.join(chunks),
                machine_translation='\n\n'.join(draft_translations),
                translated_text='\n\n'.join(final_translations),
                current_chunk=chunk_num + total_chunks,
                total_chunks=total_chunks * 2
            )
            
            if config.translation.chunk_delay > 0:
                time.sleep(config.translation.chunk_delay)
        
        # Final result
        self.logger.info(f"Translation complete: {total_chunks} chunks processed")
        
        yield TranslationProgress(
            progress=100,
            stage='completed',
            original_text='\n\n'.join(chunks),
            machine_translation='\n\n'.join(draft_translations),
            translated_text='\n\n'.join(final_translations),
            current_chunk=total_chunks * 2,
            total_chunks=total_chunks * 2
        )
