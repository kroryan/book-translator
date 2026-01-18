"""
Unit Tests for Configuration System
"""
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    AppConfig, ServerConfig, OllamaConfig, TranslationConfig,
    CacheConfig, FileConfig, LoggingConfig, _get_bool_env, _get_int_env, _get_float_env
)


class TestEnvHelpers:
    """Test environment variable helper functions."""
    
    def test_get_bool_env_true_values(self, monkeypatch):
        for val in ["true", "1", "yes", "on", "TRUE", "True"]:
            monkeypatch.setenv("TEST_BOOL", val)
            assert _get_bool_env("TEST_BOOL", False) == True
    
    def test_get_bool_env_false_values(self, monkeypatch):
        for val in ["false", "0", "no", "off", "FALSE", "False"]:
            monkeypatch.setenv("TEST_BOOL", val)
            assert _get_bool_env("TEST_BOOL", True) == False
    
    def test_get_bool_env_default(self, monkeypatch):
        monkeypatch.delenv("TEST_BOOL", raising=False)
        assert _get_bool_env("TEST_BOOL", True) == True
        assert _get_bool_env("TEST_BOOL", False) == False
    
    def test_get_int_env(self, monkeypatch):
        monkeypatch.setenv("TEST_INT", "42")
        assert _get_int_env("TEST_INT", 0) == 42
    
    def test_get_int_env_invalid(self, monkeypatch):
        monkeypatch.setenv("TEST_INT", "not_a_number")
        assert _get_int_env("TEST_INT", 99) == 99
    
    def test_get_float_env(self, monkeypatch):
        monkeypatch.setenv("TEST_FLOAT", "3.14")
        assert _get_float_env("TEST_FLOAT", 0.0) == pytest.approx(3.14)
    
    def test_get_float_env_invalid(self, monkeypatch):
        monkeypatch.setenv("TEST_FLOAT", "not_a_float")
        assert _get_float_env("TEST_FLOAT", 2.5) == 2.5


class TestServerConfig:
    """Test server configuration."""
    
    def test_default_values(self):
        config = ServerConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 5001
        assert config.debug == False
        assert len(config.cors_origins) > 0
    
    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("BOOK_TRANSLATOR_HOST", "0.0.0.0")
        monkeypatch.setenv("BOOK_TRANSLATOR_PORT", "8080")
        config = ServerConfig()
        assert config.host == "0.0.0.0"
        assert config.port == 8080


class TestOllamaConfig:
    """Test Ollama API configuration."""
    
    def test_default_values(self):
        config = OllamaConfig()
        assert "localhost:11434" in config.api_url
        assert config.connect_timeout == 30
        assert config.read_timeout == 300
        assert 0 <= config.temperature <= 1
        assert 0 <= config.top_p <= 1


class TestTranslationConfig:
    """Test translation processing configuration."""
    
    def test_default_values(self):
        config = TranslationConfig()
        assert config.chunk_size >= 100
        assert config.max_prompt_length >= 1000
        assert config.max_retries >= 1
        assert 0 <= config.similarity_threshold <= 1


class TestFileConfig:
    """Test file handling configuration."""
    
    def test_max_file_size_bytes(self):
        config = FileConfig()
        assert config.max_file_size_bytes == config.max_file_size_mb * 1024 * 1024
    
    def test_allowed_extensions(self):
        config = FileConfig()
        assert ".txt" in config.allowed_extensions


class TestAppConfig:
    """Test main application configuration."""
    
    def test_all_sections_present(self):
        config = AppConfig()
        assert hasattr(config, 'server')
        assert hasattr(config, 'ollama')
        assert hasattr(config, 'translation')
        assert hasattr(config, 'cache')
        assert hasattr(config, 'file')
        assert hasattr(config, 'logging')
    
    def test_validation_chunk_size(self):
        """Test that validation fails for invalid chunk_size."""
        with pytest.raises(ValueError, match="chunk_size"):
            config = AppConfig()
            config.translation.chunk_size = 50
            config._validate()
    
    def test_validation_similarity_threshold(self):
        """Test that validation fails for invalid similarity_threshold."""
        with pytest.raises(ValueError, match="similarity_threshold"):
            config = AppConfig()
            config.translation.similarity_threshold = 1.5
            config._validate()
