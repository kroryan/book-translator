"""
API Routes
==========
Flask blueprints for all API endpoints.
"""

import json
import os
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime as dt
from html import escape
from pathlib import Path

from flask import Blueprint, Response, jsonify, request, send_file
from werkzeug.utils import secure_filename

from book_translator.api.middleware import rate_limit
from book_translator.config import config
from book_translator.config.constants import SUPPORTED_LANGUAGES, TranslationStatus
from book_translator.database.repositories import get_translation_repository
from book_translator.services.cache_service import get_cache
from book_translator.services.ollama_client import get_ollama_client
from book_translator.services.translator import BookTranslator
from book_translator.utils.logging import get_logger
from book_translator.utils.text_processing import clean_for_epub
from book_translator.utils.validators import (
    validate_file,
    validate_language,
    validate_model_name,
)

# Global thread pool for translation tasks (limits concurrent translations)
_translation_executor = None
_translation_tasks = {}
_translation_cancel_events = {}
_translation_lock = threading.Lock()


def get_translation_executor() -> ThreadPoolExecutor:
    """Get or create the translation thread pool."""
    global _translation_executor
    if _translation_executor is None:
        max_workers = config.translation.max_workers
        _translation_executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="translation"
        )
    return _translation_executor


def _register_translation_task(
    translation_id: int, future, cancel_event: threading.Event
) -> None:
    """Track a submitted translation task and its cancellation token."""
    with _translation_lock:
        _translation_tasks[translation_id] = future
        _translation_cancel_events[translation_id] = cancel_event


def _unregister_translation_task(translation_id: int) -> None:
    """Remove completed task tracking."""
    with _translation_lock:
        _translation_tasks.pop(translation_id, None)
        _translation_cancel_events.pop(translation_id, None)


def _get_cancel_event(translation_id: int) -> threading.Event | None:
    """Get cancellation event for an active translation."""
    with _translation_lock:
        return _translation_cancel_events.get(translation_id)


def _cancel_translation_task(translation_id: int) -> bool:
    """Signal cancellation and attempt to stop queued work."""
    with _translation_lock:
        cancel_event = _translation_cancel_events.get(translation_id)
        future = _translation_tasks.get(translation_id)

    if cancel_event is not None:
        cancel_event.set()

    if future is not None:
        future.cancel()

    return cancel_event is not None or future is not None


def _submit_translation_job(
    translation_id: int,
    filename: str,
    content: str,
    source_lang: str,
    target_lang: str,
    model_name: str,
    genre: str = "unknown",
    custom_instructions: str = "",
) -> None:
    """Submit a translation job to the background executor."""
    logger = get_logger().api_logger
    repo = get_translation_repository()
    translator = BookTranslator(model_name=model_name)
    cancel_event = threading.Event()

    def run_translation():
        try:
            start_time = time.time()
            final_result = None

            if cancel_event.is_set():
                return

            for progress in translator.translate_text(
                content,
                source_lang,
                target_lang,
                translation_id,
                genre=genre,
                custom_instructions=custom_instructions,
            ):
                if cancel_event.is_set():
                    logger.info(
                        f"Translation {translation_id} cancellation acknowledged"
                    )
                    return

                translation = repo.get_by_id(translation_id)
                if (
                    not translation
                    or translation["status"] == TranslationStatus.CANCELLED.value
                ):
                    logger.info(
                        f"Translation {translation_id} stopped before progress update"
                    )
                    return

                repo.update_progress(
                    translation_id,
                    progress.progress,
                    progress.stage,
                    progress.machine_translation,
                    progress.translated_text,
                )
                final_result = progress

            translation = repo.get_by_id(translation_id)
            if (
                not translation
                or translation["status"] == TranslationStatus.CANCELLED.value
            ):
                logger.info(f"Translation {translation_id} stopped before completion")
                return

            if final_result and final_result.translated_text:
                cleaned_text = clean_for_epub(final_result.translated_text)
                output_filename = (
                    f"{Path(filename).stem}_{target_lang}_{translation_id}.txt"
                )
                output_path = config.paths.translations_folder / output_filename
                output_path.write_text(cleaned_text, encoding="utf-8")

                processing_time = time.time() - start_time
                repo.mark_completed(
                    translation_id,
                    final_result.translated_text,
                    output_filename,
                    processing_time,
                )
            else:
                repo.mark_failed(translation_id, "Translation produced no output")

        except Exception as e:
            logger.error(f"Translation {translation_id} failed: {e}")
            repo.mark_failed(translation_id, str(e))
        finally:
            _unregister_translation_task(translation_id)

    executor = get_translation_executor()
    future = executor.submit(run_translation)
    _register_translation_task(translation_id, future, cancel_event)


