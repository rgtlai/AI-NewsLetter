#!/usr/bin/env sh
set -e

if command -v uv >/dev/null 2>&1; then
  echo "[uv] Exporting requirements.txt from pyproject.toml"
  uv export --no-dev --format requirements-txt > requirements.txt
  echo "[uv] Wrote requirements.txt"
else
  echo "[uv] uv not found; skipping export. Using existing requirements.txt"
fi


