@echo off
cd /d %~dp0
python -m pip install -r requirements.txt
set /p ADMIN_PASSWORD=Choose admin password: 
if "%ADMIN_PASSWORD%"=="" set ADMIN_PASSWORD=123456
python server.py
pause
