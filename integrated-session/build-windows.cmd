@echo off
setlocal
cd /d "%~dp0"
py -3 -m pip install pyinstaller==6.22.3 av==19.0.2
if errorlevel 1 exit /b 1
py -3 -m PyInstaller --noconfirm --onefile --name START-Vital-Lab-Integrated --add-data "console.html;." --add-data "student.html;." --add-data "instructor.html;." --add-data "monitor.html;." --add-data "trace.html;." --add-data "display.html;." --add-data "observer.html;." --add-data "cases.json;." --add-data "teacher.js;." --add-data "student.js;." --add-data "student-feed.js;." --add-data "common.js;." --add-data "Third-Party-Notices.txt;." hub.py
if errorlevel 1 exit /b 1
echo Built dist\START-Vital-Lab-Integrated.exe
endlocal
