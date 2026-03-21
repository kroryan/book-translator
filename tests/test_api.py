"""
Integration Tests for Flask API
================================
Tests for the refactored book_translator API endpoints.
"""
import pytest
import sys
import os
import json
import tempfile
import io
from unittest.mock import patch

# Setup test environment
os.environ.setdefault('BOOK_TRANSLATOR_ENV', 'testing')
os.environ.setdefault('VERBOSE_DEBUG', 'false')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def client():
    """Create test client for Flask app."""
    from book_translator.app import create_app

    app = create_app(testing=True)
    app.config['TESTING'] = True

    with app.test_client() as client:
        yield client


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_endpoint_exists(self, client):
        response = client.get('/api/health')
        assert response.status_code in [200, 503]  # 503 if Ollama not running

    def test_health_returns_json(self, client):
        response = client.get('/api/health')
        assert response.content_type == 'application/json'

    def test_health_has_status(self, client):
        response = client.get('/api/health')
        data = json.loads(response.data)
        assert 'status' in data


class TestStaticFiles:
    """Test static file serving."""

    def test_index_page(self, client):
        response = client.get('/')
        # Either 200 (file exists) or 404 (file missing in test env)
        assert response.status_code in [200, 404]


class TestModelsEndpoint:
    """Test models listing endpoint."""

    def test_models_endpoint_exists(self, client):
        response = client.get('/api/models')
        # May return 500 if Ollama not running, but endpoint should exist
        assert response.status_code in [200, 500, 503]

    def test_current_model_endpoint(self, client):
        response = client.get('/api/models/current')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'model' in data


class TestTranslationsEndpoint:
    """Test translations listing endpoint."""

    def test_translations_list(self, client):
        response = client.get('/api/translations')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'translations' in data
        assert isinstance(data['translations'], list)

    def test_translations_stats(self, client):
        response = client.get('/api/translations/stats')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, dict)

    @patch('book_translator.api.routes._submit_translation_job')
    def test_retry_translation_endpoint(self, mock_submit, client):
        from book_translator.database.repositories import get_translation_repository

        repo = get_translation_repository()
        translation_id = repo.create(
            original_filename='sample.txt',
            source_language='en',
            target_language='es',
            model_name='test-model',
            original_text='Hello world',
            file_size=11
        )

        response = client.post(f'/api/retry-translation/{translation_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'processing'
        assert 'id' in data
        mock_submit.assert_called_once()


class TestTranslateEndpoint:
    """Test translation upload endpoint."""

    def test_no_file_returns_error(self, client):
        response = client.post('/api/translate', data={})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_empty_filename_returns_error(self, client):
        data = {
            'file': (io.BytesIO(b''), ''),
            'source_lang': 'en',
            'target_lang': 'es',
            'model': 'test-model'
        }
        response = client.post('/api/translate', data=data, content_type='multipart/form-data')
        assert response.status_code == 400

    def test_invalid_extension_returns_error(self, client):
        data = {
            'file': (io.BytesIO(b'test content'), 'test.exe'),
            'source_lang': 'en',
            'target_lang': 'es',
            'model': 'test-model'
        }
        response = client.post('/api/translate', data=data, content_type='multipart/form-data')
        assert response.status_code == 400
        resp_data = json.loads(response.data)
        assert 'Invalid file type' in resp_data.get('error', '') or 'error' in resp_data

    def test_invalid_source_language_returns_error(self, client):
        data = {
            'file': (io.BytesIO(b'test content'), 'test.txt'),
            'source_lang': 'xx',
            'target_lang': 'es',
            'model': 'test-model'
        }
        response = client.post('/api/translate', data=data, content_type='multipart/form-data')
        assert response.status_code == 400
        resp_data = json.loads(response.data)
        assert 'Unsupported language' in resp_data.get('error', '')



class TestLogsEndpoint:
    """Test logs endpoint."""

    def test_logs_endpoint_exists(self, client):
        response = client.get('/logs')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'logs' in data

    def test_logs_clear(self, client):
        response = client.post('/logs/clear')
        assert response.status_code == 200


class TestMetricsEndpoint:
    """Test metrics endpoint."""

    def test_metrics_endpoint_exists(self, client):
        response = client.get('/api/metrics')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, dict)
        assert 'translation_metrics' in data
        assert 'system_metrics' in data
        assert 'total_translations' in data['translation_metrics']
        assert 'completed_translations' in data['translation_metrics']
        assert 'failed_translations' in data['translation_metrics']
        assert 'success_rate' in data['translation_metrics']


class TestCacheEndpoints:
    """Test cache endpoints."""

    def test_cache_stats(self, client):
        response = client.get('/api/cache/stats')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'total_entries' in data

    def test_cache_clear(self, client):
        response = client.post('/api/cache/clear')
        assert response.status_code == 200


class TestExportEndpoints:
    """Test export endpoints."""

    def test_export_epub_requires_text(self, client):
        response = client.post('/api/export/epub', json={})
        assert response.status_code == 400

    def test_export_epub_returns_file(self, client):
        response = client.post('/api/export/epub', json={
            'text': 'Paragraph one.\n\nParagraph two.',
            'title': 'Sample Book',
            'author': 'Author Name'
        })
        assert response.status_code == 200
        assert response.content_type == 'application/epub+zip'


class TestLanguagesEndpoint:
    """Test languages endpoint."""

    def test_languages_list(self, client):
        response = client.get('/api/languages')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'languages' in data
        assert 'en' in data['languages']
        assert 'es' in data['languages']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
