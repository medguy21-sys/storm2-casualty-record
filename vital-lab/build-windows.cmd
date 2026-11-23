@echo off
setlocal
cd /d "%~dp0"
py -3 -m pip install pyinstaller==6.22.3
if errorlevel 1 exit /b 1
py -3 -m PyInstaller --noconfirm --onefile --name START-Vital-Lab-Mobile --add-data "index.html;." --add-data "display.html;." --add-data "observer.html;." --add-data "guide.html;." --add-data "journey.svg;." --add-data "inventory.ps1;." --add-data "Third-Party-Notices.txt;." host.py
if errorlevel 1 exit /b 1
echo Built dist\START-Vital-Lab-Mobile.exe
endlocal
