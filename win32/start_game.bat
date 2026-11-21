@echo off
title Open Toontown - Game Client
cd..

rem Read the contents of PPYTHON_PATH into %PPYTHON_PATH%:
set /P PPYTHON_PATH=<PPYTHON_PATH

rem Your own username and server address are kept in win32\my_settings.bat.
rem That file is never uploaded to GitHub, so updates never overwrite it.
rem It is made the first time you play; delete it to set things up again.
if exist win32\my_settings.bat goto play

echo.
echo  First-time setup
echo  ----------------
set /P NEW_NAME=Choose your username: 
set /P NEW_SERVER=Server IP address (leave blank if the server runs on this PC): 
> win32\my_settings.bat echo set LOGIN_TOKEN=%NEW_NAME%
if "%NEW_SERVER%"=="" goto play
>> win32\my_settings.bat echo set GAME_SERVER=%NEW_SERVER%:7198

:play
call win32\my_settings.bat
%PPYTHON_PATH% -m toontown.launcher.QuickStartLauncher
pause
