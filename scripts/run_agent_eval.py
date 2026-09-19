#!/usr/bin/env python3
"""Run bounded, real Claude CLI evaluations for planner/executor agents."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "research/agent-evals/cases"
SHARED = ROOT / ".claude/skills/shared-js-core/scripts"
sys.path.insert(0, str(SHARED))

from artifact_receipt import create_review_receipt, plan_digest, scope_fingerprint  # noqa: E402


RESULT_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "status": {"enum": ["completed", "refused", "blocked"]},
        "framework": {"enum": ["react", "next", "react-native", "unknown"]},
        "critic": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["status", "framework", "critic", "reason"],
    "additionalProperties": False,
})


def run_git(workspace: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=workspace, text=True).strip()


def initialize_workspace(case: dict, workspace: Path) -> dict[str, bytes | None]:
    for relative, content in case.get("files", {}).items():
        path = workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
    subprocess.run(["git", "config", "user.email", "eval@example.com"], cwd=workspace, check=True)
    subprocess.run(["git", "config", "user.name", "Agent Eval"], cwd=workspace, check=True)
    subprocess.run(["git", "add", "."], cwd=workspace, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=workspace, check=True)

    if case.get("gate") in {"accepted", "stale"}:
        contract = {
            "schema_version": 1,
            "objective": case["objective"],
            "framework": case["framework"],
            "scope": case["scope"],
            "assumptions": [],
            "steps": case["steps"],
            "validation": case["validation"],
            "rollback": "Revert only the scoped fixture change.",
            "out_of_scope": ["Commit, push, deploy"],
            "critic": case["critic"],
        }
        digest = plan_digest(contract)
        contract["plan_sha256"] = digest
        scope = scope_fingerprint(workspace, run_git(workspace, "rev-parse", "HEAD"), case["scope"])
        review = "VERDICT: ACCEPT\n\nOverall Assessment\nAccepted for this bounded fixture.\n"
        receipt = create_review_receipt(review, digest, scope["scope_sha256"], case["critic"])
        (workspace / "plan.json").write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
        (workspace / "scope.json").write_text(json.dumps(scope, indent=2) + "\n", encoding="utf-8")
        (workspace / "review.txt").write_text(review, encoding="utf-8")
        (workspace / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        if case["gate"] == "stale":
            stale_path = workspace / case["scope"][0]
            if stale_path.is_dir():
                stale_path = stale_path / "stale.txt"
            stale_path.parent.mkdir(parents=True, exist_ok=True)
            stale_path.write_text("scope changed after review\n", encoding="utf-8")

    return {
        item["path"]: (workspace / item["path"]).read_bytes()
        if (workspace / item["path"]).exists() else None
        for item in case.get("assert_files", [])
    }


def structured_result(stdout: str) -> dict:
    outer = json.loads(stdout)
    value = outer.get("structured_output")
    if isinstance(value, dict):
        return value
    result = outer.get("result")
    if isinstance(result, str):
        return json.loads(result)
    raise ValueError("Claude output did not contain structured JSON")


def evaluate_case(case: dict, max_budget: float, timeout: int) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix=f"react-agent-eval-{case['id']}-") as directory:
        workspace = Path(directory)
        before = initialize_workspace(case, workspace)
        prompt = case["prompt"].format(workspace=workspace)
        command = [
            "claude", "-p", "--agent", case["agent"],
            "--add-dir", str(workspace),
            "--permission-mode", "acceptEdits" if case["agent"] == "react-executor" else "plan",
            "--permission-prompts", "none",
            "--no-session-persistence",
            "--max-budget-usd", str(max_budget),
            "--json-schema", RESULT_SCHEMA,
            "--output-format", "json",
            prompt,
        ]
        process = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        if process.returncode:
            return False, f"Claude exited {process.returncode}: {process.stderr.strip()}"
        try:
            result = structured_result(process.stdout)
        except (json.JSONDecodeError, ValueError) as exc:
            return False, f"Invalid structured result: {exc}"
        for key, expected in case["expect"].items():
            if result.get(key) != expected:
                return False, f"Expected {key}={expected!r}, got {result.get(key)!r}"
        for assertion in case.get("assert_files", []):
            path = workspace / assertion["path"]
            current = path.read_bytes() if path.exists() else None
            changed = current != before[assertion["path"]]
            if changed != assertion["changed"]:
                return False, f"Unexpected mutation state for {assertion['path']}"
            if assertion.get("contains") and (
                current is None or assertion["contains"] not in current.decode("utf-8")
            ):
                return False, f"Missing expected content in {assertion['path']}"
        return True, result["reason"]


def load_cases(ids: list[str] | None) -> list[dict]:
    cases = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in sorted(CASES.glob("*.yaml"))]
    if ids:
        selected = [case for case in cases if case["id"] in ids]
        missing = sorted(set(ids) - {case["id"] for case in selected})
        if missing:
            raise SystemExit(f"Unknown eval cases: {', '.join(missing)}")
        return selected
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Required opt-in: invoke the paid Claude CLI.")
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--max-budget-usd", type=float, default=0.50, help="Per-case ceiling.")
    parser.add_argument("--timeout", type=int, default=300, help="Per-case seconds.")
    args = parser.parse_args()
    cases = load_cases(args.ids)
    if not args.run:
        print(f"Loaded {len(cases)} real-agent cases. Re-run with --run to spend up to "
              f"${args.max_budget_usd:.2f} per case.")
        return 0
    if not shutil.which("claude"):
        print("Claude CLI is not installed.", file=sys.stderr)
        return 2
    failures = 0
    for case in cases:
        try:
            passed, detail = evaluate_case(case, args.max_budget_usd, args.timeout)
        except subprocess.TimeoutExpired:
            passed, detail = False, f"timed out after {args.timeout}s"
        print(f"{'PASS' if passed else 'FAIL'} {case['id']}: {detail}", flush=True)
        failures += not passed
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
