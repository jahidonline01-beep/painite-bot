@echo off
title Painite Admin Windows Desktop App
echo ========================================================
echo   Launching Painite Admin Windows Desktop App...
echo ========================================================
echo.
if not exist node_modules (
    echo Installing dependencies, please wait...
    call npm install
)
echo Launching Desktop App Window...
call npm run electron
pause
