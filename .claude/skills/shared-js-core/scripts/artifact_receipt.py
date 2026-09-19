#!/usr/bin/env python3
"""Create and verify deterministic planner/executor review artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath

from external_skill_lib import ExternalSkillError, SHA256_RE, canonical_json_bytes, sha256_bytes


PLAN_REQUIRED = {
    "schema_version",
    "objective",
    "framework",
    "scope",
    "assumptions",
    "steps",
    "validation",
    "rollback",
    "out_of_scope",
    "critic",
}
ACCEPTED_VERDICTS = {"ACCEPT", "ACCEPT-WITH-RESERVATIONS"}
VERDICT_RE = re.compile(
    r"^VERDICT:\s*(REJECT|REVISE|ACCEPT-WITH-RESERVATIONS|ACCEPT)\s*$",
    re.MULTILINE,
)


def read_json(path: str) -> dict:
    try:
        if path == "-":
            return json.load(sys.stdin)
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExternalSkillError("INVALID_ARTIFACT", f"Unable to read JSON artifact: {exc}") from exc


def read_text(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ExternalSkillError("INVALID_REVIEW", f"Unable to read critic output: {exc}") from exc


def validate_digest(name: str, value: str) -> None:
    if not SHA256_RE.fullmatch(value):
        raise ExternalSkillError("INVALID_DIGEST", f"{name} must be a lowercase SHA-256 digest")


def plan_digest(plan: dict) -> str:
    missing = sorted(PLAN_REQUIRED - set(plan))
    if missing:
        raise ExternalSkillError("INVALID_PLAN", f"Missing plan fields: {', '.join(missing)}")
    if plan["schema_version"] != 1:
        raise ExternalSkillError("INVALID_PLAN", "Unsupported plan schema_version")
    if plan["framework"] not in {"react", "next", "react-native"}:
        raise ExternalSkillError("INVALID_PLAN", "framework must be react, next, or react-native")
    expected_critic = {
        "react": "react-critic",
        "next": "next-critic",
        "react-native": "react-native-critic",
    }[plan["framework"]]
    if plan["critic"] != expected_critic:
        raise ExternalSkillError(
            "CRITIC_MISMATCH",
            f"Expected {expected_critic} for framework {plan['framework']}",
        )
    payload = {key: value for key, value in plan.items() if key != "plan_sha256"}
    return sha256_bytes(canonical_json_bytes(payload))


def safe_scope_path(value: str) -> str:
    parsed = PurePosixPath(value)
    if parsed.is_absolute() or any(part in {"", ".", ".."} for part in parsed.parts):
        raise ExternalSkillError("INVALID_SCOPE", f"Unsafe scope path: {value!r}")
    return str(parsed)


def git_output(root: Path, *args: str) -> bytes:
    process = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.returncode:
        raise ExternalSkillError(
            "GIT_ERROR",
            process.stderr.decode("utf-8", errors="replace").strip() or "git command failed",
        )
    return process.stdout


def base_records(root: Path, base_commit: str, paths: list[str]) -> dict[str, dict]:
    output = git_output(root, "ls-tree", "-r", "-z", base_commit, "--", *paths)
    records: dict[str, dict] = {}
    for raw in output.split(b"\0"):
        if not raw:
            continue
        metadata, raw_path = raw.split(b"\t", 1)
        mode, object_type, object_id = metadata.decode("ascii").split()
        if object_type != "blob":
            continue
        path = raw_path.decode("utf-8")
        records[path] = {"mode": mode, "git_blob": object_id}
    return records


def within_scope(path: str, scopes: list[str]) -> bool:
    return any(path == scope or path.startswith(f"{scope}/") for scope in scopes)


def current_paths(root: Path, scopes: list[str]) -> set[str]:
    paths: set[str] = set()
    for scope in scopes:
        target = root / scope
        if target.is_symlink() or target.is_file():
            paths.add(scope)
        elif target.is_dir():
            for candidate in target.rglob("*"):
                if candidate.is_file() or candidate.is_symlink():
                    paths.add(candidate.relative_to(root).as_posix())
    return paths


def scope_fingerprint(root: Path, base_commit: str, paths: list[str]) -> dict:
    root = root.resolve()
    scopes = sorted({safe_scope_path(path) for path in paths})
    if not scopes:
        raise ExternalSkillError("INVALID_SCOPE", "At least one scope path is required")
    resolved_base = git_output(root, "rev-parse", "--verify", f"{base_commit}^{{commit}}").decode().strip()
    before = base_records(root, resolved_base, scopes)
    now = current_paths(root, scopes)
    records: list[dict] = []
    for relative in sorted(set(before) | now, key=lambda item: item.encode("utf-8")):
        if not within_scope(relative, scopes):
            continue
        target = root / relative
        record: dict = {"path": relative, "base": before.get(relative)}
        if relative not in now:
            record["current"] = None
        elif target.is_symlink():
            link = os.readlink(target)
            record["current"] = {
                "mode": "120000",
                "size": len(link.encode("utf-8")),
                "sha256": sha256_bytes(link.encode("utf-8")),
            }
        else:
            data = target.read_bytes()
            mode = "100755" if target.stat().st_mode & stat.S_IXUSR else "100644"
            record["current"] = {"mode": mode, "size": len(data), "sha256": sha256_bytes(data)}
        records.append(record)
    payload = {"schema_version": 1, "base_commit": resolved_base, "scope": scopes, "files": records}
    return {**payload, "scope_sha256": sha256_bytes(canonical_json_bytes(payload))}


def create_review_receipt(
    review_text: str,
    artifact_digest: str,
    scope_digest: str,
    critic: str,
) -> dict:
    validate_digest("artifact_sha256", artifact_digest)
    validate_digest("scope_sha256", scope_digest)
    matches = VERDICT_RE.findall(review_text)
    if len(matches) != 1:
        raise ExternalSkillError("INVALID_REVIEW", "Critic output must contain exactly one VERDICT line")
    verdict = matches[0]
    if verdict not in ACCEPTED_VERDICTS:
        raise ExternalSkillError("REVIEW_REJECTED", f"Critic verdict is {verdict}")
    return {
        "schema_version": 1,
        "critic": critic,
        "verdict": verdict,
        "artifact_sha256": artifact_digest,
        "scope_sha256": scope_digest,
        "review_sha256": sha256_bytes(review_text.encode("utf-8")),
    }


def verify_receipt(
    receipt: dict,
    artifact_digest: str,
    scope_digest: str,
    review_digest: str,
    critic: str,
) -> None:
    validate_digest("artifact_sha256", artifact_digest)
    validate_digest("scope_sha256", scope_digest)
    validate_digest("review_sha256", review_digest)
    required = {
        "schema_version", "critic", "verdict", "artifact_sha256", "scope_sha256", "review_sha256",
    }
    missing = sorted(required - set(receipt))
    if missing:
        raise ExternalSkillError("INVALID_RECEIPT", f"Missing receipt fields: {', '.join(missing)}")
    if receipt["schema_version"] != 1:
        raise ExternalSkillError("INVALID_RECEIPT", "Unsupported receipt schema_version")
    if receipt["critic"] != critic:
        raise ExternalSkillError("CRITIC_MISMATCH", f"Receipt critic is {receipt['critic']}, expected {critic}")
    if receipt["verdict"] not in ACCEPTED_VERDICTS:
        raise ExternalSkillError("REVIEW_REJECTED", f"Receipt verdict is {receipt['verdict']}")
    if receipt["artifact_sha256"] != artifact_digest:
        raise ExternalSkillError("ARTIFACT_CHANGED", "Receipt does not match the artifact digest")
    if receipt["scope_sha256"] != scope_digest:
        raise ExternalSkillError("SCOPE_CHANGED", "Receipt does not match the working-tree scope")
    if receipt["review_sha256"] != review_digest:
        raise ExternalSkillError("REVIEW_CHANGED", "Receipt does not match the critic output")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan_parser = subparsers.add_parser("plan-digest")
    plan_parser.add_argument("--input", default="-")
    scope_parser = subparsers.add_parser("scope-fingerprint")
    scope_parser.add_argument("--root", default=".")
    scope_parser.add_argument("--base-commit", required=True)
    scope_parser.add_argument("--paths", nargs="+", required=True)
    receipt_parser = subparsers.add_parser("verify-receipt")
    receipt_parser.add_argument("--receipt", required=True)
    receipt_parser.add_argument("--artifact-sha256", required=True)
    receipt_parser.add_argument("--scope-sha256", required=True)
    receipt_parser.add_argument("--review-output", required=True)
    receipt_parser.add_argument("--critic", required=True)
    create_parser = subparsers.add_parser("create-receipt")
    create_parser.add_argument("--review-output", required=True)
    create_parser.add_argument("--artifact-sha256", required=True)
    create_parser.add_argument("--scope-sha256", required=True)
    create_parser.add_argument("--critic", required=True)
    args = parser.parse_args()
    try:
        if args.command == "plan-digest":
            artifact = read_json(args.input)
            print(json.dumps({"plan_sha256": plan_digest(artifact)}))
        elif args.command == "scope-fingerprint":
            print(json.dumps(scope_fingerprint(Path(args.root), args.base_commit, args.paths), indent=2))
        elif args.command == "verify-receipt":
            review_text = read_text(args.review_output)
            verify_receipt(
                read_json(args.receipt),
                args.artifact_sha256,
                args.scope_sha256,
                sha256_bytes(review_text.encode("utf-8")),
                args.critic,
            )
            print(json.dumps({"ok": True}))
        else:
            review_text = read_text(args.review_output)
            print(json.dumps(create_review_receipt(
                review_text,
                args.artifact_sha256,
                args.scope_sha256,
                args.critic,
            ), indent=2))
        return 0
    except ExternalSkillError as exc:
        print(json.dumps({"ok": False, "code": exc.code, "error": str(exc)}), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