def create_translation_blueprint() -> Blueprint:
    """Create translation routes blueprint."""
    bp = Blueprint("translations", __name__, url_prefix="/api")
    logger = get_logger().api_logger

    @bp.route("/translate", methods=["POST"])
    @rate_limit
    def start_translation():
        """Start a new translation."""
        try:
            # Validate file
            if "file" not in request.files:
                return jsonify({"error": "No file provided"}), 400

            file = request.files["file"]
            if file.filename == "":
                return jsonify({"error": "No file selected"}), 400

            # Validate file type and size
            validation = validate_file(file)
            if not validation[0]:  # is_valid
                return jsonify({"error": validation[1]}), 400  # error_message

            # Get parameters
            source_lang = request.form.get("source_lang", "auto")
            target_lang = request.form.get("target_lang", "es")
            model_name = request.form.get("model", config.ollama.default_model)
            genre = request.form.get("genre", "unknown")
            custom_instructions = request.form.get("custom_instructions", "").strip()

            if source_lang != "auto":
                source_validation = validate_language(source_lang)
                if not source_validation[0]:
                    return jsonify({"error": source_validation[1]}), 400

            # Validate languages
            target_validation = validate_language(target_lang)
            if not target_validation[0]:
                return jsonify({"error": target_validation[1]}), 400

            # Validate model
            model_validation = validate_model_name(model_name)
            if not model_validation[0]:  # is_valid
                return jsonify({"error": model_validation[1]}), 400  # error_message

            # Save file
            filename = secure_filename(file.filename)
            upload_path = config.paths.upload_folder / filename
            file.save(str(upload_path))

            # Read content with encoding detection
            try:
                content = upload_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Try other common encodings
                for encoding in ["latin-1", "cp1252", "iso-8859-1"]:
                    try:
                        content = upload_path.read_text(encoding=encoding)
                        logger.warning(
                            f"File {filename} decoded with {encoding} (not UTF-8)"
                        )
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    return (
                        jsonify(
                            {
                                "error": "Unable to decode file. Please use UTF-8 encoding."
                            }
                        ),
                        400,
                    )
            file_size = upload_path.stat().st_size
            upload_path.unlink(missing_ok=True)

            # Create translation record
            repo = get_translation_repository()
            translation_id = repo.create(
                original_filename=filename,
                source_language=source_lang,
                target_language=target_lang,
                model_name=model_name,
                original_text=content,
                file_size=file_size,
                custom_instructions=custom_instructions,
            )

            logger.info(f"Translation {translation_id} created for {filename}")
            _submit_translation_job(
                translation_id=translation_id,
                filename=filename,
                content=content,
                source_lang=source_lang,
                target_lang=target_lang,
                model_name=model_name,
                genre=genre,
                custom_instructions=custom_instructions,
            )

            return jsonify(
                {
                    "id": translation_id,
                    "status": "processing",
                    "message": "Translation started",
                }
            )

        except Exception as e:
            logger.error(f"Error starting translation: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route("/translate/<int:translation_id>/status", methods=["GET"])
    def get_translation_status(translation_id: int):
        """Get translation status."""
        repo = get_translation_repository()
        translation = repo.get_by_id(translation_id)

        if not translation:
            return jsonify({"error": "Translation not found"}), 404

        return jsonify(
            {
                "id": translation["id"],
                "status": translation["status"],
                "progress": translation["progress"],
                "stage": translation["stage"],
                "error_message": translation.get("error_message"),
            }
        )

    @bp.route("/translate/<int:translation_id>/stream", methods=["GET"])
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

                current_progress = translation["progress"]

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

                if translation["status"] in ["completed", "failed", "cancelled"]:
                    break

                time.sleep(1)

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @bp.route("/translate/<int:translation_id>", methods=["DELETE"])
    def cancel_translation(translation_id: int):
        """Cancel a translation."""
        repo = get_translation_repository()
        translation = repo.get_by_id(translation_id)

        if not translation:
            return jsonify({"error": "Translation not found"}), 404

        if translation["status"] not in ["pending", "processing"]:
            return jsonify({"error": "Cannot cancel completed translation"}), 400

        _cancel_translation_task(translation_id)
        repo.mark_cancelled(translation_id)
        return jsonify({"message": "Translation cancelled"})

    @bp.route("/retry-translation/<int:translation_id>", methods=["POST"])
    def retry_translation(translation_id: int):
        """Retry a previous translation as a new background job."""
        repo = get_translation_repository()
        translation = repo.get_by_id(translation_id)

        if not translation:
            return jsonify({"error": "Translation not found"}), 404

        if not translation.get("original_text"):
            return jsonify({"error": "Original text is not available for retry"}), 400

        new_translation_id = repo.create(
            original_filename=translation["original_filename"],
            source_language=translation["source_language"],
            target_language=translation["target_language"],
            model_name=translation["model_name"],
            original_text=translation["original_text"],
            file_size=translation.get("file_size"),
            custom_instructions=translation.get("custom_instructions"),
        )

        _submit_translation_job(
            translation_id=new_translation_id,
            filename=translation["original_filename"],
            content=translation["original_text"],
            source_lang=translation["source_language"],
            target_lang=translation["target_language"],
            model_name=translation["model_name"],
            genre="unknown",
            custom_instructions=translation.get("custom_instructions", ""),
        )

        return jsonify(
            {
                "id": new_translation_id,
                "status": "processing",
                "message": "Translation retry started",
            }
        )

    @bp.route("/translations", methods=["GET"])
    def list_translations():
        """List all translations."""
        status = request.args.get("status")
        limit = int(request.args.get("limit", 100))
        offset = int(request.args.get("offset", 0))

        repo = get_translation_repository()
        translations = repo.get_all(status=status, limit=limit, offset=offset)

        return jsonify({"translations": translations})

    @bp.route("/translations/stats", methods=["GET"])
    def get_stats():
        """Get translation statistics."""
        repo = get_translation_repository()
        return jsonify(repo.get_stats())

    return bp


def create_models_blueprint() -> Blueprint:
    """Create models routes blueprint."""
    bp = Blueprint("models", __name__, url_prefix="/api")

    @bp.route("/models", methods=["GET"])
    def list_models():
        """List available Ollama models."""
        try:
            client = get_ollama_client()
            models = client.list_models()
            if models:
                if hasattr(models[0], "__dataclass_fields__"):
                    models = [asdict(m) for m in models]
                elif hasattr(models[0], "__dict__"):
                    models = [m.__dict__ for m in models]
                elif isinstance(models[0], str):
                    models = [{"name": m} for m in models]
            else:
                models = []
            return jsonify({"models": models}), 200
        except Exception as e:
            return (
                jsonify({"error": f"Failed to fetch Ollama models: {e}", "models": []}),
                500,
            )

    @bp.route("/models/current", methods=["GET"])
    def get_current_model():
        """Get current default model."""
        return jsonify({"model": config.ollama.default_model})

    return bp


def create_health_blueprint() -> Blueprint:
    """Create health check routes blueprint."""
    bp = Blueprint("health", __name__, url_prefix="/api")

    @bp.route("/health", methods=["GET"])
    def health_check():
        """Health check endpoint."""
        client = get_ollama_client()
        ollama_healthy = client.is_healthy()

        return jsonify(
            {
                "status": "healthy" if ollama_healthy else "degraded",
                "ollama": "connected" if ollama_healthy else "disconnected",
                "version": "2.0.0",
            }
        )

    @bp.route("/metrics", methods=["GET"])
    def get_metrics():
        """Get application metrics."""
        import time

        import psutil

        repo = get_translation_repository()
        stats = repo.get_stats()
        by_status = stats.get("by_status", {})
        total_translations = stats.get("total", 0)
        completed_translations = by_status.get("completed", 0)
        failed_translations = by_status.get("failed", 0)
        success_rate = 0.0
        if total_translations:
            success_rate = (completed_translations / total_translations) * 100

        # System metrics (cross-platform compatible)
        import sys

        if sys.platform == "win32":
            # On Windows, use the drive where the app is running
            disk_path = os.path.splitdrive(os.getcwd())[0] + "\\"
        else:
            disk_path = "/"

        try:
            disk_percent = psutil.disk_usage(disk_path).percent
        except Exception:
            disk_percent = 0.0

        system_metrics = {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": disk_percent,
            "uptime": time.time() - psutil.boot_time(),
        }

        # Translation metrics
        translation_metrics = {
            "total_translations": total_translations,
            "completed_translations": completed_translations,
            "failed_translations": failed_translations,
            "success_rate": success_rate,
            "average_translation_time": stats.get("avg_processing_time") or 0.0,
        }

        return jsonify(
            {
                "translation_metrics": translation_metrics,
                "system_metrics": system_metrics,
            }
        )

    @bp.route("/cache/stats", methods=["GET"])
    def cache_stats():
        """Get cache statistics."""
        cache = get_cache()
        return jsonify(cache.get_stats())

    @bp.route("/cache/clear", methods=["POST"])
    def clear_cache():
        """Clear the translation cache."""
        cache = get_cache()
        cache.clear()
        return jsonify({"message": "Cache cleared"})

    return bp


def create_files_blueprint() -> Blueprint:
    """Create file handling routes blueprint."""
    bp = Blueprint("files", __name__, url_prefix="/api")
    logger = get_logger().api_logger

    @bp.route("/download/<int:translation_id>", methods=["GET"])
    def download_translation(translation_id: int):
        """Download translated file."""
        repo = get_translation_repository()
        translation = repo.get_by_id(translation_id)

        if not translation:
            return jsonify({"error": "Translation not found"}), 404

        if translation["status"] != "completed":
            return jsonify({"error": "Translation not yet complete"}), 400

        file_path = (
            config.paths.translations_folder / translation["translated_filename"]
        )

        if not file_path.exists():
            return jsonify({"error": "File not found"}), 404

        return send_file(
            str(file_path),
            as_attachment=True,
            download_name=translation["translated_filename"],
        )

    @bp.route("/languages", methods=["GET"])
    def list_languages():
        """List supported languages."""
        return jsonify({"languages": SUPPORTED_LANGUAGES})

    @bp.route("/export/epub", methods=["POST"])
    def export_epub():
        """Export translated text as a minimal EPUB package."""
        data = request.get_json(silent=True) or {}
        text = data.get("text", "")
        title = data.get("title", "Translation")
        author = data.get("author", "Book Translator")

        if not text:
            return jsonify({"error": "No text provided"}), 400

        epub_id = str(uuid.uuid4())
        epub_filename = f"translation_{epub_id}.epub"
        epub_path = config.paths.translations_folder / epub_filename

        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        html_paragraphs = "".join(f"<p>{escape(p)}</p>\n" for p in paragraphs)
        safe_title = escape(title)
        safe_author = escape(author)

        with zipfile.ZipFile(epub_path, "w", zipfile.ZIP_DEFLATED) as epub:
            epub.writestr(
                "mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED
            )
            epub.writestr(
                "META-INF/container.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>""",
            )
            epub.writestr(
                "OEBPS/content.opf",
                f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="BookID">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:title>{safe_title}</dc:title>
        <dc:creator>{safe_author}</dc:creator>
        <dc:language>en</dc:language>
        <dc:identifier id="BookID">{epub_id}</dc:identifier>
        <meta property="dcterms:modified">{dt.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}</meta>
    </metadata>
    <manifest>
        <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
        <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    </manifest>
    <spine toc="ncx">
        <itemref idref="chapter1"/>
    </spine>
</package>""",
            )
            epub.writestr(
                "OEBPS/toc.ncx",
                f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
    <head>
        <meta name="dtb:uid" content="{epub_id}"/>
        <meta name="dtb:depth" content="1"/>
    </head>
    <docTitle>
        <text>{safe_title}</text>
    </docTitle>
    <navMap>
        <navPoint id="chapter1" playOrder="1">
            <navLabel><text>Chapter 1</text></navLabel>
            <content src="chapter1.xhtml"/>
        </navPoint>
    </navMap>
</ncx>""",
            )
            epub.writestr(
                "OEBPS/chapter1.xhtml",
                f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>{safe_title}</title>
    <style>
        body {{ font-family: serif; line-height: 1.6; margin: 2em; }}
        p {{ margin-bottom: 1em; text-indent: 1.5em; }}
        p:first-of-type {{ text-indent: 0; }}
    </style>
</head>
<body>
    <h1>{safe_title}</h1>
    {html_paragraphs}
</body>
</html>""",
            )

        return send_file(
            str(epub_path),
            as_attachment=True,
            download_name=f"{Path(title).stem or 'translation'}.epub",
            mimetype="application/epub+zip",
        )

    return bp


def create_logs_blueprint() -> Blueprint:
    """Create logs routes blueprint for frontend console panel."""
    from book_translator.utils.logging import log_buffer

    bp = Blueprint("logs", __name__)

    @bp.route("/logs", methods=["GET"])
    def get_logs():
        """Get logs from in-memory buffer for the frontend console panel."""
        since_id = request.args.get("since", 0, type=int)
        if since_id > 0:
            logs = log_buffer.get_since(since_id)
        else:
            logs = log_buffer.get_all()
        return jsonify({"logs": logs})

    @bp.route("/logs/stream")
    def stream_logs():
        """Stream logs in real-time using Server-Sent Events."""

        def generate():
            last_id = 0
            while True:
                logs = log_buffer.get_since(last_id)
                for log in logs:
                    last_id = log["id"]
                    yield f"data: {json.dumps(log)}\n\n"
                time.sleep(0.5)

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    @bp.route("/logs/clear", methods=["POST"])
    def clear_logs():
        """Clear the log buffer."""
        log_buffer.clear()
        return jsonify({"message": "Logs cleared"})

    return bp
