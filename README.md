# Spotify MP3 Downloader

Webowa aplikacja do pobierania playlist ze Spotify w formacie **MP3 320 kbps**.
Projekt studencki.

---

## Wymagania

| Zależność | Wersja | Instalacja |
|-----------|--------|-----------|
| Python    | 3.10+  | [python.org](https://python.org) |
| FFmpeg    | dowolna | patrz niżej |
| pip       | –      | wbudowany w Python |

### Instalacja FFmpeg (Windows)

```powershell
# Najprościej – przez spotdl (pobierze FFmpeg automatycznie):
spotdl --download-ffmpeg
```

Lub ręcznie – pobierz z https://ffmpeg.org i dodaj do zmiennej PATH.

---

## Instalacja i uruchomienie

```powershell
# 1. Sklonuj/przejdź do katalogu projektu
cd q:\mp3-conv

# 2. Zainstaluj zależności Pythona
pip install -r requirements.txt

# 3. Zainstaluj FFmpeg przez spotdl (pierwsze uruchomienie)
spotdl --download-ffmpeg

# 4. Uruchom serwer Flask
python app.py

# 5. Otwórz w przeglądarce:
#    http://localhost:5000
```

---

## Jak używać

1. Otwórz `http://localhost:5000` w przeglądarce
2. Wklej link do playlisty Spotify (np. `https://open.spotify.com/playlist/...`)
3. Kliknij **Pobierz**
4. Poczekaj na zakończenie pobierania (postęp widoczny w czasie rzeczywistym)
5. Pobierz wszystkie pliki jako **ZIP** jednym kliknięciem

Pobrane pliki MP3 znajdziesz w katalogu `downloads/<job_id>/`.

---

## Architektura

```
app.py              ← backend Flask (API + logika pobierania)
templates/
  index.html        ← frontend (HTML + CSS + JS w jednym pliku)
downloads/          ← katalog pobieranych plików (tworzony automatycznie)
requirements.txt    ← zależności Pythona
```

### Endpointy API

| Metoda | Endpoint | Opis |
|--------|----------|------|
| `GET`  | `/` | Strona główna (UI) |
| `POST` | `/api/download` | Rozpocznij pobieranie playlisty |
| `GET`  | `/api/status/<job_id>` | Status i postęp zadania |
| `GET`  | `/api/download-zip/<job_id>` | Pobierz pliki jako ZIP |

---

## Uwagi prawne

> Narzędzie przeznaczone wyłącznie do celów **edukacyjnych**. Pobieranie treści
> chronionych prawem autorskim może naruszać regulamin Spotify i obowiązujące
> przepisy prawa. Używaj odpowiedzialnie.

---

## Technologie

- [Flask](https://flask.palletsprojects.com/) – backend webowy
- [spotDL](https://github.com/spotDL/spotify-downloader) – pobieranie z Spotify
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) – silnik pobierania audio
- [FFmpeg](https://ffmpeg.org/) – konwersja do MP3 320kbps
