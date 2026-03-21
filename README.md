<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 320">
  <defs>
    <linearGradient id="modernGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#000000;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#18181b;stop-opacity:1" />
    </linearGradient>
    <filter id="glow">
      <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
      <feMerge>
        <feMergeNode in="coloredBlur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  <rect width="1280" height="320" fill="url(#modernGrad)"/>
  <path d="M0 40 L1280 40 M0 80 L1280 80 M0 120 L1280 120 M0 160 L1280 160 M0 200 L1280 200 M0 240 L1280 240 M0 280 L1280 280" stroke="#27272a" stroke-width="0.5"/>
  <g transform="translate(100, 100)">
    <g filter="url(#glow)">
      <path d="M20,20 L60,20 A10,10 0 0 1 70,30 L70,90 A10,10 0 0 1 60,100 L20,100 A10,10 0 0 1 10,90 L10,30 A10,10 0 0 1 20,20 Z" fill="none" stroke="#06b6d4" stroke-width="2"/>
      <path d="M25,30 L55,30 M25,45 L55,45 M25,60 L55,60" stroke="#06b6d4" stroke-width="2"/>
    </g>
    <text x="100" y="45" font-family="Arial" font-size="48" font-weight="bold" fill="white" filter="url(#glow)">Book Translator</text>
    <text x="100" y="80" font-family="Arial" font-size="20" fill="#94a3b8">Multilingual Translation Platform</text>
    <g transform="translate(100, 120)">
      <rect x="0" y="0" rx="20" ry="20" width="90" height="40" fill="#06b6d4" fill-opacity="0.1" stroke="#06b6d4" stroke-width="1"/>
      <text x="45" y="25" font-family="Arial" font-size="14" fill="#06b6d4" text-anchor="middle">Python</text>
      <rect x="100" y="0" rx="20" ry="20" width="90" height="40" fill="#06b6d4" fill-opacity="0.1" stroke="#06b6d4" stroke-width="1"/>
      <text x="145" y="25" font-family="Arial" font-size="14" fill="#06b6d4" text-anchor="middle">React</text>
      <rect x="200" y="0" rx="20" ry="20" width="90" height="40" fill="#06b6d4" fill-opacity="0.1" stroke="#06b6d4" stroke-width="1"/>
      <text x="245" y="25" font-family="Arial" font-size="14" fill="#06b6d4" text-anchor="middle">Flask</text>
    </g>
  </g>
  <g transform="translate(800, 0)" fill="#06b6d4" fill-opacity="0.03">
    <circle cx="200" cy="100" r="80"/>
    <circle cx="300" cy="200" r="120"/>
    <circle cx="150" cy="250" r="60"/>
  </g>
</svg>

<h1 align="center">Book Translator</h1>

<p align="center">
  Translate long-form text files through a local Ollama-powered desktop and web app.
</p>

<p align="center">
  <a href="https://github.com/KazKozDev/book-translator/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/KazKozDev/book-translator/ci.yml?branch=main&label=CI" alt="CI status">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/github/license/KazKozDev/book-translator" alt="MIT license">
  </a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Ollama-local%20models-111111" alt="Ollama local models">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Web-2ea44f" alt="Platforms">
</p>

Book Translator provides a two-stage workflow for translating books and large documents: first it generates a draft translation, then it runs a second pass to improve fluency, consistency, and style. The project targets users who want a local-first interface, progress tracking, saved history, and downloadable output without building a custom prompt pipeline around Ollama.

## Highlights

- Two-stage translation refinement
- Local Ollama model execution
- Flask API and browser UI
- Desktop launcher with tray mode
- Translation history, cache, and export

## Demo

![Book Translator screenshot](demo.jpg)

## Overview

The repository ships a modular Python application centered around the [`book_translator`](/Users/artemk/projects/book-trans/book_translator) package. A Flask backend handles uploads, translation jobs, Ollama integration, metrics, and downloads, while the static frontend provides the browser UI. The current `main` branch includes tests, Docker support, Windows packaging files, and a desktop launcher via [`run.py`](/Users/artemk/projects/book-trans/run.py).

## Motivation

Long-document translation tends to fail at the workflow level before it fails at the model level: chapters need chunking, retries, continuity, visibility into progress, and some way to recover usable output from imperfect generations. This project closes that gap with an opinionated local app instead of a collection of scripts. The two-stage pipeline is the core product idea: do not stop at the first draft when a second review pass can improve readability and consistency.

## Architecture

- [`run.py`](/Users/artemk/projects/book-trans/run.py) starts the local app, supports tray mode when optional desktop dependencies are installed, and opens the browser UI.
- [`book_translator/app.py`](/Users/artemk/projects/book-trans/book_translator/app.py) builds the Flask app, registers blueprints, configures CORS, and serves the frontend.
- [`book_translator/api/routes.py`](/Users/artemk/projects/book-trans/book_translator/api/routes.py) exposes translation, models, health, cache, download, and log endpoints.
- [`book_translator/services/translator.py`](/Users/artemk/projects/book-trans/book_translator/services/translator.py) implements chunking, stage-one translation, stage-two refinement, and cache-aware execution.
- [`book_translator/database`](/Users/artemk/projects/book-trans/book_translator/database) stores jobs and chunk metadata in SQLite.
- [`tests`](/Users/artemk/projects/book-trans/tests) covers API endpoints, config, and core translation behavior.

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com/) running locally
- At least one installed Ollama model

## Quick Start

1. Clone the repository and install dependencies.

   ```bash
   git clone https://github.com/KazKozDev/book-translator.git
   cd book-translator
   pip install -r requirements.txt
   ```

2. Pull an Ollama model.

   ```bash
   ollama pull llama3.2
   ```

3. Start the application.

   ```bash
   python run.py
   ```

4. Open [http://localhost:5001](http://localhost:5001) if it does not open automatically.

## Usage

### Translate a document

1. Start the app.
2. Choose source language, target language, and model.
3. Upload a `.txt` file.
4. Monitor progress in the UI, then download the translated result.

### Run the web app without tray mode

If the optional desktop dependencies are unavailable, `run.py` falls back to a plain Flask launch and still opens the browser automatically.

### Build desktop binaries

The repository includes PyInstaller specs for Windows packaging:

```bash
pyinstaller book_translator_onefile.spec
```

### Run tests

```bash
pytest -q
```

## Current State

- The codebase is modular and covered by automated tests.
- The app supports local translation workflows, cache management, metrics, and downloadable text output.
- The README in earlier revisions overstated some capabilities; this version reflects the repository as it exists on the current `main` branch.

---

MIT - see LICENSE

If you like this project, please give it a star ⭐

For questions, feedback, or support, reach out to:

[LinkedIn](https://www.linkedin.com/in/kazkozdev/)
[Email](mailto:kazkozdev@gmail.com)
