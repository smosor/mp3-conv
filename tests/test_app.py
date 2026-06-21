"""
Testy jednostkowe dla aplikacji Spotify MP3 Downloader.
Testują endpointy API, walidację URL-i i logikę pomocniczą
bez wywoływania spotdl (mockujemy subprocess).
"""

import json
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ─── Import aplikacji ──────────────────────────────────────────────────────────
import sys
import os

# Dodajemy katalog nadrzędny do sys.path, żeby importy działały
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, is_valid_spotify_url, update_job, jobs, jobs_lock


# ─── Fixture: klient testowy Flask ─────────────────────────────────────────────
@pytest.fixture
def client():
    """Tworzy testowego klienta Flask."""
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def cleanup_jobs():
    """Czyści słownik zadań przed każdym testem."""
    with jobs_lock:
        jobs.clear()
    yield
    with jobs_lock:
        jobs.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# Testy walidacji URL-a Spotify
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsValidSpotifyUrl:
    """Testy funkcji is_valid_spotify_url."""

    def test_valid_playlist_url(self):
        url = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
        assert is_valid_spotify_url(url) is True

    def test_valid_playlist_url_with_intl(self):
        url = "https://open.spotify.com/intl-pl/playlist/37i9dQZF1DXcBWIGoYBM5M"
        assert is_valid_spotify_url(url) is True

    def test_valid_playlist_url_http(self):
        url = "http://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
        assert is_valid_spotify_url(url) is True

    def test_invalid_url_track(self):
        url = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"
        assert is_valid_spotify_url(url) is False

    def test_invalid_url_album(self):
        url = "https://open.spotify.com/album/4aawyAB9vmqN3uQ7FjRGTy"
        assert is_valid_spotify_url(url) is False

    def test_invalid_url_random_string(self):
        assert is_valid_spotify_url("not-a-url-at-all") is False

    def test_invalid_url_empty(self):
        assert is_valid_spotify_url("") is False

    def test_invalid_url_youtube(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert is_valid_spotify_url(url) is False

    def test_valid_url_with_whitespace(self):
        url = "  https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M  "
        assert is_valid_spotify_url(url) is True


# ═══════════════════════════════════════════════════════════════════════════════
# Testy funkcji update_job
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpdateJob:
    """Testy funkcji update_job."""

    def test_update_existing_job(self):
        with jobs_lock:
            jobs["test-123"] = {"status": "queued", "progress": 0}

        update_job("test-123", status="running", progress=50)

        assert jobs["test-123"]["status"] == "running"
        assert jobs["test-123"]["progress"] == 50

    def test_update_nonexistent_job_does_nothing(self):
        update_job("nonexistent-id", status="running")
        assert "nonexistent-id" not in jobs

    def test_update_adds_new_fields(self):
        with jobs_lock:
            jobs["test-456"] = {"status": "queued"}

        update_job("test-456", last_track="Song.mp3", tracks_done=5)

        assert jobs["test-456"]["last_track"] == "Song.mp3"
        assert jobs["test-456"]["tracks_done"] == 5


# ═══════════════════════════════════════════════════════════════════════════════
# Testy endpointu GET /
# ═══════════════════════════════════════════════════════════════════════════════

class TestIndexPage:
    """Testy strony głównej."""

    def test_index_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_index_returns_html(self, client):
        response = client.get("/")
        assert b"Spotify MP3 Downloader" in response.data

    def test_index_contains_form_elements(self, client):
        response = client.get("/")
        html = response.data.decode("utf-8")
        assert 'id="playlist-url"' in html
        assert 'id="btn-download"' in html


# ═══════════════════════════════════════════════════════════════════════════════
# Testy endpointu POST /api/download
# ═══════════════════════════════════════════════════════════════════════════════

class TestApiDownload:
    """Testy endpointu rozpoczynającego pobieranie."""

    def test_missing_url_returns_400(self, client):
        response = client.post(
            "/api/download",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_empty_url_returns_400(self, client):
        response = client.post(
            "/api/download",
            data=json.dumps({"url": ""}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_invalid_url_returns_400(self, client):
        response = client.post(
            "/api/download",
            data=json.dumps({"url": "https://youtube.com/watch?v=abc"}),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "Nieprawidłowy URL" in data["error"]

    @patch("app.threading.Thread")
    def test_valid_url_returns_202_with_job_id(self, mock_thread_cls, client):
        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        response = client.post(
            "/api/download",
            data=json.dumps({
                "url": "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
            }),
            content_type="application/json",
        )

        assert response.status_code == 202
        data = response.get_json()
        assert "job_id" in data
        mock_thread.start.assert_called_once()

    @patch("app.threading.Thread")
    def test_valid_url_creates_job_entry(self, mock_thread_cls, client):
        mock_thread_cls.return_value = MagicMock()

        response = client.post(
            "/api/download",
            data=json.dumps({
                "url": "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
            }),
            content_type="application/json",
        )

        job_id = response.get_json()["job_id"]
        assert job_id in jobs
        assert jobs[job_id]["status"] == "queued"
        assert jobs[job_id]["progress"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Testy endpointu GET /api/status/<job_id>
# ═══════════════════════════════════════════════════════════════════════════════

class TestApiStatus:
    """Testy endpointu statusu zadania."""

    def test_nonexistent_job_returns_404(self, client):
        response = client.get("/api/status/nonexistent-id")
        assert response.status_code == 404

    def test_existing_job_returns_status(self, client):
        with jobs_lock:
            jobs["job-abc"] = {
                "id": "job-abc",
                "status": "running",
                "progress": 42,
                "tracks_total": 10,
                "tracks_done": 4,
                "tracks_error": 0,
                "last_track": "Test Song.mp3",
                "files": [],
                "error": None,
                "log": [],
            }

        response = client.get("/api/status/job-abc")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "running"
        assert data["progress"] == 42
        assert data["last_track"] == "Test Song.mp3"


# ═══════════════════════════════════════════════════════════════════════════════
# Testy endpointu GET /api/download-zip/<job_id>
# ═══════════════════════════════════════════════════════════════════════════════

class TestApiDownloadZip:
    """Testy endpointu pobierania archiwum ZIP."""

    def test_nonexistent_job_returns_404(self, client):
        response = client.get("/api/download-zip/nonexistent-id")
        assert response.status_code == 404

    def test_not_done_job_returns_400(self, client):
        with jobs_lock:
            jobs["job-running"] = {"status": "running"}

        response = client.get("/api/download-zip/job-running")
        assert response.status_code == 400

    def test_done_job_with_no_files_returns_404(self, client, tmp_path):
        job_id = "job-nofiles"
        job_dir = tmp_path / job_id
        job_dir.mkdir()

        with jobs_lock:
            jobs[job_id] = {"status": "done", "files": []}

        # Podmiana DOWNLOADS_DIR na tmp_path
        with patch("app.DOWNLOADS_DIR", tmp_path):
            response = client.get(f"/api/download-zip/{job_id}")
            assert response.status_code == 404

    def test_done_job_with_files_returns_zip(self, client, tmp_path):
        job_id = "job-withfiles"
        job_dir = tmp_path / job_id
        job_dir.mkdir()
        # Tworzymy testowy plik MP3
        (job_dir / "TestSong.mp3").write_bytes(b"fake mp3 data")

        with jobs_lock:
            jobs[job_id] = {"status": "done", "files": ["TestSong.mp3"]}

        with patch("app.DOWNLOADS_DIR", tmp_path):
            response = client.get(f"/api/download-zip/{job_id}")
            assert response.status_code == 200
            assert response.content_type == "application/zip"
            assert response.headers.get("Content-Disposition") is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Testy endpointu GET /api/jobs
# ═══════════════════════════════════════════════════════════════════════════════

class TestApiJobs:
    """Testy endpointu listy zadań."""

    def test_empty_jobs_returns_empty_list(self, client):
        response = client.get("/api/jobs")
        assert response.status_code == 200
        assert response.get_json() == []

    def test_returns_all_jobs(self, client):
        with jobs_lock:
            jobs["job-1"] = {"id": "job-1", "status": "done"}
            jobs["job-2"] = {"id": "job-2", "status": "running"}

        response = client.get("/api/jobs")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 2
