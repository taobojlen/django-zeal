#!/usr/bin/env bash
# Autoresearch runner for django-zeal performance optimization
# Runs: unit tests (correctness gate) → performance benchmark
# Outputs METRIC lines for the agent to parse
# Exit code 0 = all good, non-zero = broken
set -euo pipefail

cd "$(dirname "$0")/.."

# ── Step 1: Unit tests (correctness gate) ───────────────────────────
echo "=== Unit Tests ==="
if ! .venv/bin/pytest tests/ -x -q --tb=short 2>&1; then
  echo "FATAL: unit tests failed"
  exit 1
fi

# ── Step 2: Performance benchmark ───────────────────────────────────
echo ""
echo "=== Performance Benchmark ==="
.venv/bin/python auto/bench.py 15 5 2>&1
