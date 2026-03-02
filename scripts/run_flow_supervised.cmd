@echo off
REM Flow Video Generation - Supervisor Launcher
REM Usage: run_flow_supervised.cmd "prompt" "output.mp4"

setlocal

set PROMPT=%1
set OUTPUT=%2

if "%PROMPT%"=="" (
    echo Usage: %0 "video prompt" "output.mp4"
    echo Example: %0 "talking nail 8 seconds" "D:\Gemini-Downloads\nail.mp4"
    exit /b 1
)

if "%OUTPUT%"=="" set OUTPUT=D:\Gemini-Downloads\flow-video-%date:~-4%%date:~3,2%%date:~0,2%-%time:~0,2%%time:~3,2%.mp4

echo ============================================================
echo Flow Video Generation - Supervisor Mode
echo ============================================================
echo Prompt: %PROMPT%
echo Output: %OUTPUT%
echo ============================================================
echo.

REM Run supervisor
python "C:\Users\DELL\.openclaw\workspace\agents\sompro\skills\gemini-video-download\scripts\supervisor_flow_video.py" --prompt "%PROMPT%" --out "%OUTPUT%" --retries 2

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================================
    echo SUCCESS: Video generated and verified
    echo Output: %OUTPUT%
    echo ============================================================
) else (
    echo.
    echo ============================================================
    echo FAILED: Check audit log at D:\Gemini-Downloads\artifacts\
    echo ============================================================
)

endlocal
