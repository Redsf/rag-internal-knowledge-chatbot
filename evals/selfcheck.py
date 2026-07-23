#!/usr/bin/env python3
"""CI self-check for the eval suite.

Runs without API keys or a live deployment: it byte-compiles every module in
this directory and validates that the test-case file parses, has unique IDs,
and carries the fields the runner depends on. Catches a broken eval harness
before anyone discovers it mid-eval.
"""

from __future__ import annotations

import json
import py_compile
import sys
from collections import Counter
from pathlib import Path

EVAL_DIR = Path(__file__).parent
REQUIRED_FIELDS = ("id", "type")


def compile_modules() -> list[str]:
    errors = []
    for module in sorted(EVAL_DIR.glob("*.py")):
        try:
            py_compile.compile(str(module), doraise=True, cfile=None)
        except py_compile.PyCompileError as exc:
            errors.append(f"{module.name}: {exc}")
    return errors


def check_cases(path: Path) -> tuple[list[str], int]:
    errors: list[str] = []
    if not path.exists():
        return [f"{path.name} is missing"], 0

    cases = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            cases.append(json.loads(line))
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}:{lineno}: invalid JSON — {exc}")

    for case in cases:
        missing = [f for f in REQUIRED_FIELDS if f not in case]
        if missing:
            errors.append(f"case {case.get('id', '?')}: missing {', '.join(missing)}")

    duplicates = [cid for cid, n in Counter(c.get("id") for c in cases).items() if n > 1]
    for cid in duplicates:
        errors.append(f"duplicate case ID: {cid}")

    return errors, len(cases)


def main() -> int:
    errors = compile_modules()
    case_errors, count = check_cases(EVAL_DIR / "test_cases.jsonl")
    errors += case_errors

    for error in errors:
        print(f"ERROR {error}")

    if errors:
        print(f"\nEval self-check failed with {len(errors)} error(s).")
        return 1

    print(f"Eval self-check passed: {count} test case(s), all modules compile.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
