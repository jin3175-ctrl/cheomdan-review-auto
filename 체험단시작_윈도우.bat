@echo off
setlocal
cd /d "%~dp0"
title 체험단 후기 자동화
set PYTHONUTF8=1
where claude >nul 2>nul
if %errorlevel%==0 goto RUN
if exist "%USERPROFILE%\.local\bin\claude.exe" goto RUNLOCAL
echo.
echo [!] 클로드 코드가 설치되어 있지 않습니다.
echo     설치_윈도우 파일을 먼저 더블클릭해 주세요.
echo.
pause
exit /b 1

:RUNLOCAL
set PATH=%USERPROFILE%\.local\bin;%PATH%
goto RUN

:RUN
echo.
echo  클로드 코드를 시작합니다. 이렇게 말해 보세요:
echo.
echo     방금 임시저장한 글로 체험단 후기 완성해줘
echo.
claude
pause
