@echo off
rem Copy the app to the badge, restart it, then save what the badge prints
rem to badge_log.txt.  "deploy.bat all" also copies ship_data.py.
cd /d "%~dp0"
rem The badge's serial port. Change this if Windows gives it another number.
set BADGE_PORT=COM13
set FILES=__init__.py app.py game.py cockpit.py viewer.py bench.py tildagon.toml metadata.json
if /i "%1"=="all" set FILES=%FILES% ship_data.py

echo Copying to the badge...
mpremote connect %BADGE_PORT% fs mkdir :/apps/elite_demo > nul 2>&1
mpremote connect %BADGE_PORT% cp %FILES% :/apps/elite_demo/ > badge_log.txt 2>&1
if errorlevel 1 (
    type badge_log.txt
    echo.
    echo COPY FAILED. Is the badge on %BADGE_PORT%, and is another mpremote window open?
    pause
    exit /b 1
)
type badge_log.txt
mpremote connect %BADGE_PORT% reset >> badge_log.txt 2>&1

echo.
echo Saving the badge's output to badge_log.txt for 5 minutes.
echo Use the badge now. Close this window or press Ctrl+C to stop early.
python tools\badge_log.py 300 %BADGE_PORT%
if errorlevel 9009 py tools\badge_log.py 300 %BADGE_PORT%
