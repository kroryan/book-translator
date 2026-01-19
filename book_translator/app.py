"""
Book Translator Application
===========================
Flask application factory and main entry point.
"""
import os
from flask import Flask, send_from_directory
from flask_cors import CORS

from book_translator.config import config
from book_translator.database.connection import get_database
from book_translator.api.routes import (
    create_translation_blueprint,
    create_models_blueprint,
    create_health_blueprint,
    create_files_blueprint,
    create_logs_blueprint
)
from book_translator.api.middleware import add_rate_limit_headers
from book_translator.utils.logging import get_logger, debug_print


def create_app(testing: bool = False) -> Flask:
    """
    Application factory for Flask app.
    
    Args:
        testing: If True, configure for testing
    
    Returns:
        Configured Flask application
    """
    app = Flask(
        __name__,
        static_folder=config.paths.static_folder,
        static_url_path='/static'
    )
    
    # Configuration
    app.config.update(
        SECRET_KEY=config.server.secret_key,
        MAX_CONTENT_LENGTH=config.file.max_file_size_bytes,
        JSON_SORT_KEYS=False,
        TESTING=testing
    )
    
    # CORS configuration
    cors_origins = config.server.cors_origins
    if testing:
        cors_origins = ['*']
    
    CORS(
        app,
        resources={r"/api/*": {"origins": cors_origins}},
        supports_credentials=True
    )
    
    # Initialize database
    if not testing:
        get_database()
    
    # Register blueprints
    app.register_blueprint(create_translation_blueprint())
    app.register_blueprint(create_models_blueprint())
    app.register_blueprint(create_health_blueprint())
    app.register_blueprint(create_files_blueprint())
    app.register_blueprint(create_logs_blueprint())
    
    # Add middleware
    app.after_request(add_rate_limit_headers)
    
    # Error handlers
    @app.errorhandler(400)
    def bad_request(e):
        return {'error': 'Bad request', 'details': str(e)}, 400
    
    @app.errorhandler(404)
    def not_found(e):
        return {'error': 'Resource not found'}, 404
    
    @app.errorhandler(413)
    def file_too_large(e):
        max_mb = config.file.max_file_size_mb
        return {'error': f'File too large. Maximum size is {max_mb}MB'}, 413
    
    @app.errorhandler(429)
    def rate_limited(e):
        return {'error': 'Rate limit exceeded'}, 429
    
    @app.errorhandler(500)
    def internal_error(e):
        logger = get_logger().api_logger
        logger.error(f"Internal error: {e}")
        return {'error': 'Internal server error'}, 500
    
    # Serve frontend
    @app.route('/')
    def index():
        return send_from_directory(config.paths.static_folder, 'index.html')
    
    # Log startup
    logger = get_logger()
    logger.api_logger.info(f"Book Translator started on {config.server.host}:{config.server.port}")
    
    if config.logging.verbose_debug:
        debug_print("🚀 Application initialized", 'INFO', 'APP')
    
    return app


def run_server():
    """Run the Flask development server."""
    app = create_app()
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    📚 Book Translator v2.0                   ║
╠══════════════════════════════════════════════════════════════╣
║  Server: http://{config.server.host}:{config.server.port:<5}                              ║
║  Model:  {config.ollama.default_model:<50} ║
║  Debug:  {'Enabled' if config.logging.verbose_debug else 'Disabled':<50} ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    app.run(
        host=config.server.host,
        port=config.server.port,
        debug=config.logging.verbose_debug,
        threaded=True
    )


if __name__ == '__main__':
    run_server()
