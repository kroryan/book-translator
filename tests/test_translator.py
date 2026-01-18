"""
Unit Tests for Language Detection
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestLanguageMarkers:
    """Test language marker detection."""
    
    def test_english_markers_import(self):
        from translator import LANGUAGE_MARKERS
        assert 'en' in LANGUAGE_MARKERS
        assert 'type' in LANGUAGE_MARKERS['en']
        assert 'markers' in LANGUAGE_MARKERS['en']
    
    def test_spanish_markers_import(self):
        from translator import LANGUAGE_MARKERS
        assert 'es' in LANGUAGE_MARKERS
        assert len(LANGUAGE_MARKERS['es']['markers']) > 0
    
    def test_supported_languages(self):
        from translator import LANGUAGE_MARKERS
        expected = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'zh', 'ja', 'ko']
        for lang in expected:
            assert lang in LANGUAGE_MARKERS, f"Missing language: {lang}"


class TestDetectLanguageMarkers:
    """Test detect_language_markers function."""
    
    def test_detect_english_text(self):
        from translator import detect_language_markers
        text = "The quick brown fox jumps over the lazy dog. This is a test."
        count, markers, ratio = detect_language_markers(text, 'en')
        assert count > 0
        assert len(markers) > 0
    
    def test_detect_spanish_text(self):
        from translator import detect_language_markers
        text = "El rápido zorro marrón salta sobre el perro perezoso. Esta es una prueba."
        count, markers, ratio = detect_language_markers(text, 'es')
        assert count > 0
    
    def test_detect_no_markers(self):
        from translator import detect_language_markers
        text = "12345 67890"  # Numbers only
        count, markers, ratio = detect_language_markers(text, 'en')
        assert count == 0
    
    def test_empty_text(self):
        from translator import detect_language_markers
        count, markers, ratio = detect_language_markers("", 'en')
        assert count == 0
        assert len(markers) == 0
    
    def test_chinese_character_detection(self):
        from translator import detect_language_markers
        text = "这是一个测试。我们在学习中文。"
        count, markers, ratio = detect_language_markers(text, 'zh')
        assert count > 0


class TestTranslationValidation:
    """Test translation validation logic."""
    
    @pytest.fixture
    def translator(self):
        from translator import BookTranslator
        return BookTranslator(model_name="test-model")
    
    def test_empty_translation_fails(self, translator):
        result = translator._is_likely_translated("Hello world", "", "en", "es")
        assert result == False
    
    def test_identical_text_fails(self, translator):
        text = "This is a test sentence."
        result = translator._is_likely_translated(text, text, "en", "es")
        assert result == False
    
    def test_same_language_passes(self, translator):
        result = translator._is_likely_translated(
            "Hello world", 
            "Hello world modified", 
            "en", "en"
        )
        assert result == True
    
    def test_short_text_passes(self, translator):
        result = translator._is_likely_translated(
            "Hello",
            "Hola",
            "en", "es"
        )
        assert result == True
    
    def test_good_translation_passes(self, translator):
        original = "The house is big. The garden is beautiful."
        translated = "La casa es grande. El jardín es hermoso."
        result = translator._is_likely_translated(original, translated, "en", "es")
        assert result == True


class TestCleanTranslationResponse:
    """Test LLM response cleaning."""
    
    @pytest.fixture
    def translator(self):
        from translator import BookTranslator
        return BookTranslator(model_name="test-model")
    
    def test_removes_think_tags(self, translator):
        response = "<think>Let me think about this...</think>Esta es la traducción."
        cleaned = translator._clean_translation_response(response, "")
        assert "<think>" not in cleaned
        assert "traducción" in cleaned
    
    def test_removes_instruction_repetitions(self, translator):
        response = "IMPORTANT: Return ONLY the translation.\nEsta es la traducción."
        cleaned = translator._clean_translation_response(response, "")
        assert "IMPORTANT" not in cleaned
        assert "traducción" in cleaned
    
    def test_handles_empty_input(self, translator):
        cleaned = translator._clean_translation_response("", "")
        assert cleaned == ""
    
    def test_removes_translation_prefix(self, translator):
        response = "Here is the translation:\nEsta es la traducción."
        cleaned = translator._clean_translation_response(response, "")
        assert "Here is the translation" not in cleaned
