# Book Translator

Translate long-form text files through a local Ollama-powered desktop and web app.

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
