@echo off
setlocal

rem Move to project folder (folder where this .bat is located)
cd /d "%~dp0"

rem Set environment variables for this command session only
set "MASTODON_API_BASE_URL=https://mastodon.social"
set "MASTODON_ACCESS_TOKEN=INSERISCI_IL_TUO_TOKEN"

if "%MASTODON_ACCESS_TOKEN%"=="INSERISCI_IL_TUO_TOKEN" (
  echo ERRORE: imposta il token Mastodon nel file run_bot.bat
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo ERRORE: Python del venv non trovato in .venv\Scripts\python.exe
  exit /b 1
)

echo Avvio bot...
".venv\Scripts\python.exe" "mastodon_bot.py"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo Il bot e terminato con errore ^(exit code %EXIT_CODE%^).
) else (
  echo Bot eseguito con successo.
)

exit /b %EXIT_CODE%
