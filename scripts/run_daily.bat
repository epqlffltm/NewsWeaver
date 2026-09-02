@echo off
REM NewsWeaver/scripts/run_daily.bat
REM 작업 스케줄러에서 호출하는 일일 배치 실행 스크립트.
REM 스케줄러는 가상환경과 작업 디렉터리를 알지 못하므로 여기서 명시한다.

cd /d "%~dp0.."

uv run python -m news_weaver.cli

exit /b %ERRORLEVEL%