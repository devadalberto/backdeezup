@echo off
:: windows-autostart.bat — Start BackDeezUp Docker Compose stack on Windows boot
::
:: Usage: Copy this file (or a shortcut to it) into:
::   %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
::
:: On every Windows login / server boot, this will launch WSL and bring up
:: the full BackDeezUp 6-container stack (web + nginx + db + redis + celery + celerybeat).
::
:: The window is hidden so it does not interrupt the desktop.
:: Log output is written to %TEMP%\backdeezup-autostart.log for troubleshooting.

setlocal

set LOGFILE=%TEMP%\backdeezup-autostart.log

echo [%DATE% %TIME%] BackDeezUp autostart triggered >> "%LOGFILE%"

wsl -d Debian -u saitama -- bash -c "cd ~/repos/github/devadalberto/backdeezup && docker compose up -d" >> "%LOGFILE%" 2>&1

if %ERRORLEVEL% == 0 (
    echo [%DATE% %TIME%] docker compose up -d completed successfully >> "%LOGFILE%"
) else (
    echo [%DATE% %TIME%] docker compose up -d FAILED with exit code %ERRORLEVEL% >> "%LOGFILE%"
)

endlocal
