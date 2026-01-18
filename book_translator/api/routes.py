"""
API Routes
==========
Flask blueprints for all API endpoints.
"""
import json
import time
import threading
from pathlib import Path
from flask import Blueprint, request, jsonify, Response, send_file, current_app
from werkzeug.utils import secure_filename

from book_translator.config import config
from book_translator.config.constants import TranslationStatus, SUPPORTED_LANGUAGES
from book_translator.services.translator import BookTranslator
from book_translator.services.ollama_client import get_ollama_client
from dataclasses import asdict
from book_translator.services.cache_service import get_cache
from book_translator.database.repositories import (
    get_translation_repository,
    TranslationChunkRepository
)
from book_translator.utils.validators import validate_file, validate_language, validate_model_name
from book_translator.utils.logging import get_logger, debug_print
from book_translator.utils.text_processing import clean_for_epub


def create_translation_blueprint() -> Blueprint:
    """Create translation routes blueprint."""
    bp = Blueprint('translations', __name__, url_prefix='/api')
    logger = get_logger().api_logger
    
    @bp.route('/translate', methods=['POST'])
    def start_translation():
        """Start a new translation."""
        try:
            # Validate file
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            # Validate file type and size
            validation = validate_file(file)
            if not validation[0]:  # is_valid
                return jsonify({'error': validation[1]}), 400  # error_message
            
            # Get parameters
            source_lang = request.form.get('source_lang', 'auto')
            target_lang = request.form.get('target_lang', 'es')
            model_name = request.form.get('model', config.ollama.default_model)
            
            # Validate languages
            if target_lang not in SUPPORTED_LANGUAGES:
                return jsonify({'error': f'Unsupported target language: {target_lang}'}), 400
            
            # Validate model
            model_validation = validate_model_name(model_name)
            if not model_validation[0]:  # is_valid
                return jsonify({'error': model_validation[1]}), 400  # error_message
            
            # Save file
            filename = secure_filename(file.filename)
            upload_path = config.paths.upload_folder / filename
            file.save(str(upload_path))
            
            # Read content
            content = upload_path.read_text(encoding='utf-8')
            file_size = upload_path.stat().st_size
            
            # Create translation record
            repo = get_translation_repository()
            translation_id = repo.create(
                original_filename=filename,
                source_language=source_lang,
                target_language=target_lang,
                model_name=model_name,
                original_text=content,
                file_size=file_size
            )
            
            logger.info(f"Translation {translation_id} created for {filename}")
            
            # Start translation in background
            translator = BookTranslator(model_name=model_name)
            
            def run_translation():
                try:
                    start_time = time.time()
                    final_result = None
                    
                    for progress in translator.translate_text(
                        content, source_lang, target_lang, translation_id
                    ):
                        repo.update_progress(
                            translation_id,
                            progress.progress,
                            progress.stage,
                            progress.machine_translation,
                            progress.translated_text
                        )
                        final_result = progress
                    
                    if final_result and final_result.translated_text:
                        # Clean and save translated file
                        cleaned_text = clean_for_epub(final_result.translated_text)
                        output_filename = f"{Path(filename).stem}_{target_lang}.txt"
                        output_path = config.paths.translations_folder / output_filename
                        output_path.write_text(cleaned_text, encoding='utf-8')
                        
                        processing_time = time.time() - start_time
                        repo.mark_completed(
                            translation_id,
                            final_result.translated_text,
                            output_filename,
                            processing_time
                        )
                    else:
                        repo.mark_failed(translation_id, "Translation produced no output")
                        
                except Exception as e:
                    logger.error(f"Translation {translation_id} failed: {e}")
                    repo.mark_failed(translation_id, str(e))
            
            thread = threading.Thread(target=run_translation)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'id': translation_id,
                'status': 'processing',
                'message': 'Translation started'
            })
            
        except Exception as e:
            logger.error(f"Error starting translation: {e}")
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/translate/<int:translation_id>/status', methods=['GET'])
    def get_translation_status(translation_id: int):
        """Get translation status."""
        repo = get_translation_repository()
        translation = repo.get_by_id(translation_id)
        
        if not translation:
            return jsonify({'error': 'Translation not found'}), 404
        
        return jsonify({
            'id': translation['id'],
            'status': translation['status'],
            'progress': translation['progress'],
            'stage': translation['stage'],
            'error_message': translation.get('error_message')
        })
    
    @bp.route('/translate/<int:translation_id>/stream', methods=['GET'])
    def stream_translation(translation_id: int):
        """Stream translation progress via SSE."""
        repo = get_translation_repository()
        
        def generate():
            last_progress = -1
            while True:
                translation = repo.get_by_id(translation_id)
                
                if not translation:
                    yield f"data: {json.dumps({'error': 'Translation not found'})}\n\n"
                    break
                
                current_progress = translation['progress']
                
                if current_progress != last_progress:
                    yield f"data: {json.dumps({
                        'id': translation['id'],
                        'status': translation['status'],
                        'progress': translation['progress'],
                        'stage': translation['stage'],
                        'machine_translation': translation.get('machine_translation', ''),
                        'translated_text': translation.get('translated_text', '')
                    })}\n\n"
                    last_progress = current_progress
                
                if translation['status'] in ['completed', 'failed', 'cancelled']:
                    break
                
                time.sleep(1)
        
        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
        )
    
    @bp.route('/translate/<int:translation_id>', methods=['DELETE'])
    def cancel_translation(translation_id: int):
        """Cancel a translation."""
        repo = get_translation_repository()
        translation = repo.get_by_id(translation_id)
        
        if not translation:
            return jsonify({'error': 'Translation not found'}), 404
        
        if translation['status'] not in ['pending', 'processing']:
            return jsonify({'error': 'Cannot cancel completed translation'}), 400
        
        repo.mark_cancelled(translation_id)
        return jsonify({'message': 'Translation cancelled'})
    
    @bp.route('/translations', methods=['GET'])
    def list_translations():
        """List all translations."""
        status = request.args.get('status')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        repo = get_translation_repository()
        translations = repo.get_all(status=status, limit=limit, offset=offset)
        
        return jsonify({'translations': translations})
    
    @bp.route('/translations/stats', methods=['GET'])
    def get_stats():
        """Get translation statistics."""
        repo = get_translation_repository()
        return jsonify(repo.get_stats())
    
    return bp


