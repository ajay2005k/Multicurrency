#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
npm ci --prefix frontend
npm run build --prefix frontend
# Artifacts target Lambda's platform, rather than the laptop running this script.
.venv/bin/python -m pip install --upgrade --target .build/lambda -r backend/requirements.lock.txt --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --only-binary=:all: --no-compile
.venv/bin/python scripts/package-cloudshell.py
