"""Week1 readiness test runner. Runs critical test blocks in order, prints PASS/FAIL per block."""

import subprocess
import sys

BLOCKS = [
    ("test_contract_shapes", ["pytest", "-q", "apps/api/tests/test_contract_shapes.py", "-ra"]),
    ("test_grounding", ["pytest", "-q", "apps/api/tests/test_grounding.py", "-ra"]),
    ("test_versioning", ["pytest", "-q", "apps/api/tests/test_versioning.py", "-ra"]),
    (
        "test_crawl_rules + quote_flow_exclusion",
        ["pytest", "-q", "tests/test_crawl_rules.py", "apps/api/tests/test_quote_flow_exclusion.py", "-ra"],
    ),
    ("test_auth_injects_tenant", ["pytest", "-q", "apps/api/tests/test_auth_injects_tenant.py", "-ra"]),
]


def main() -> int:
    any_fail = False
    for name, cmd in BLOCKS:
        result = subprocess.run(cmd)
        status = "PASS" if result.returncode == 0 else "FAIL"
        print(f"{status}: {name}")
        if result.returncode != 0:
            any_fail = True
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
