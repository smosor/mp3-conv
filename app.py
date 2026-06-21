"""
Spotify Playlist Downloader - główny plik aplikacji Flask.
Obsługuje pobieranie playlist ze Spotify w formacie MP3 320kbps
przy użyciu narzędzia spotdl i FFmpeg.
"""

import os
import uuid
import threading
import zipfile
import subprocess
import json
import re
from pathlib import Path
from datetime import datetime
import sys
from flask import Flask, request, jsonify, render_template, send_file, abort

# --- Inicjalizacja aplikacji ---
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # max 16 MB body

# Katalog, w którym zapisywane są pobrane pliki
DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)

# Słownik przechowujący stany zadań: { job_id: { status, progress, tracks, errors } }
jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────────────────────
# Funkcje pomocnicze
# ─────────────────────────────────────────────────────────────────────────────

def is_valid_spotify_url(url: str) -> bool:
    """Sprawdza, czy podany URL jest prawidłowym linkiem do playlisty Spotify."""
    pattern = r"https?://open\.spotify\.com/(intl-[a-z]+/)?playlist/[A-Za-z0-9]+"
    return bool(re.match(pattern, url.strip()))


def update_job(job_id: str, **kwargs) -> None:
    """Aktualizuje stan zadania w słowniku jobs."""
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(kwargs)


def run_download(job_id: str, playlist_url: str, output_dir: Path) -> None:
    """
    Funkcja uruchamiana w osobnym wątku.
    Wywołuje spotdl i śledzi postęp pobierania na podstawie wyjścia konsoli.
    """
    update_job(job_id, status="running", started_at=datetime.now().isoformat())

    # Komenda spotdl: pobierz playlistę, konwertuj do MP3 320kbps
    cmd = [
        sys.executable, "-m", "spotdl",
        playlist_url,
        "--output", str(output_dir),
        "--format", "mp3",
        "--bitrate", "320k",
        "--threads", "4",
        "--print-errors",
    ]

    try:
        # Uruchamiamy proces i czytamy wyjście linia po linii
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        tracks_found = 0
        tracks_done = 0
        tracks_error = 0
        log_lines = []

        for line in process.stdout:
            line = line.rstrip()
            if not line:
                continue

            log_lines.append(line)

            # Parsowanie wyjścia spotdl – wykrywanie postępu
            if "Found" in line and "song" in line:
                # np. "Found 42 songs in playlist"
                m = re.search(r"Found (\d+)", line)
                if m:
                    tracks_found = int(m.group(1))
                    update_job(job_id, tracks_total=tracks_found)

            elif "Downloaded" in line or "Converted" in line:
                tracks_done += 1
                # Wyciągamy nazwę pliku z linii np. "Downloaded: Artysta - Tytuł.mp3"
                m = re.search(r'(?:Downloaded|Converted)[:\s]+(.+)', line)
                track_name = m.group(1).strip() if m else line
                update_job(
                    job_id,
                    tracks_done=tracks_done,
                    last_track=track_name,
                    progress=int((tracks_done / max(tracks_found, 1)) * 100),
                )

            elif "Skipping" in line or "Failed" in line or "Error" in line:
                tracks_error += 1
                update_job(job_id, tracks_error=tracks_error)

        process.wait()

        # Zbieramy nazwy pobranych plików MP3
        downloaded_files = [
            f.name for f in output_dir.iterdir()
            if f.is_file() and f.suffix.lower() == ".mp3"
        ]

        if process.returncode == 0 or downloaded_files:
            update_job(
                job_id,
                status="done",
                progress=100,
                tracks_done=len(downloaded_files),
                files=downloaded_files,
                finished_at=datetime.now().isoformat(),
                log=log_lines[-50:],  # ostatnie 50 linii logu
            )
        else:
            update_job(
                job_id,
                status="error",
                error="spotdl zakończył się błędem. Sprawdź logi.",
                log=log_lines[-50:],
                finished_at=datetime.now().isoformat(),
            )

    except FileNotFoundError:
        # spotdl nie jest zainstalowane lub nie ma go w PATH
        update_job(
            job_id,
            status="error",
            error="Nie znaleziono 'spotdl'. Upewnij się, że jest zainstalowane: pip install spotdl",
            finished_at=datetime.now().isoformat(),
        )
    except Exception as exc:
        update_job(
            job_id,
            status="error",
            error=f"Nieoczekiwany błąd: {str(exc)}",
            finished_at=datetime.now().isoformat(),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Endpointy API
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Strona główna – zwraca interfejs użytkownika."""
    return render_template("index.html")


@app.route("/api/download", methods=["POST"])
def api_download():
    """
    Przyjmuje URL playlisty Spotify i rozpoczyna pobieranie w tle.
    Zwraca job_id do śledzenia postępu.
    """
    data = request.get_json(silent=True) or {}
    playlist_url = (data.get("url") or "").strip()

    if not playlist_url:
        return jsonify({"error": "Brak URL playlisty."}), 400

    if not is_valid_spotify_url(playlist_url):
        return jsonify({
            "error": "Nieprawidłowy URL. Podaj link do playlisty Spotify, np. https://open.spotify.com/playlist/..."
        }), 400

    # Tworzymy nowe zadanie
    job_id = str(uuid.uuid4())
    output_dir = DOWNLOADS_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    with jobs_lock:
        jobs[job_id] = {
            "id": job_id,
            "url": playlist_url,
            "status": "queued",      # queued | running | done | error
            "progress": 0,
            "tracks_total": 0,
            "tracks_done": 0,
            "tracks_error": 0,
            "last_track": "",
            "files": [],
            "error": None,
            "log": [],
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "finished_at": None,
        }

    # Uruchamiamy pobieranie w osobnym wątku (nie blokujemy requestu)
    thread = threading.Thread(
        target=run_download,
        args=(job_id, playlist_url, output_dir),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id}), 202


@app.route("/api/status/<job_id>")
def api_status(job_id: str):
    """Zwraca aktualny stan zadania pobierania."""
    with jobs_lock:
        job = jobs.get(job_id)

    if job is None:
        return jsonify({"error": "Nie znaleziono zadania."}), 404

    return jsonify(job)


@app.route("/api/download-zip/<job_id>")
def api_download_zip(job_id: str):
    """
    Pakuje wszystkie pobrane pliki MP3 do archiwum ZIP
    i wysyła je do przeglądarki użytkownika.
    """
    with jobs_lock:
        job = jobs.get(job_id)

    if job is None:
        return abort(404)

    if job["status"] != "done":
        return jsonify({"error": "Pobieranie jeszcze nie zakończyło się."}), 400

    output_dir = DOWNLOADS_DIR / job_id
    mp3_files = list(output_dir.glob("*.mp3"))

    if not mp3_files:
        return jsonify({"error": "Brak plików MP3 do pobrania."}), 404

    # Tworzymy archiwum ZIP w pamięci
    zip_path = output_dir / "playlist.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for mp3 in mp3_files:
            zf.write(mp3, mp3.name)

    return send_file(
        zip_path,
        as_attachment=True,
        download_name="spotify_playlist.zip",
        mimetype="application/zip",
    )


@app.route("/api/jobs")
def api_jobs():
    """Zwraca listę wszystkich zadań (do debugowania)."""
    with jobs_lock:
        return jsonify(list(jobs.values()))


# ─────────────────────────────────────────────────────────────────────────────
# Start serwera
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Spotify MP3 Downloader")
    print("  Otwórz przeglądarkę: http://localhost:5000")
    print("=" * 60)
    app.run(debug=True, host="0.0.0.0", port=5000)
