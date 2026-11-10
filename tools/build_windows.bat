@echo off
REM Builds tools\dist\tSPA_Designer.exe (single file, no console window).
REM Requires Python 3.9+ on Windows. Run from the tools folder: build_windows.bat
cd /d "%~dp0"
python -m pip install --upgrade pyside6 pyinstaller || goto :err
python -m PyInstaller --noconfirm --onefile --windowed --name tSPA_Designer tspa_designer_gui.py || goto :err
echo.
echo Done: %~dp0dist\tSPA_Designer.exe
pause
exit /b 0
:err
echo Build failed.
pause
exit /b 1