def create_models_blueprint() -> Blueprint:
    """Create models routes blueprint."""
    bp = Blueprint('models', __name__, url_prefix='/api')
    logger = get_logger().api_logger

    @bp.route('/models', methods=['GET'])
    def list_models():
        """List available Ollama models."""
        try:
            client = get_ollama_client()
            models = client.list_models()
            # Asegurar que la respuesta es una lista de dicts
            if models:
                # Si es una lista de dataclasses, convertir a dict
                if hasattr(models[0], '__dataclass_fields__'):
                    models = [asdict(m) for m in models]
                # Si es una lista de objetos con __dict__, convertir
                elif hasattr(models[0], '__dict__'):
                    models = [m.__dict__ for m in models]
                # Si es una lista de strings, convertir a dict
                elif isinstance(models[0], str):
                    models = [{'name': m} for m in models]
            else:
                models = []
            return jsonify({'models': models}), 200
        except Exception as e:
            return jsonify({'error': f'No se pudo obtener modelos de Ollama: {str(e)}', 'models': []}), 500

    @bp.route('/models/current', methods=['GET'])
    def get_current_model():
        """Get current default model."""
        return jsonify({'model': config.ollama.default_model})

    return bp


def create_health_blueprint() -> Blueprint:
    """Create health check routes blueprint."""
    bp = Blueprint('health', __name__, url_prefix='/api')
    
    @bp.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint."""
        client = get_ollama_client()
        ollama_healthy = client.is_healthy()
        
        return jsonify({
            'status': 'healthy' if ollama_healthy else 'degraded',
            'ollama': 'connected' if ollama_healthy else 'disconnected',
            'version': '2.0.0'
        })
    
    @bp.route('/metrics', methods=['GET'])
    def get_metrics():
        """Get application metrics."""
        import psutil
        import time
        
        repo = get_translation_repository()
        stats = repo.get_stats()
        
        # System metrics
        system_metrics = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage': psutil.disk_usage('/').percent,
            'uptime': time.time() - psutil.boot_time()
        }
        
        # Translation metrics
        translation_metrics = {
            'total_translations': stats.get('total', 0),
            'completed_translations': stats.get('completed', 0),
            'failed_translations': stats.get('failed', 0),
            'success_rate': stats.get('success_rate', 100.0),
            'average_translation_time': stats.get('avg_time', 0.0)
        }
        
        return jsonify({
            'translation_metrics': translation_metrics,
            'system_metrics': system_metrics
        })
    
    @bp.route('/cache/stats', methods=['GET'])
    def cache_stats():
        """Get cache statistics."""
        cache = get_cache()
        return jsonify(cache.get_stats())
    
    @bp.route('/cache/clear', methods=['POST'])
    def clear_cache():
        """Clear the translation cache."""
        cache = get_cache()
        cache.clear()
        return jsonify({'message': 'Cache cleared'})
    
    return bp


def create_files_blueprint() -> Blueprint:
    """Create file handling routes blueprint."""
    bp = Blueprint('files', __name__, url_prefix='/api')
    logger = get_logger().api_logger
    
    @bp.route('/download/<int:translation_id>', methods=['GET'])
    def download_translation(translation_id: int):
        """Download translated file."""
        repo = get_translation_repository()
        translation = repo.get_by_id(translation_id)
        
        if not translation:
            return jsonify({'error': 'Translation not found'}), 404
        
        if translation['status'] != 'completed':
            return jsonify({'error': 'Translation not yet complete'}), 400
        
        file_path = config.paths.translations_folder / translation['translated_filename']
        
        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404
        
        return send_file(
            str(file_path),
            as_attachment=True,
            download_name=translation['translated_filename']
        )
    
    @bp.route('/languages', methods=['GET'])
    def list_languages():
        """List supported languages."""
        return jsonify({'languages': SUPPORTED_LANGUAGES})
    
    return bp


def create_logs_blueprint() -> Blueprint:
    """Create logs routes blueprint for frontend console panel."""
    from book_translator.utils.logging import log_buffer
    
    bp = Blueprint('logs', __name__)
    
    @bp.route('/logs', methods=['GET'])
    def get_logs():
        """Get logs from in-memory buffer for the frontend console panel."""
        since_id = request.args.get('since', 0, type=int)
        if since_id > 0:
            logs = log_buffer.get_since(since_id)
        else:
            logs = log_buffer.get_all()
        return jsonify({'logs': logs})
    
    @bp.route('/logs/stream')
    def stream_logs():
        """Stream logs in real-time using Server-Sent Events."""
        def generate():
            last_id = 0
            while True:
                logs = log_buffer.get_since(last_id)
                for log in logs:
                    last_id = log['id']
                    yield f"data: {json.dumps(log)}\n\n"
                time.sleep(0.5)
        
        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive'
            }
        )
    
    @bp.route('/logs/clear', methods=['POST'])
    def clear_logs():
        """Clear the log buffer."""
        log_buffer.clear()
        return jsonify({'message': 'Logs cleared'})
    
    return bp
