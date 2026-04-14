#!/usr/bin/env bash
set -euo pipefail

run_as_root() {
  if [[ "${DEPLOY_USE_SUDO:-false}" == "true" ]]; then
    sudo "$@"
  else
    "$@"
  fi
}

DEPLOY_BASE_DIR="${DEPLOY_BASE_DIR:-/opt}"
DEPLOY_APP_NAME="${DEPLOY_APP_NAME:-research-report-agent}"
DEPLOY_PATH="${DEPLOY_PATH:-${DEPLOY_BASE_DIR%/}/${DEPLOY_APP_NAME}}"
RELEASE_ID="${CI_COMMIT_SHORT_SHA:-$(date +%Y%m%d%H%M%S)}"
RELEASES_DIR="${DEPLOY_PATH}/releases"
SHARED_DIR="${DEPLOY_PATH}/shared"
RELEASE_DIR="${RELEASES_DIR}/${RELEASE_ID}"
CURRENT_LINK="${DEPLOY_PATH}/current"

echo "Deploy path: ${DEPLOY_PATH}"
echo "Release id: ${RELEASE_ID}"

run_as_root mkdir -p "${RELEASE_DIR}" "${SHARED_DIR}"
run_as_root mkdir -p "${SHARED_DIR}/outputs" "${SHARED_DIR}/logs" "${SHARED_DIR}/memory"

archive_path="$(mktemp "/tmp/${DEPLOY_APP_NAME}-release.XXXXXX.tar.gz")"
tar \
  --exclude-vcs \
  --exclude=".venv" \
  --exclude="__pycache__" \
  --exclude="*.pyc" \
  --exclude=".cache" \
  --exclude="dist" \
  --exclude="logs/*" \
  --exclude="outputs/*" \
  -czf "${archive_path}" .

run_as_root tar -xzf "${archive_path}" -C "${RELEASE_DIR}"
rm -f "${archive_path}"

run_as_root rm -rf "${RELEASE_DIR}/outputs" "${RELEASE_DIR}/logs" "${RELEASE_DIR}/memory"
run_as_root ln -sfn "${SHARED_DIR}/outputs" "${RELEASE_DIR}/outputs"
run_as_root ln -sfn "${SHARED_DIR}/logs" "${RELEASE_DIR}/logs"
run_as_root ln -sfn "${SHARED_DIR}/memory" "${RELEASE_DIR}/memory"

if [[ -n "${DEPLOY_ENV_FILE:-}" ]]; then
  printf '%s\n' "${DEPLOY_ENV_FILE}" | run_as_root tee "${SHARED_DIR}/.env" >/dev/null
fi

if run_as_root test -f "${SHARED_DIR}/.env"; then
  run_as_root cp "${SHARED_DIR}/.env" "${RELEASE_DIR}/.env"
fi

if ! python3 -m venv "${RELEASE_DIR}/.venv"; then
  export PATH="$HOME/.local/bin:$PATH"
  if ! python3 -m pip --version >/dev/null 2>&1; then
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
    elif command -v wget >/dev/null 2>&1; then
      wget -qO /tmp/get-pip.py https://bootstrap.pypa.io/get-pip.py
    else
      echo "Neither curl nor wget is available to bootstrap pip." >&2
      exit 1
    fi
    python3 /tmp/get-pip.py --user
  fi
  python3 -m pip install --user --upgrade pip virtualenv
  python3 -m virtualenv "${RELEASE_DIR}/.venv"
fi
if ! "${RELEASE_DIR}/.venv/bin/python" -m pip --version >/dev/null 2>&1; then
  "${RELEASE_DIR}/.venv/bin/python" -m ensurepip --upgrade
fi
"${RELEASE_DIR}/.venv/bin/pip" install --upgrade pip
"${RELEASE_DIR}/.venv/bin/pip" install -r "${RELEASE_DIR}/requirements.txt"
if [[ -f "${RELEASE_DIR}/report_review_agent/requirements.txt" ]]; then
  "${RELEASE_DIR}/.venv/bin/pip" install -r "${RELEASE_DIR}/report_review_agent/requirements.txt"
fi

run_as_root ln -sfn "${RELEASE_DIR}" "${CURRENT_LINK}"

if [[ "${DEPLOY_WITH_DOCKER_COMPOSE:-true}" == "true" ]]; then
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    run_as_root bash -lc "cd '${CURRENT_LINK}' && docker compose up -d --build"
  elif command -v docker-compose >/dev/null 2>&1; then
    run_as_root bash -lc "cd '${CURRENT_LINK}' && docker-compose up -d --build"
  else
    echo "DEPLOY_WITH_DOCKER_COMPOSE=true but docker compose is unavailable." >&2
    exit 1
  fi
fi

if [[ -n "${SYSTEMD_SERVICE:-}" ]]; then
  if command -v systemctl >/dev/null 2>&1; then
    run_as_root systemctl restart "${SYSTEMD_SERVICE}"
  else
    echo "SYSTEMD_SERVICE is set but systemctl is unavailable." >&2
    exit 1
  fi
fi

echo "Deployment finished: ${CURRENT_LINK}"
