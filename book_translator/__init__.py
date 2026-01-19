"""
Book Translator - A two-stage AI translation system
====================================================
This package provides a Flask-based web application for translating books
using Ollama LLM models with a two-stage translation approach:
1. Primary translation
2. Reflection and improvement

Author: Book Translator Team
Version: 2.0.0
"""

__version__ = "2.0.0"
__author__ = "Book Translator Team"

from book_translator.app import create_app, run_server

__all__ = ["create_app", "run_server", "__version__"]

