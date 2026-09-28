@echo off
REM ---------------------------------------------------------------
REM  Start the app + cloudflared quick tunnel (public HTTPS access)
REM  Usage: double-click this file, or run it in a terminal.
REM  NOTE: quick tunnels are ephemeral - every run gives a NEW url.
REM        Watch for the "https://xxxx.trycloudflare.com" line below.
REM ---------------------------------------------------------------
cd /d "%~dp0.."

set "CF=cloudflared"
where cloudflared >nul 2>nul || set "CF=C:\Program Files (x86)\cloudflared\cloudflared.exe"

REM Bind to loopback only: the tunnel runs on this machine, so there is
REM no need to expose the app to the local network.
set "HOST=127.0.0.1"
set "PORT=8300"

echo [1/2] Starting app on %HOST%:%PORT% ...
start "RAG-fate-app" cmd /k python main.py
timeout /t 5 /nobreak >nul

echo [2/2] Opening cloudflared quick tunnel ...
echo       (the public url is printed a few lines below)
echo.
"%CF%" tunnel --url http://127.0.0.1:%PORT% --no-autoupdate
pause