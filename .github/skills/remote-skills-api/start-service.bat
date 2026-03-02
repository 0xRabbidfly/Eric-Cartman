@echo off
setlocal
:: Auto-start Remote Skills API at login
:: Place a shortcut to this in shell:startup, or run install-startup.ps1

set "SCRIPT_DIR=%~dp0"
set "ROOT=%SCRIPT_DIR%..\..\.."
set "LOG=%SCRIPT_DIR%server.log"

echo.>> "%LOG%"
echo [%date% %time%] Launcher invoked from "%SCRIPT_DIR%" >> "%LOG%"

pushd "%ROOT%" 2>nul
if errorlevel 1 (
	echo [%date% %time%] ERROR: Failed to enter project root "%ROOT%" >> "%LOG%"
	exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
	echo [%date% %time%] ERROR: node.exe not found on PATH >> "%LOG%"
	popd
	exit /b 1
)

if exist "%USERPROFILE%\.local\bin\claude.exe" (
	set "CLAUDE_PATH=%USERPROFILE%\.local\bin\claude.exe"
)

echo.>> "%LOG%"
echo [%date% %time%] Starting Remote Skills API from "%ROOT%" >> "%LOG%"
if defined CLAUDE_PATH echo [%date% %time%] CLAUDE_PATH="%CLAUDE_PATH%" >> "%LOG%"

node ".github\skills\remote-skills-api\server.js" >> "%LOG%" 2>&1
set "EXITCODE=%ERRORLEVEL%"
echo [%date% %time%] Remote Skills API exited with code %EXITCODE% >> "%LOG%"
popd
exit /b %EXITCODE%
