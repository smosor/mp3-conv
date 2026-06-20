#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Skrypt instalacyjny Spotify MP3 Downloader.
    Pobiera i instaluje Pythona (jeśli brak), Flask, spotdl, yt-dlp i FFmpeg.
    Uruchamia serwer Flask po instalacji.
.DESCRIPTION
    Projekt studencki – narzędzie do pobierania playlist Spotify jako MP3 320kbps.
#>

# --- Konfiguracja ---
$PythonInstallerUrl = "https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe"
$PythonInstallerPath = "$env:TEMP\python-installer.exe"

Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║     Spotify MP3 Downloader – Instalator      ║" -ForegroundColor Green
Write-Host "  ╚══════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

# --- Sprawdzenie Pythona ---
function Find-Python {
    # Szukamy Pythona w typowych lokalizacjach
    $candidates = @(
        "python",
        "python3",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe",
        "C:\Python310\python.exe"
    )
    foreach ($p in $candidates) {
        try {
            $ver = & $p --version 2>&1
            if ($ver -match "Python 3\.(1[0-9]|\d)") {
                return $p
            }
        } catch {}
    }
    return $null
}

$PythonExe = Find-Python

if (-not $PythonExe) {
    Write-Host "  [!] Python nie znaleziony. Pobieranie instalatora..." -ForegroundColor Yellow
    Write-Host "      URL: $PythonInstallerUrl" -ForegroundColor Gray
    
    Invoke-WebRequest -Uri $PythonInstallerUrl -OutFile $PythonInstallerPath -UseBasicParsing
    Write-Host "  [✓] Pobrano instalator Pythona." -ForegroundColor Green
    
    Write-Host "  [*] Instalowanie Pythona (dodawanie do PATH)..." -ForegroundColor Cyan
    Start-Process -FilePath $PythonInstallerPath -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0" -Wait
    Remove-Item $PythonInstallerPath -Force -ErrorAction SilentlyContinue
    
    # Odśwież PATH w bieżącej sesji
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "Machine")
    
    $PythonExe = Find-Python
    if (-not $PythonExe) {
        Write-Host "  [✗] Instalacja Pythona nie powiodła się. Zainstaluj ręcznie z https://python.org" -ForegroundColor Red
        exit 1
    }
    Write-Host "  [✓] Python zainstalowany: $PythonExe" -ForegroundColor Green
} else {
    $ver = & $PythonExe --version 2>&1
    Write-Host "  [✓] Python znaleziony: $ver ($PythonExe)" -ForegroundColor Green
}

# --- Instalacja zależności Python ---
Write-Host ""
Write-Host "  [*] Instalowanie zależności Pythona (Flask, spotdl, yt-dlp)..." -ForegroundColor Cyan
& $PythonExe -m pip install --upgrade pip --quiet
& $PythonExe -m pip install -r requirements.txt --quiet

if ($LASTEXITCODE -eq 0) {
    Write-Host "  [✓] Zależności zainstalowane." -ForegroundColor Green
} else {
    Write-Host "  [✗] Błąd instalacji zależności. Sprawdź połączenie z internetem." -ForegroundColor Red
    exit 1
}

# --- Instalacja FFmpeg przez spotdl ---
Write-Host ""
Write-Host "  [*] Instalowanie FFmpeg przez spotdl..." -ForegroundColor Cyan
& $PythonExe -m spotdl --download-ffmpeg 2>&1 | Out-Null
Write-Host "  [✓] FFmpeg gotowy." -ForegroundColor Green

# --- Uruchomienie serwera ---
Write-Host ""
Write-Host "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  ✓ Instalacja zakończona!" -ForegroundColor Green
Write-Host ""
Write-Host "  Uruchamiam serwer..." -ForegroundColor Cyan
Write-Host "  Otwórz przeglądarkę: " -NoNewline
Write-Host "http://localhost:5000" -ForegroundColor Yellow
Write-Host "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""

# Otwieramy przeglądarkę po 2 sekundach
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:5000"
} | Out-Null

# Uruchamiamy Flask
& $PythonExe app.py
