"""
Text Processing Utilities
=========================
Functions for processing and manipulating text.
"""
import re
from typing import List, Tuple
from book_translator.config import config


def normalize_text(text: str) -> str:
    """
    Normalize text by removing extra whitespace and standardizing line endings.
    
    Args:
        text: Text to normalize
    
    Returns:
        Normalized text
    """
    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Remove excessive blank lines (keep max 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def split_into_chunks(text: str, max_length: int = None) -> List[str]:
    """
    Split text into smaller chunks for translation.
    Ensures clean boundaries at paragraph level when possible.
    
    Args:
        text: Text to split
        max_length: Maximum chunk length (uses config if not specified)
    
    Returns:
        List of text chunks
    """
    if max_length is None:
        max_length = config.translation.max_prompt_length
    
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = []
    current_length = 0
    
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        
        para_length = len(paragraph)
        
        # If single paragraph is too long, split by sentences
        if para_length > max_length:
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = []
                current_length = 0
            
            # Split long paragraph by sentences
            sentences = re.split(r'(?<=[.!?])\s+', paragraph)
            sentence_chunk = []
            sentence_length = 0
            
            for sentence in sentences:
                if sentence_length + len(sentence) > max_length and sentence_chunk:
                    chunks.append(' '.join(sentence_chunk))
                    sentence_chunk = []
                    sentence_length = 0
                sentence_chunk.append(sentence)
                sentence_length += len(sentence) + 1
            
            if sentence_chunk:
                chunks.append(' '.join(sentence_chunk))
            continue
        
        # Check if adding this paragraph would exceed the limit
        if current_length + para_length + 2 > max_length and current_chunk:
            chunks.append('\n\n'.join(current_chunk))
            current_chunk = []
            current_length = 0
        
        current_chunk.append(paragraph)
        current_length += para_length + 2
    
    # Don't forget the last chunk
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))
    
    return chunks if chunks else [text]


def clean_translation_response(translation: str, previous_chunk: str = "") -> str:
    """
    Clean the LLM response to remove unwanted content.
    
    Args:
        translation: Raw translation from LLM
        previous_chunk: Previous chunk for detecting repetition
    
    Returns:
        Cleaned translation
    """
    if not translation:
        return ""
    
    translation = translation.strip()
    
    # Remove <think> tags and their content (common in reasoning models)
    translation = re.sub(r'<think>.*?</think>', '', translation, flags=re.DOTALL | re.IGNORECASE)
    translation = translation.strip()
    
    # Remove common instruction repetitions
    unwanted_patterns = [
        r'IMPORTANT:\s*Return ONLY the translation.*?\n+',
        r'IMPORTANTE:\s*Devuelve SOLO la traducción.*?\n+',
        r'TEXT TO TRANSLATE:.*?\n+',
        r'TEXTO A TRADUCIR:.*?\n+',
        r'^\s*Here is the translation:?\s*\n*',
        r'^\s*Here\'s the translation:?\s*\n*',
        r'^\s*Translation:?\s*\n*',
        r'^\s*Translated text:?\s*\n*',
        r'^\s*\*\*Translation:?\*\*\s*\n*',
        r'^\s*---+\s*\n*',
    ]
    
    for pattern in unwanted_patterns:
        translation = re.sub(pattern, '', translation, flags=re.IGNORECASE | re.MULTILINE)
    
    translation = translation.strip()
    
    # Remove leading/trailing quotes that might have been added
    if translation.startswith('"') and translation.endswith('"'):
        translation = translation[1:-1]
    if translation.startswith("'") and translation.endswith("'"):
        translation = translation[1:-1]
    
    # Remove repetition from previous chunk if present
    if previous_chunk and len(previous_chunk) > 50:
        # Get last 100 chars of previous chunk
        prev_end = previous_chunk[-100:].strip()
        if translation.startswith(prev_end):
            translation = translation[len(prev_end):].strip()
    
    return translation


def extract_proper_nouns(text: str) -> List[str]:
    """
    Extract proper nouns (capitalized words/phrases) from text.
    
    Args:
        text: Text to analyze
    
    Returns:
        List of unique proper nouns
    """
    # Match capitalized words that are not at sentence start
    pattern = r'(?<!^)(?<![.!?]\s)\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
    nouns = re.findall(pattern, text, re.MULTILINE)
    return list(set(nouns))


def count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def count_characters(text: str, include_spaces: bool = True) -> int:
    """Count characters in text."""
    if include_spaces:
        return len(text)
    return len(text.replace(' ', '').replace('\n', '').replace('\t', ''))
