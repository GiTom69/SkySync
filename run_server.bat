@echo off
REM SkySync Server Runner

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Run the FastAPI server
uvicorn main:app --reload --host 127.0.0.1 --port 8000

pause
