@echo off
setlocal enabledelayedexpansion
set APP_NAME=Leadmachine
set SRC=leadmachine.py

echo.
echo  Leadmachine Windows Build
echo  --------------------------

REM Python prüfen
python --version >nul 2>&1
if errorlevel 1 (
    echo  FEHLER: Python nicht gefunden.
    echo  Installiere von https://www.python.org/downloads/windows/
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version') do echo  Python: %%v

REM Abhängigkeiten
echo.
echo  Installiere Abhängigkeiten...
python -m pip install --quiet --upgrade customtkinter pyinstaller
if errorlevel 1 (
    echo  FEHLER: pip fehlgeschlagen.
    exit /b 1
)

REM Build
echo.
echo  Baue %APP_NAME%...
python -m PyInstaller ^
    --windowed --onedir --name %APP_NAME% --noconfirm ^
    --collect-all customtkinter --collect-all darkdetect ^
    %SRC%
if errorlevel 1 (
    echo  FEHLER: Build fehlgeschlagen.
    exit /b 1
)

echo.
echo  Fertig: dist\%APP_NAME%\%APP_NAME%.exe
echo  Doppelklick zum Starten.
echo.
