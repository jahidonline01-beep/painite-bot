@echo off
title Painite Admin Windows Launcher
echo ========================================================
echo   Starting Painite Admin Server & Telegram Bot...
echo ========================================================
echo.
if not exist node_modules (
    echo Installing dependencies, please wait...
    call npm install
)
echo Starting Painite server...
start http://localhost:3000
npm start
pause
