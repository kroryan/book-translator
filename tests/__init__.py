"""
Book Translator - Test Suite
============================
Basic unit and integration tests for the Book Translator application.
Run with: pytest tests/ -v
"""
import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
