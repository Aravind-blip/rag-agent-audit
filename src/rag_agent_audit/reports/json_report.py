"""JSON report — machine-readable output for downstream tooling."""

from __future__ import annotations

import json
from dataclasses import asdict

from rag_agent_audit.result import TestResult


def build_json_report(suite_name: str, results: list[TestResult]) -> str:
    total = len(results)
    passed = sum(1 for r in results if r.passed)

    payload = {
        "suite": suite_name,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
        },
        "tests": [asdict(r) for r in results],
    }
    return json.dumps(payload, indent=2)
