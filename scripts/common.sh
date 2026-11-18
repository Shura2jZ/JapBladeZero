#!/usr/bin/env bash
# Common setup for the pipeline scripts: run from the repository root.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONIOENCODING=utf-8
mkdir -p logs
