@echo off
cd /d %~dp0
echo.
echo YOUSSEF.COM v8 - Keep existing v7 data
echo Paste the FULL path to your old YOUSSEF_COM_v7 folder below.
echo Example: C:\Users\ADMIN\Desktop\YOUSSEF_COM_v7
set /p OLD_FOLDER=Old v7 folder: 
if "%OLD_FOLDER%"=="" goto :cancel
if not exist "%OLD_FOLDER%\youssef.db" (
  echo.
  echo ERROR: Could not find youssef.db in that folder.
  pause
  exit /b 1
)
copy /Y "%OLD_FOLDER%\youssef.db" "%~dp0youssef.db" >nul
if errorlevel 1 (
  echo ERROR copying database.
  pause
  exit /b 1
)
echo.
echo Existing database copied successfully. Start YOUSSEF.COM v8 now.
pause
exit /b 0
:cancel
echo Cancelled.
pause
