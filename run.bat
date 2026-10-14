@echo off
set "SCRIPT_DIR=%~dp0"
if exist "C:\Python314\pythonw.exe" (
    start "" "C:\Python314\pythonw.exe" "%SCRIPT_DIR%app.py"
) else (
    start "" pythonw "%SCRIPT_DIR%app.py"
)
exit
