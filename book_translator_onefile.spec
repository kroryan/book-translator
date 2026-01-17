# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec File for Book Translator - SINGLE FILE VERSION
=================================================================
This file creates a SINGLE .exe with everything included.

To create the .exe:
    pyinstaller book_translator_onefile.spec

The result will be in: dist/BookTranslator.exe

NOTE: The file will be larger (~50-100MB) but it's a single file.
"""

import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

# Get the spec file directory
spec_dir = os.path.dirname(os.path.abspath(SPEC))

# Collect all data from Flask and its dependencies
flask_datas, flask_binaries, flask_hiddenimports = collect_all('flask')
jinja2_datas, jinja2_binaries, jinja2_hiddenimports = collect_all('jinja2')
werkzeug_datas, werkzeug_binaries, werkzeug_hiddenimports = collect_all('werkzeug')

# Collect PIL/Pillow data
try:
    pil_datas, pil_binaries, pil_hiddenimports = collect_all('PIL')
except Exception:
    pil_datas, pil_binaries, pil_hiddenimports = [], [], []

# Collect pystray data
try:
    pystray_datas, pystray_binaries, pystray_hiddenimports = collect_all('pystray')
except Exception:
    pystray_datas, pystray_binaries, pystray_hiddenimports = [], [], []

# Main script analysis
a = Analysis(
    ['app_desktop.py'],
    pathex=[spec_dir],
    binaries=flask_binaries + jinja2_binaries + werkzeug_binaries + pil_binaries + pystray_binaries,
    datas=[
        # Include static files (frontend)
        ('static', 'static'),
    ] + flask_datas + jinja2_datas + werkzeug_datas + pil_datas + pystray_datas,
    hiddenimports=[
        # Flask and dependencies
        'flask',
        'flask.app',
        'flask.blueprints',
        'flask.cli',
        'flask.config',
        'flask.ctx',
        'flask.globals',
        'flask.helpers',
        'flask.json',
        'flask.logging',
        'flask.sessions',
        'flask.signals',
        'flask.templating',
        'flask.testing',
        'flask.views',
        'flask.wrappers',
        'flask_cors',
        # Werkzeug
        'werkzeug',
        'werkzeug.datastructures',
        'werkzeug.debug',
        'werkzeug.exceptions',
        'werkzeug.formparser',
        'werkzeug.http',
        'werkzeug.local',
        'werkzeug.routing',
        'werkzeug.security',
        'werkzeug.serving',
        'werkzeug.test',
        'werkzeug.urls',
        'werkzeug.useragents',
        'werkzeug.utils',
        'werkzeug.wrappers',
        'werkzeug.wsgi',
        # Jinja2
        'jinja2',
        'jinja2.ext',
        'jinja2.loaders',
        # Other dependencies
        'markupsafe',
        'itsdangerous',
        'click',
        # Other modules used
        'requests',
        'psutil',
        'sqlite3',
        'hashlib',
        'logging',
        'logging.handlers',
        'flaskwebgui',
        'charset_normalizer',
        'certifi',
        'urllib3',
        # System tray support
        'pystray',
        'pystray._base',
        'pystray._win32',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFilter',
        'PIL.ImageFont',
    ] + flask_hiddenimports + jinja2_hiddenimports + werkzeug_hiddenimports + pil_hiddenimports + pystray_hiddenimports,
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

# Create SINGLE executable (onefile)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='BookTranslator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Hidden - logs visible in built-in console panel
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.ico',  # Application icon
)
