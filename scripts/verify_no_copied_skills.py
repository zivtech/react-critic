#!/usr/bin/env python3
"""Validate v1 compatibility and the authoritative v2 external-skill lock."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

import yaml


ROOT = Path(__file__).resolve().parent.parent
SHARED_SCRIPTS = ROOT / ".claude/skills/shared-js-core/scripts"
sys.path.insert(0, str(SHARED_SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from external_skill_lib import (  # noqa: E402
    ExternalSkillError,
    SHA_RE,
    load_json,
    resolve_locked_file,
    validate_file_records,
    validate_relative_path,
)
from skill_security import TRUSTED_OWNERS, scan_content  # noqa: E402


V1_MANIFESTS = sorted(ROOT.glob(".claude/skills/*/references/external-skills-manifest.yaml"))
V2_MANIFESTS = sorted(ROOT.glob(".claude/skills/*/references/external-skills-manifest.json"))
LOCK = ROOT / ".claude/skills/shared-js-core/references/external-skills-lock.json"
ID_RE = re.compile(r"^[^/]+/[^/]+/[^/]+$")


def fail(message: str) -> None:
    raise ExternalSkillError("VALIDATION", message)


def validate_v1() -> None:
    if not V1_MANIFESTS:
        fail("No v1 compatibility manifests found")
    for manifest in V1_MANIFESTS:
        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        if data.get("version") != 1 or not data.get("skills"):
            fail(f"Invalid v1 manifest: {manifest}")
        for entry in data["skills"]:
            if not ID_RE.fullmatch(str(entry.get("id", ""))):
                fail(f"Invalid v1 skill ID in {manifest}: {entry.get('id')}")
            if not SHA_RE.fullmatch(str(entry.get("pinned_commit", ""))):
                fail(f"Invalid v1 pin for {entry.get('id')}")


def validate_lock(lock: dict) -> None:
    if lock.get("version") != 2:
        fail("External skills lock must use version 2")
    skills = lock.get("skills")
    if not isinstance(skills, dict) or not skills:
        fail("External skills lock has no entries")

    active_sources: dict[tuple[str, str], str] = {}
    for skill_id, entry in skills.items():
        if skill_id != entry.get("id") or not ID_RE.fullmatch(skill_id):
            fail(f"Invalid or mismatched lock ID: {skill_id}")
        owner = skill_id.split("/", 1)[0]
        if owner not in TRUSTED_OWNERS:
            fail(f"Untrusted owner {owner!r} for {skill_id}")
        if not str(entry.get("repo_url", "")).startswith("https://github.com/"):
            fail(f"Invalid repo URL for {skill_id}")
        if not str(entry.get("skills_url", "")).startswith("https://skills.sh/"):
            fail(f"Invalid skills.sh URL for {skill_id}")
        validate_relative_path(str(entry.get("source_path", "")))
        if not SHA_RE.fullmatch(str(entry.get("pinned_commit", ""))):
            fail(f"Invalid pin for {skill_id}")
        lifecycle = entry.get("lifecycle")
        if lifecycle not in {"active", "deprecated"}:
            fail(f"Invalid lifecycle for {skill_id}: {lifecycle}")
        validate_file_records(entry)
        if lifecycle == "active":
            key = (entry["repo_url"], entry["source_path"])
            if key in active_sources:
                fail(f"Active source collision: {skill_id} and {active_sources[key]}")
            active_sources[key] = skill_id
            for old_id in entry.get("supersedes", []):
                old = skills.get(old_id)
                if not old or old.get("lifecycle") != "deprecated" or skill_id not in old.get("replaced_by", []):
                    fail(f"Broken supersession lineage: {old_id} -> {skill_id}")
        else:
            if not entry.get("deprecation_reason"):
                fail(f"Deprecated entry lacks reason: {skill_id}")
            for replacement in entry.get("replaced_by", []):
                if replacement not in skills or skills[replacement].get("lifecycle") != "active":
                    fail(f"Invalid replacement for {skill_id}: {replacement}")


def validate_consumers(lock: dict) -> None:
    if not V2_MANIFESTS:
        fail("No v2 consumer manifests found")
    seen_consumers: set[str] = set()
    for manifest_path in V2_MANIFESTS:
        manifest = load_json(manifest_path)
        consumer = manifest.get("consumer")
        if manifest.get("version") != 2 or not consumer or consumer in seen_consumers:
            fail(f"Invalid v2 consumer manifest: {manifest_path}")
        if consumer != manifest_path.parents[1].name:
            fail(f"Consumer name does not match its directory: {manifest_path}")
        seen_consumers.add(consumer)
        seen_ids: set[str] = set()
        for item in manifest.get("skills", []):
            skill_id = item.get("id")
            if skill_id in seen_ids:
                fail(f"Duplicate consumer skill {skill_id} in {consumer}")
            seen_ids.add(skill_id)
            entry = lock["skills"].get(skill_id)
            if not entry:
                fail(f"Consumer {consumer} references unlocked skill {skill_id}")
            if item.get("enabled", True) and entry.get("lifecycle") != "active":
                fail(f"Consumer {consumer} enables deprecated skill {skill_id}")
            if not isinstance(item.get("priority"), int):
                fail(f"Consumer {consumer} entry lacks integer priority: {skill_id}")


def verify_live(lock: dict) -> None:
    for skill_id, entry in lock["skills"].items():
        for record in entry["files"]:
            content = resolve_locked_file(entry, record["path"])
            warnings = scan_content(content, f"{skill_id}:{record['path']}")
            accepted = {item["finding_hash"] for item in entry.get("scan_exceptions", [])}
            unexpected = [warning for warning in warnings if _warning_hash(skill_id, warning) not in accepted]
            if unexpected:
                fail(f"Unapproved scan warning for {skill_id}:{record['path']}: {unexpected[0]}")
        print(f"OK {skill_id} ({len(entry['files'])} files)")


def _warning_hash(skill_id: str, warning: str) -> str:
    import hashlib

    return hashlib.sha256(f"{skill_id}\0{warning}".encode("utf-8")).hexdigest()[:16]


def validate_no_copies() -> None:
    tracked = subprocess.check_output(["git", "-C", str(ROOT), "ls-files"], text=True).splitlines()
    forbidden = ("research/javascript-skills/upstream/", "research/javascript-skills/extracted/")
    for path in tracked:
        if path.startswith(forbidden):
            fail(f"Forbidden copied-skill path: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-content", action="store_true", help="Fetch and verify every locked instruction file.")
    args = parser.parse_args()
    try:
        validate_v1()
        lock = load_json(LOCK)
        validate_lock(lock)
        validate_consumers(lock)
        validate_no_copies()
        if args.verify_content:
            verify_live(lock)
    except (ExternalSkillError, KeyError, TypeError, yaml.YAMLError) as exc:
        code = exc.code if isinstance(exc, ExternalSkillError) else "VALIDATION"
        print(f"ERROR [{code}]: {exc}", file=sys.stderr)
        return 1
    print(
        f"Validation passed: {len(V1_MANIFESTS)} v1 manifests, "
        f"{len(V2_MANIFESTS)} v2 consumers, {len(lock['skills'])} locked skills."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
