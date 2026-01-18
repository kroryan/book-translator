"""
Unit Tests for Translation Service
===================================
Tests for the BookTranslator and language detection.
"""
import pytest
import sys
import os

# Setup test environment
os.environ.setdefault('BOOK_TRANSLATOR_ENV', 'testing')
os.environ.setdefault('VERBOSE_DEBUG', 'false')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from book_translator.config.constants import LANGUAGE_MARKERS
from book_translator.utils.language_detection import (
    detect_language_markers,
    detect_language,
    is_likely_translated
)
from book_translator.utils.text_processing import clean_translation_response


class TestLanguageMarkers:
    """Test language marker detection."""

    def test_english_markers_import(self):
        assert 'en' in LANGUAGE_MARKERS
        assert 'type' in LANGUAGE_MARKERS['en']
        assert 'markers' in LANGUAGE_MARKERS['en']

    def test_spanish_markers_import(self):
        assert 'es' in LANGUAGE_MARKERS
        assert len(LANGUAGE_MARKERS['es']['markers']) > 0

    def test_supported_languages(self):
        expected = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'zh', 'ja', 'ko']
        for lang in expected:
            assert lang in LANGUAGE_MARKERS, f"Missing language: {lang}"


class TestDetectLanguageMarkers:
    """Test detect_language_markers function."""

    def test_detect_english_text(self):
        text = "The quick brown fox jumps over the lazy dog. This is a test."
        count, markers, ratio = detect_language_markers(text, 'en')
        assert count > 0
        assert len(markers) > 0

    def test_detect_spanish_text(self):
        text = "El rápido zorro marrón salta sobre el perro perezoso. Esta es una prueba."
        count, markers, ratio = detect_language_markers(text, 'es')
        assert count > 0

    def test_detect_no_markers(self):
        text = "12345 67890"  # Numbers only
        count, markers, ratio = detect_language_markers(text, 'en')
        assert count == 0

    def test_empty_text(self):
        count, markers, ratio = detect_language_markers("", 'en')
        assert count == 0
        assert len(markers) == 0

    def test_chinese_character_detection(self):
        text = "这是一个测试。我们在学习中文。"
        count, markers, ratio = detect_language_markers(text, 'zh')
        assert count > 0

    def test_japanese_detection(self):
        text = "これはテストです。日本語を勉強しています。"
        count, markers, ratio = detect_language_markers(text, 'ja')
        assert count > 0

    def test_korean_detection(self):
        text = "이것은 테스트입니다. 한국어를 배우고 있습니다."
        count, markers, ratio = detect_language_markers(text, 'ko')
        assert count > 0


class TestDetectLanguage:
    """Test automatic language detection."""

    def test_detect_english(self):
        text = "The quick brown fox jumps over the lazy dog."
        lang, confidence = detect_language(text)
        assert lang == 'en'

    def test_detect_spanish(self):
        text = "El rápido zorro marrón salta sobre el perro perezoso."
        lang, confidence = detect_language(text)
        assert lang == 'es'

    def test_detect_french(self):
        # Use a longer text with more French markers for reliable detection
        text = "Le renard brun rapide saute par-dessus le chien paresseux. C'est une belle journée et il fait très beau. Je suis content de voir que tout va bien."
        lang, confidence = detect_language(text)
        assert lang == 'fr'


class TestTranslationValidation:
    """Test translation validation logic."""

    def test_empty_translation_fails(self):
        result = is_likely_translated("Hello world", "", "en", "es")
        assert result == False

    def test_identical_text_fails(self):
        text = "This is a test sentence with enough words to trigger detection."
        result = is_likely_translated(text, text, "en", "es")
        assert result == False

    def test_same_language_passes(self):
        result = is_likely_translated(
            "Hello world",
            "Hello world modified",
            "en", "en"
        )
        assert result == True

    def test_short_text_passes(self):
        result = is_likely_translated(
            "Hello",
            "Hola",
            "en", "es"
        )
        assert result == True

    def test_good_translation_passes(self):
        original = "The house is big. The garden is beautiful."
        translated = "La casa es grande. El jardín es hermoso."
        result = is_likely_translated(original, translated, "en", "es")
        assert result == True


class TestCleanTranslationResponse:
    """Test LLM response cleaning."""

    def test_removes_think_tags(self):
        response = "<think>Let me think about this...</think>Esta es la traducción."
        cleaned = clean_translation_response(response, "")
        assert "<think>" not in cleaned
        assert "traducción" in cleaned

    def test_removes_thinking_tags(self):
        response = "<thinking>Internal reasoning...</thinking>Final output."
        cleaned = clean_translation_response(response, "")
        assert "<thinking>" not in cleaned
        assert "Final output" in cleaned

    def test_removes_instruction_repetitions(self):
        response = "IMPORTANT: Return ONLY the translation.\nEsta es la traducción."
        cleaned = clean_translation_response(response, "")
        assert "IMPORTANT" not in cleaned
        assert "traducción" in cleaned

    def test_handles_empty_input(self):
        cleaned = clean_translation_response("", "")
        assert cleaned == ""

    def test_removes_translation_prefix(self):
        response = "Here is the translation:\nEsta es la traducción."
        cleaned = clean_translation_response(response, "")
        assert "Here is the translation" not in cleaned

    def test_removes_spanish_prefix(self):
        response = "Traducción:\nEste es el texto traducido."
        cleaned = clean_translation_response(response, "")
        assert "Traducción:" not in cleaned

    def test_removes_markdown_code_blocks(self):
        response = "```\nEsta es la traducción.\n```"
        cleaned = clean_translation_response(response, "")
        assert "```" not in cleaned

    def test_preserves_actual_content(self):
        response = "El gato está en la casa."
        cleaned = clean_translation_response(response, "")
        assert "El gato está en la casa" in cleaned


class TestBookTranslator:
    """Test BookTranslator class."""

    def test_initialization(self):
        from book_translator.services.translator import BookTranslator

        translator = BookTranslator(model_name='test-model')
        assert translator.model_name == 'test-model'

    def test_default_model(self):
        from book_translator.services.translator import BookTranslator

        translator = BookTranslator()
        assert translator.model_name is not None

    def test_has_cache(self):
        from book_translator.services.translator import BookTranslator

        translator = BookTranslator(model_name='test-model')
        assert translator.cache is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
