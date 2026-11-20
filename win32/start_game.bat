@echo off
title Open Toontown - Game Client
cd..

rem Read the contents of PPYTHON_PATH into %PPYTHON_PATH%:
set /P PPYTHON_PATH=<PPYTHON_PATH

set LOGIN_TOKEN=ravinmadcow
set GAME_SERVER=192.168.1.149:7198

%PPYTHON_PATH% -m toontown.launcher.QuickStartLauncher
pause
