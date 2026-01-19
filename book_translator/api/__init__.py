"""
API Module
==========
Flask API routes and blueprints.
"""
from book_translator.api.routes import (
    create_translation_blueprint,
    create_models_blueprint,
    create_health_blueprint,
    create_files_blueprint
)

__all__ = [
    'create_translation_blueprint',
    'create_models_blueprint',
    'create_health_blueprint',
    'create_files_blueprint'
]
