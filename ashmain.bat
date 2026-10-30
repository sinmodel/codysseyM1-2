
@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PROJECT_DIR=%~dp0"
set "PYTHONPATH=%PROJECT_DIR%"
set "VENV_DIR=%LOCALAPPDATA%\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\Local\AIStockHelper\venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

title AI Stock Helper - 실행

echo.
echo ==========================================
echo       AI Stock Helper 실행
echo ==========================================
echo.

if not exist "%PROJECT_DIR%.env" (
    echo [오류] USB 프로젝트 폴더에 .env 파일이 없습니다.
    pause
    exit /b 1
)

if not exist "%VENV_PY%" goto CREATE_VENV
goto CHECK_PACKAGES

:CREATE_VENV
echo [1/4] 로컬 가상환경을 생성합니다.

where python >nul 2>nul
if not errorlevel 1 goto USE_PYTHON

where py >nul 2>nul
if not errorlevel 1 goto USE_PY

echo [오류] Python을 찾을 수 없습니다.
pause
exit /b 1

:USE_PYTHON
python -m venv "%VENV_DIR%"
if errorlevel 1 goto SETUP_ERROR
goto CHECK_PACKAGES

:USE_PY
py -3 -m venv "%VENV_DIR%"
if errorlevel 1 goto SETUP_ERROR
goto CHECK_PACKAGES

:CHECK_PACKAGES
echo [2/4] 필수 패키지를 확인합니다.

"%VENV_PY%" -c "import fastapi, uvicorn, firebase_admin, dotenv, openai" >nul 2>nul
if not errorlevel 1 goto START_SERVER

echo 필요한 패키지를 설치합니다. 잠시 기다려 주세요.
"%VENV_PY%" -m pip install -r "%PROJECT_DIR%requirements.txt"
if errorlevel 1 goto SETUP_ERROR

:START_SERVER
echo [3/4] 서버를 시작합니다.
echo [4/4] 브라우저를 엽니다.
echo.
echo 종료하려면 이 창에서 Ctrl+C를 누르세요.
echo.

"%VENV_PY%" "app\main.py"

echo.
echo 서버가 정상적으로 종료되었습니다.
exit /b 0

:SETUP_ERROR
echo.
echo [오류] 실행 준비에 실패했습니다.
pause
exit /b 1
