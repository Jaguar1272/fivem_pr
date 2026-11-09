#!/usr/bin/env bash
# ============================================================
#  FiveM 디스코드 봇 실행 쉘 스크립트 (Linux)
#   - 처음 실행: 가상환경(venv) 생성 + 패키지 설치 + 봇 실행
#   - 이후 실행: 바로 봇 실행
#   - 봇이 오류로 꺼지면 자동 재시작 (연속 실패 시 중단)
#   - 패키지를 다시 설치하려면:  ./start_fivem_bot.sh --reinstall
# ============================================================

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

VENV_DIR="venv"
MAX_RESTARTS=5
RESTART_DELAY=5

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${SCRIPT_DIR}" || exit 1

echo "============================================"
echo "  FiveM 디스코드 봇 실행기"
echo "============================================"
echo

# ---------- 1) 필수 파일 확인 ----------
if [ ! -f "main.py" ]; then
    echo "[오류] main.py 를 찾을 수 없습니다."
    echo "       이 스크립트를 봇 폴더 안에 넣고 실행하세요."
    exit 1
fi

if [ ! -f ".env" ]; then
    echo "[오류] .env 파일이 없습니다. 봇 폴더에 아래 내용으로 만들어 주세요."
    echo
    echo "    DISCORD_TOKEN=봇토큰"
    echo "    ADMIN_ROLE_ID=관리자역할ID"
    exit 1
fi

if ! grep -E "^DISCORD_TOKEN *=" .env >/dev/null 2>&1; then
    echo "[오류] .env 파일에 DISCORD_TOKEN 항목이 없습니다."
    exit 1
fi

# ---------- 2) Python 찾기 ----------
PY=""
if command -v python3 >/dev/null 2>&1; then
    PY="python3"
elif command -v python >/dev/null 2>&1; then
    PY="python"
fi

if [ -z "${PY}" ]; then
    echo "[오류] Python을 찾을 수 없습니다."
    echo "       sudo apt install python3 python3-venv 로 설치해 주세요."
    exit 1
fi

${PY} -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"
if [ $? -ne 0 ]; then
    echo "[오류] Python 3.8 이상이 필요합니다. 최신 버전으로 설치해 주세요."
    exit 1
fi

# ---------- 3) 가상환경 준비 ----------
if [ ! -f "${VENV_DIR}/bin/python" ]; then
    echo "[1/3] 가상환경을 만드는 중입니다..."
    ${PY} -m venv "${VENV_DIR}"
    if [ $? -ne 0 ]; then
        echo "[오류] 가상환경 생성에 실패했습니다."
        exit 1
    fi
fi
VPY="${VENV_DIR}/bin/python"

# ---------- 4) 패키지 설치 (처음 한 번만) ----------
if [ "$1" = "--reinstall" ]; then
    rm -f "${VENV_DIR}/.deps_ok"
fi

if [ ! -f "${VENV_DIR}/.deps_ok" ]; then
    echo "[2/3] 필요한 패키지를 설치하는 중입니다..."
    "${VPY}" -m pip install --upgrade pip >/dev/null 2>&1
    "${VPY}" -m pip install "discord.py==2.7.1" python-dotenv
    if [ $? -ne 0 ]; then
        echo "[오류] 패키지 설치에 실패했습니다. 인터넷 연결을 확인하세요."
        exit 1
    fi
    echo "ok" > "${VENV_DIR}/.deps_ok"
fi

# ---------- 5) 봇 실행 (비정상 종료 시 자동 재시작) ----------
RESTARTS=0

while true; do
    echo
    echo "[3/3] 봇을 시작합니다. 종료하려면 Ctrl+C 를 누르세요."
    echo "--------------------------------------------"

    START_T=${SECONDS}
    "${VPY}" main.py
    EXITCODE=$?
    END_T=${SECONDS}

    if [ ${EXITCODE} -eq 0 ]; then
        echo
        echo "봇이 정상적으로 종료되었습니다."
        exit 0
    fi

    # 1분(60초) 이상 정상 동작했다면 연속 실패 횟수 초기화
    UPTIME=$((END_T - START_T))
    if [ ${UPTIME} -ge 60 ]; then
        RESTARTS=0
    fi

    RESTARTS=$((RESTARTS + 1))
    echo
    echo "[경고] 봇이 비정상 종료되었습니다. 종료 코드: ${EXITCODE}"

    if [ ${RESTARTS} -ge ${MAX_RESTARTS} ]; then
        echo "[오류] 연속 ${MAX_RESTARTS}회 실패하여 자동 재시작을 중단합니다."
        echo "       위쪽 오류 메시지를 확인하세요. 토큰 오류나 인텐트 설정 문제일 수 있습니다."
        exit 1
    fi

    echo "${RESTART_DELAY}초 후 자동으로 다시 시작합니다. 시도 ${RESTARTS}/${MAX_RESTARTS}"
    sleep ${RESTART_DELAY}
done