#!/usr/bin/env bash

set -Eeuo pipefail
umask 027

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/opt/python/3.13.0/bin/python3}"
VENV_DIR="${PROJECT_ROOT}/.venv"
RUN_DIR="${PROJECT_ROOT}/run"
LOG_DIR="${PROJECT_ROOT}/logs"
PID_FILE="${RUN_DIR}/token-tide.pid"
APP_LOG="${LOG_DIR}/app.log"
INSTALL_LOG="${LOG_DIR}/install.log"
ALEMBIC_LOG="${LOG_DIR}/alembic.log"

: "${CONFIGURATION_TAIL:?CONFIGURATION_TAIL must select application-{tail}.yaml}"

cd "${PROJECT_ROOT}"
mkdir -p "${RUN_DIR}" "${LOG_DIR}"
touch "${APP_LOG}" "${INSTALL_LOG}" "${ALEMBIC_LOG}"

stop_running_process() {
    if [[ ! -f "${PID_FILE}" ]]; then
        return
    fi

    local pid
    pid="$(<"${PID_FILE}")"
    if [[ ! "${pid}" =~ ^[0-9]+$ ]]; then
        echo "Invalid PID file, removing: ${PID_FILE}"
        rm -f "${PID_FILE}"
        return
    fi

    if ! kill -0 "${pid}" 2>/dev/null; then
        echo "Removing stale PID file: ${PID_FILE}"
        rm -f "${PID_FILE}"
        return
    fi

    local command_line
    command_line="$(ps -p "${pid}" -o command= 2>/dev/null || true)"
    if [[ "${command_line}" != *"${VENV_DIR}/bin/token-tide"* ]]; then
        echo "PID ${pid} does not belong to token-tide; refusing to kill it"
        rm -f "${PID_FILE}"
        return
    fi

    echo "Stopping token-tide, PID: ${pid}"
    kill "${pid}"
    for _ in {1..30}; do
        if ! kill -0 "${pid}" 2>/dev/null; then
            rm -f "${PID_FILE}"
            echo "token-tide stopped"
            return
        fi
        sleep 1
    done

    echo "Graceful shutdown timed out, killing PID: ${pid}"
    kill -9 "${pid}"
    rm -f "${PID_FILE}"
}

if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "Python 3.13 executable not found: ${PYTHON_BIN}" >&2
    echo "Set PYTHON_BIN to the Python 3.13+ executable path." >&2
    exit 1
fi

stop_running_process

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    echo "Creating virtual environment: ${VENV_DIR}"
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

python_version="$("${VENV_DIR}/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
python_major="${python_version%%.*}"
python_minor="${python_version#*.}"
if [[ "${python_major}" != "3" ]] || (( python_minor < 13 )); then
    echo "Virtual environment must use Python 3.13+, found: ${python_version}" >&2
    exit 1
fi

echo "Installing token-tide"
if ! "${VENV_DIR}/bin/python" -m pip install --upgrade "${PROJECT_ROOT}" >>"${INSTALL_LOG}" 2>&1; then
    echo "Installation failed, check: ${INSTALL_LOG}" >&2
    exit 1
fi

echo "Applying database migrations"
if ! "${VENV_DIR}/bin/alembic" -c "${PROJECT_ROOT}/alembic.ini" upgrade head >>"${ALEMBIC_LOG}" 2>&1; then
    echo "Database migration failed, check: ${ALEMBIC_LOG}" >&2
    exit 1
fi

token_tide_commit="$(git rev-parse --short HEAD 2>/dev/null || true)"
if [[ -z "${token_tide_commit}" ]]; then
    token_tide_commit="unknown"
fi

echo "Starting token-tide, commit: ${token_tide_commit}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] starting token-tide commit=${token_tide_commit}" >>"${APP_LOG}"
nohup "${VENV_DIR}/bin/token-tide" >>"${APP_LOG}" 2>&1 &
new_pid=$!
echo "${new_pid}" >"${PID_FILE}"

sleep 2
if ! kill -0 "${new_pid}" 2>/dev/null; then
    rm -f "${PID_FILE}"
    echo "token-tide failed to start, check: ${APP_LOG}" >&2
    exit 1
fi

echo "token-tide started, PID: ${new_pid}"
echo "Application log: ${APP_LOG}"
echo "Install log: ${INSTALL_LOG}"
echo "Alembic log: ${ALEMBIC_LOG}"
