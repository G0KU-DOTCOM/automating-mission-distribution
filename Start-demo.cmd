@echo off
setlocal
rem Prevent the Python install manager from downloading a runtime automatically.
set "PYTHON_MANAGER_AUTOMATIC_INSTALL=0"

if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
  if not errorlevel 1 goto use_venv
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 goto use_python
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 goto use_py

echo Python 3.11 eller nyere ble ikke funnet.
echo Installer Python fra https://www.python.org/downloads/ og start denne filen igjen.
set "DEMO_EXIT_CODE=1"
goto finish

:use_venv
"%~dp0.venv\Scripts\python.exe" -X utf8 "%~dp0start_demo.py" %*
set "DEMO_EXIT_CODE=%errorlevel%"
goto finish

:use_python
python -X utf8 "%~dp0start_demo.py" %*
set "DEMO_EXIT_CODE=%errorlevel%"
goto finish

:use_py
py -3 -X utf8 "%~dp0start_demo.py" %*
set "DEMO_EXIT_CODE=%errorlevel%"

:finish
if not "%DEMO_EXIT_CODE%"=="0" (
  echo.
  echo Oppstarten stoppet. Les meldingen over.
  if not defined CI pause
)
exit /b %DEMO_EXIT_CODE%
