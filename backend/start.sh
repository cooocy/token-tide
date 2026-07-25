#!/usr/bin/env bash
set -euo pipefail

: "${CONFIGURATION_TAIL:?CONFIGURATION_TAIL must select application-{tail}.yaml}"

cd "$(dirname "$0")"

.venv/bin/alembic upgrade head
exec .venv/bin/token-tide
