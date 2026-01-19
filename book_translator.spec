# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec File for Book Translator
==========================================
This file configures how PyInstaller packages the application.

To create the .exe:
    pyinstaller book_translator.spec

The result will be in: dist/BookTranslator/BookTranslator.exe
"""

import os
import sys

# Get the spec file directory
spec_dir = os.path.dirname(os.path.abspath(SPEC))

# Main script analysis
a = Analysis(
    ['run.py'],
    pathex=[spec_dir],
    binaries=[],
    datas=[
        # Include static files (frontend)
        ('static', 'static'),
        # Include book_translator package
        ('book_translator', 'book_translator'),
        # Include necessary folders (will be created empty)
        ('uploads', 'uploads'),
        ('translations', 'translations'),
        ('logs', 'logs'),
    ],
    hiddenimports=[
        'flask',
        'flask_cors',
        'requests',
        'psutil',
        'sqlite3',
        'hashlib',
        'logging',
        'logging.handlers',
        'werkzeug',
        'werkzeug.utils',
        'werkzeug.serving',
        'werkzeug.security',
        'jinja2',
        'markupsafe',
        'itsdangerous',
        'click',
        'flaskwebgui',
        'book_translator',
        'book_translator.app',
        'book_translator.config',
        'book_translator.config.settings',
        'book_translator.config.constants',
        'book_translator.models',
        'book_translator.models.translation',
        'book_translator.models.schemas',
        'book_translator.utils',
        'book_translator.utils.language_detection',
        'book_translator.utils.text_processing',
        'book_translator.utils.validators',
        'book_translator.utils.logging',
        'book_translator.services',
        'book_translator.services.ollama_client',
        'book_translator.services.cache_service',
        'book_translator.services.terminology',
        'book_translator.services.translator',
        'book_translator.database',
        'book_translator.database.connection',
        'book_translator.database.repositories',
        'book_translator.api',
        'book_translator.api.routes',
        'book_translator.api.middleware',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        'black',
        'flake8',
        'gunicorn',
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

# Create the PYZ file (Python Zip)
pyz = PYZ(a.pure, a.zipped_data)

# Create the executable
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BookTranslator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Hidden - logs visible in built-in console panel
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.ico',  # Application icon
)

# Collect everything in a folder
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BookTranslator',
)
