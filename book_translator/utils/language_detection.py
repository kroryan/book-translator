"""
Language Detection Utilities
=============================
Functions for detecting language and validating translations.
"""
from typing import Tuple, List, Set
from book_translator.config.constants import LANGUAGE_MARKERS


def detect_language_markers(text: str, language: str) -> Tuple[int, List[str], float]:
    """
    Detect language markers in text.
    
    Args:
        text: The text to analyze
        language: The language code to check for (e.g., 'en', 'es')
    
    Returns:
        Tuple of (marker_count, found_markers, ratio)
    """
    if language not in LANGUAGE_MARKERS:
        return 0, [], 0.0
    
    lang_info = LANGUAGE_MARKERS[language]
    markers = lang_info['markers']
    marker_type = lang_info['type']
    
    text_lower = text.lower()
    if marker_type == 'word':
        text_lower = ' ' + text_lower + ' '
    
    found = []
    count = 0
    
    for marker in markers:
        occurrences = text_lower.count(marker.lower())
        if occurrences > 0:
            count += occurrences
            found.append(marker.strip())
    
    # Calculate ratio based on text length
    text_length = len(text.split()) if marker_type == 'word' else len(text)
    ratio = count / max(text_length, 1)
    
    return count, found, ratio


def detect_language(text: str, candidates: List[str] = None) -> Tuple[str, float]:
    """
    Detect the most likely language of a text.
    
    Args:
        text: The text to analyze
        candidates: Optional list of language codes to consider
    
    Returns:
        Tuple of (language_code, confidence)
    """
    if candidates is None:
        candidates = list(LANGUAGE_MARKERS.keys())
    
    best_lang = 'unknown'
    best_score = 0.0
    
    for lang in candidates:
        count, _, ratio = detect_language_markers(text, lang)
        min_markers = LANGUAGE_MARKERS.get(lang, {}).get('min_markers', 3)
        
        # Score based on both count and ratio
        if count >= min_markers:
            score = count * (1 + ratio)
            if score > best_score:
                best_score = score
                best_lang = lang
    
    # Normalize confidence to 0-1 range
    confidence = min(best_score / 50, 1.0) if best_score > 0 else 0.0
    
    return best_lang, confidence


def is_likely_translated(
    original: str, 
    translated: str, 
    source_lang: str, 
    target_lang: str,
    similarity_threshold: float = 0.65
) -> bool:
    """
    Check if the translated text is actually different from the original.
    
    Args:
        original: Original text
        translated: Translated text
        source_lang: Source language code
        target_lang: Target language code
        similarity_threshold: Maximum word similarity to consider valid
    
    Returns:
        True if translation appears to have occurred
    """
    if not translated or not original:
        return False
    
    # If same language, can't easily verify
    if source_lang == target_lang:
        return True
    
    # If translated text is very short, accept it
    if len(translated) < 50:
        return True
    
    # Normalize texts for comparison (for Latin-alphabet languages)
    orig_normalized = ' '.join(original.lower().split())
    trans_normalized = ' '.join(translated.lower().split())
    
    # If they're identical, translation definitely failed
    if orig_normalized == trans_normalized:
        return False
    
    # For Latin-alphabet languages: Calculate word similarity
    if source_lang not in ['zh', 'ja', 'ko']:
        orig_words = set(orig_normalized.split())
        trans_words = set(trans_normalized.split())
        
        if len(orig_words) > 0:
            common_words = orig_words.intersection(trans_words)
            similarity = len(common_words) / len(orig_words)
            
            # Reject if similarity is very high
            if similarity > similarity_threshold:
                return False
    
    # Check source language markers in translation
    if source_lang in LANGUAGE_MARKERS:
        source_count, _, source_ratio = detect_language_markers(translated, source_lang)
        lang_info = LANGUAGE_MARKERS[source_lang]
        min_markers = lang_info['min_markers']
        
        # Calculate threshold based on text length
        word_count = len(translated.split()) if lang_info['type'] == 'word' else len(translated)
        
        if lang_info['type'] == 'word':
            threshold = max(min_markers + 3, min(10, word_count // 12))
        else:
            threshold = max(min_markers + 4, min(15, word_count // 25))
        
        if source_count > threshold:
            return False
    
    # Verify target language markers are present
    if target_lang in LANGUAGE_MARKERS:
        target_count, _, _ = detect_language_markers(translated, target_lang)
        target_min = LANGUAGE_MARKERS[target_lang]['min_markers']
        
        if target_count < target_min and len(translated) > 100:
            return False
    
    return True
