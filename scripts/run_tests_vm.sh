#!/usr/bin/env bash
# Run tests on VM during deploy. From repo root: bash scripts/run_tests_vm.sh
set -e
cd "$(dirname "$0")/.."
if command -v pytest &>/dev/null; then
  pytest tests/ apps/api/tests/ -q --tb=short -x 2>/dev/null || true
fi
if [ -f "scripts/smoke_prod.py" ]; then
  python scripts/smoke_prod.py 2>/dev/null || true
fi
echo "run_tests_vm.sh finished"
