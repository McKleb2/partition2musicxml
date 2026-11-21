#!/usr/bin/env python3
"""Application web : déposez un PDF de partition, récupérez le MusicXML."""

import io
import os
import shutil
import tempfile
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, send_from_directory
from werkzeug.utils import secure_filename

from converter import ConversionError, available_languages, check_installation, convert_pdf

BASE_DIR = Path(__file__).resolve().parent
JOBS_DIR = Path(os.environ.get("JOBS_DIR", tempfile.gettempdir())) / "partition2musicxml-jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)
MAX_MB = int(os.environ.get("MAX_UPLOAD_MB", "50"))
JOB_TTL = 3600  # les résultats sont effacés au bout d'une heure
ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_MB * 1024 * 1024

# Audiveris est gourmand en mémoire : on limite les conversions simultanées.
executor = ThreadPoolExecutor(max_workers=int(os.environ.get("WORKERS", "2")))
jobs: dict[str, dict] = {}
lock = threading.Lock()


def _cleanup():
    now = time.time()
    with lock:
        for jid in [j for j, d in jobs.items() if now - d["created"] > JOB_TTL]:
            shutil.rmtree(JOBS_DIR / jid, ignore_errors=True)
            del jobs[jid]


def _run(jid: str, src: Path, langs: list[str], compressed: bool, name: str):
    jobs[jid]["status"] = "running"
    jobs[jid]["started"] = time.time()
    try:
        res = convert_pdf(src, JOBS_DIR / jid / "out", languages=langs,
                          compressed=compressed, display_name=name)
        jobs[jid].update(status="done", files=[f.name for f in res.files], warnings=res.warnings)
    except ConversionError as e:
        jobs[jid].update(status="error", error=str(e), log=e.log)
    except Exception as e:  # garde-fou : on ne laisse jamais une tâche bloquée
        jobs[jid].update(status="error", error=f"Erreur inattendue : {e}")
    finally:
        jobs[jid]["finished"] = time.time()


@app.get("/")
def index():
    return send_from_directory(BASE_DIR / "static", "index.html")


@app.get("/static/<path:p>")
def static_files(p):
    return send_from_directory(BASE_DIR / "static", p)


@app.get("/api/status")
def status():
    return jsonify(problems=check_installation(), languages=available_languages(), max_mb=MAX_MB)


@app.post("/api/convert")
def convert():
    _cleanup()
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(error="Aucun fichier reçu."), 400
    name = Path(f.filename).name
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED:
        return jsonify(error="Format non pris en charge : envoyez un PDF (ou une image PNG, JPG, TIFF)."), 400

    jid = uuid.uuid4().hex
    d = JOBS_DIR / jid
    d.mkdir(parents=True)
    src = d / (secure_filename(name) or f"partition{ext}")
    if src.suffix.lower() != ext:
        src = src.with_suffix(ext)
    f.save(src)
    if ext == ".pdf" and not src.read_bytes()[:5] == b"%PDF-":
        shutil.rmtree(d, ignore_errors=True)
        return jsonify(error="Ce fichier n'est pas un PDF valide."), 400

    langs = [l for l in request.form.get("lang", "fra+eng").split("+") if l]
    compressed = request.form.get("format", "mxl") != "musicxml"
    with lock:
        jobs[jid] = {"status": "queued", "name": name, "created": time.time()}
    executor.submit(_run, jid, src, langs, compressed, name)
    return jsonify(id=jid), 202


@app.get("/api/jobs/<jid>")
def job(jid):
    j = jobs.get(jid) or abort(404)
    out = {k: j.get(k) for k in ("status", "name", "files", "warnings", "error", "log")}
    if j.get("started"):
        out["elapsed"] = round((j.get("finished") or time.time()) - j["started"])
    return jsonify(out)


@app.get("/api/jobs/<jid>/files/<fname>")
def download(jid, fname):
    j = jobs.get(jid) or abort(404)
    if fname not in (j.get("files") or []):
        abort(404)
    inline = request.args.get("inline") == "1"
    return send_from_directory(JOBS_DIR / jid / "out", fname, as_attachment=not inline,
                               mimetype="application/vnd.recordare.musicxml" if fname.endswith(".mxl")
                               else "application/vnd.recordare.musicxml+xml")


@app.get("/api/jobs/<jid>/zip")
def download_zip(jid):
    j = jobs.get(jid) or abort(404)
    if not j.get("files"):
        abort(404)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for fname in j["files"]:
            z.write(JOBS_DIR / jid / "out" / fname, fname)
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name=f"{Path(j['name']).stem}-musicxml.zip")


@app.errorhandler(413)
def too_large(_):
    return jsonify(error=f"Fichier trop volumineux (maximum {MAX_MB} Mo)."), 413


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    print(f"Application disponible sur http://{host}:{port}")
    app.run(host=host, port=port, threaded=True)
