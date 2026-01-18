"""
Integration Tests for Flask API
"""
import pytest
import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def client():
    """Create test client for Flask app."""
    from translator import app
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_endpoint_exists(self, client):
        response = client.get('/health')
        assert response.status_code in [200, 503]  # 503 if Ollama not running
    
    def test_health_returns_json(self, client):
        response = client.get('/health')
        assert response.content_type == 'application/json'


class TestStaticFiles:
    """Test static file serving."""
    
    def test_index_page(self, client):
        response = client.get('/')
        assert response.status_code == 200
        assert b'<!DOCTYPE html>' in response.data or b'<html' in response.data


class TestModelsEndpoint:
    """Test models listing endpoint."""
    
    def test_models_endpoint_exists(self, client):
        response = client.get('/models')
        # May return 500 if Ollama not running, but endpoint should exist
        assert response.status_code in [200, 500, 503]


class TestTranslationsEndpoint:
    """Test translations listing endpoint."""
    
    def test_translations_list(self, client):
        response = client.get('/translations')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'translations' in data
        assert isinstance(data['translations'], list)


class TestTranslateEndpoint:
    """Test translation upload endpoint."""
    
    def test_no_file_returns_error(self, client):
        response = client.post('/translate', data={})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_empty_filename_returns_error(self, client):
        data = {
            'file': (tempfile.SpooledTemporaryFile(), ''),
            'sourceLanguage': 'en',
            'targetLanguage': 'es',
            'model': 'test-model'
        }
        response = client.post('/translate', data=data, content_type='multipart/form-data')
        assert response.status_code == 400
    
    def test_invalid_extension_returns_error(self, client):
        # Create a temp file with wrong extension
        import io
        data = {
            'file': (io.BytesIO(b'test content'), 'test.exe'),
            'sourceLanguage': 'en',
            'targetLanguage': 'es',
            'model': 'test-model'
        }
        response = client.post('/translate', data=data, content_type='multipart/form-data')
        assert response.status_code == 400
        resp_data = json.loads(response.data)
        assert 'Invalid file type' in resp_data.get('error', '')
    
    def test_missing_params_returns_error(self, client):
        import io
        data = {
            'file': (io.BytesIO(b'test content'), 'test.txt'),
            # Missing sourceLanguage, targetLanguage, model
        }
        response = client.post('/translate', data=data, content_type='multipart/form-data')
        assert response.status_code == 400


class TestLogsEndpoint:
    """Test logs endpoint."""
    
    def test_logs_endpoint_exists(self, client):
        response = client.get('/logs')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'logs' in data


class TestMetricsEndpoint:
    """Test metrics endpoint."""
    
    def test_metrics_endpoint_exists(self, client):
        response = client.get('/metrics')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, dict)
