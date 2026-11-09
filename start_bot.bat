@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title FiveM 디스코드 봇
cd /d "%~dp0"

rem ============================================================
rem  FiveM 디스코드 봇 실행 배치 파일 (Windows)
rem   - 처음 실행: 가상환경(venv-win) 생성 + 패키지 설치 + 봇 실행
rem   - 이후 실행: 바로 봇 실행
rem   - 봇이 오류로 꺼지면 자동 재시작 (연속 실패 시 중단)
rem   - 패키지를 다시 설치하려면:  start_bot.bat --reinstall
rem ============================================================

set "VENV_DIR=venv-win"
set "MAX_RESTARTS=5"
set "RESTART_DELAY=5"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

echo ============================================
echo   FiveM 디스코드 봇 실행기
echo ============================================
echo.

rem ---------- 1) 필수 파일 확인 ----------
if not exist "main.py" (
    echo [오류] main.py 를 찾을 수 없습니다.
    echo        이 배치 파일을 봇 폴더 안에 넣고 실행하세요.
    goto :fail
)

if not exist ".env" (
    echo [오류] .env 파일이 없습니다. 봇 폴더에 아래 내용으로 만들어 주세요.
    echo.
    echo     DISCORD_TOKEN=봇토큰
    echo     ADMIN_ROLE_ID=관리자역할ID
    goto :fail
)

findstr /r /b /c:"DISCORD_TOKEN *=" ".env" >nul
if errorlevel 1 (
    echo [오류] .env 파일에 DISCORD_TOKEN 항목이 없습니다.
    goto :fail
)

rem ---------- 2) Python 찾기 ----------
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (
    python --version >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo [오류] Python 을 찾을 수 없습니다.
    echo        https://www.python.org/downloads/ 에서 설치하세요.
    echo        설치 첫 화면에서 "Add python.exe to PATH" 를 꼭 체크해야 합니다.
    goto :fail
)

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"
if errorlevel 1 (
    echo [오류] Python 3.8 이상이 필요합니다. 최신 버전으로 설치해 주세요.
    goto :fail
)

rem ---------- 3) 가상환경 준비 ----------
rem 압축파일 안의 venv 폴더는 리눅스용이라 윈도우에서 못 쓰므로 venv-win 을 따로 만듭니다.
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [1/3] 가상환경을 만드는 중입니다...
    %PY% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [오류] 가상환경 생성에 실패했습니다.
        goto :fail
    )
)
set "VPY=%VENV_DIR%\Scripts\python.exe"

rem ---------- 4) 패키지 설치 (처음 한 번만) ----------
if /i "%~1"=="--reinstall" del "%VENV_DIR%\.deps_ok" >nul 2>&1

if not exist "%VENV_DIR%\.deps_ok" (
    echo [2/3] 필요한 패키지를 설치하는 중입니다...
    "%VPY%" -m pip install --upgrade pip >nul 2>&1
    "%VPY%" -m pip install "discord.py==2.7.1" python-dotenv
    if errorlevel 1 (
        echo [오류] 패키지 설치에 실패했습니다. 인터넷 연결을 확인하세요.
        goto :fail
    )
    echo ok> "%VENV_DIR%\.deps_ok"
)

rem ---------- 5) 봇 실행 (비정상 종료 시 자동 재시작) ----------
set /a RESTARTS=0

:run
echo.
echo [3/3] 봇을 시작합니다. 종료하려면 Ctrl+C 를 누르고 Y 를 입력하세요.
echo --------------------------------------------
call :now START_T
"%VPY%" main.py
set "EXITCODE=%errorlevel%"
call :now END_T

if "%EXITCODE%"=="0" (
    echo.
    echo 봇이 정상적으로 종료되었습니다.
    goto :end
)

rem 1분 이상 정상 동작했다면 연속 실패 횟수를 초기화
set /a UPTIME=END_T-START_T
if !UPTIME! lss 0 set /a UPTIME+=86400
if !UPTIME! geq 60 set /a RESTARTS=0

set /a RESTARTS+=1
echo.
echo [경고] 봇이 비정상 종료되었습니다. 종료 코드: %EXITCODE%

if !RESTARTS! geq %MAX_RESTARTS% (
    echo [오류] 연속 %MAX_RESTARTS%회 실패하여 자동 재시작을 중단합니다.
    echo        위쪽 오류 메시지를 확인하세요. 토큰 오류나 인텐트 설정 문제일 수 있습니다.
    goto :fail
)

echo %RESTART_DELAY%초 후 자동으로 다시 시작합니다. 시도 !RESTARTS!/%MAX_RESTARTS%
timeout /t %RESTART_DELAY% /nobreak >nul
goto :run

:end
echo.
pause
endlocal
exit /b 0

:fail
echo.
pause
endlocal
exit /b 1

rem ---------- 현재 시각을 초 단위로 반환하는 함수 ----------
:now
set "t=%time: =0%"
set /a "%~1=(1!t:~0,2!-100)*3600+(1!t:~3,2!-100)*60+(1!t:~6,2!-100)"
exit /b
