#!/usr/bin/env python3
"""Refresh explicit v2 external-skill pins and instruction-bundle hashes."""

from __future__ import annotations

import argparse
import copy
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parent.parent
SHARED_SCRIPTS = ROOT / ".claude/skills/shared-js-core/scripts"
sys.path.insert(0, str(SHARED_SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from external_skill_lib import (  # noqa: E402
    ExternalSkillError,
    bundle_digest,
    collect_bundle,
    current_head,
    github_tree,
    load_json,
    warning_hash,
    write_json,
    write_text_atomic,
)
from skill_security import scan_content  # noqa: E402


LOCK = ROOT / ".claude/skills/shared-js-core/references/external-skills-lock.json"
REPORT = ROOT / "research/javascript-skills/reports/external-skills-refresh-report.md"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_exceptions(values: list[str]) -> set[tuple[str, str]]:
    parsed: set[tuple[str, str]] = set()
    for value in values:
        try:
            skill_id, finding_hash = value.rsplit(":", 1)
        except ValueError as exc:
            raise SystemExit(f"Invalid --allow-scan-warning value: {value}") from exc
        parsed.add((skill_id, finding_hash))
    return parsed


def target_ids(lock: dict, requested: list[str] | None, all_entries: bool) -> list[str]:
    available = lock.get("skills", {})
    if requested:
        missing = sorted(set(requested) - set(available))
        if missing:
            raise SystemExit(f"Unknown skill IDs: {', '.join(missing)}")
        return sorted(set(requested))
    if all_entries:
        return sorted(available)
    return sorted(skill_id for skill_id, entry in available.items() if entry.get("lifecycle") == "active")


def discover_heads(lock: dict, ids: list[str]) -> dict[str, str]:
    heads: dict[str, str] = {}
    for skill_id in ids:
        entry = lock["skills"][skill_id]
        if entry.get("lifecycle") != "active":
            continue
        repo_url = entry["repo_url"]
        if repo_url not in heads:
            heads[repo_url] = current_head(repo_url)
    return heads


def refresh_entry(
    entry: dict,
    head: str | None,
    allowed: set[tuple[str, str]],
    tree: list[dict],
) -> tuple[dict, list[dict]]:
    candidate = copy.deepcopy(entry)
    if candidate.get("lifecycle") == "active":
        candidate["pinned_commit"] = head
    if not candidate.get("pinned_commit"):
        raise ExternalSkillError("MISSING_PIN", f"No pin available for {candidate['id']}")

    records, texts = collect_bundle(candidate, tree=tree)
    source_name = PurePosixPath(candidate["source_path"]).name
    entry_record = next(record for record in records if record["path"] == source_name)
    findings: list[dict] = []
    for relative_path, content in sorted(texts.items()):
        for warning in scan_content(content, f"{candidate['id']}:{relative_path}"):
            finding_hash = warning_hash(candidate["id"], warning)
            accepted = (candidate["id"], finding_hash) in allowed
            findings.append({"hash": finding_hash, "warning": warning, "accepted": accepted})
            if not accepted:
                raise ExternalSkillError(
                    "SCAN_WARNING",
                    f"{candidate['id']} scan warning {finding_hash}: {warning}",
                )
    candidate["files"] = records
    candidate["entry_sha256"] = entry_record["sha256"]
    candidate["bundle_sha256"] = bundle_digest(records)
    candidate["scan_exceptions"] = [
        {"finding_hash": finding["hash"], "warning": finding["warning"]}
        for finding in findings if finding["accepted"]
    ]
    return candidate, findings


def write_report(changes: list[dict], findings: list[dict]) -> None:
    lines = [
        "# External Skill Refresh Report",
        "",
        f"Generated: {now_iso()}",
        f"Updated entries: {len(changes)}",
        "",
        "| Skill | Lifecycle | Old pin | New pin | Files | Bundle |",
        "|---|---|---|---|---:|---|",
    ]
    for change in changes:
        lines.append(
            f"| `{change['id']}` | {change['lifecycle']} | `{change['old'] or '-'}` | "
            f"`{change['new']}` | {change['files']} | `{change['bundle']}` |"
        )
    if findings:
        lines.extend(["", "## Approved Scan Exceptions", ""])
        for finding in findings:
            if finding["accepted"]:
                lines.append(f"- `{finding['id']}:{finding['hash']}` — {finding['warning']}")
    write_text_atomic(REPORT, "\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Exit 1 when an active upstream HEAD moved; never write.")
    parser.add_argument("--approve", action="store_true", help="Write an all-or-nothing verified refresh transaction.")
    parser.add_argument("--all", action="store_true", help="Include deprecated tombstones as well as active entries.")
    parser.add_argument("--ids", nargs="+", help="Refresh only these exact IDs as one transaction.")
    parser.add_argument(
        "--allow-scan-warning",
        action="append",
        default=[],
        metavar="ID:FINDING_HASH",
        help="Human-approved, exact scan exception; recorded in the lock and report.",
    )
    args = parser.parse_args()
    if args.check and args.approve:
        parser.error("--check and --approve are mutually exclusive")
    if args.approve and not (args.ids or args.all):
        parser.error("--approve requires an explicit --ids transaction or --all")

    lock = load_json(LOCK)
    ids = target_ids(lock, args.ids, args.all)
    try:
        heads = discover_heads(lock, ids)
    except ExternalSkillError as exc:
        print(f"ERROR [{exc.code}]: {exc}", file=sys.stderr)
        return 2

    stale = []
    for skill_id in ids:
        entry = lock["skills"][skill_id]
        if entry.get("lifecycle") != "active":
            continue
        latest = heads[entry["repo_url"]]
        if latest != entry.get("pinned_commit"):
            stale.append((skill_id, entry.get("pinned_commit", ""), latest))

    if args.check:
        for skill_id, old, new in stale:
            print(f"STALE {skill_id}: {old or '-'} -> {new}")
        print(f"Checked {len(ids)} entries; {len(stale)} active pins moved.")
        return 1 if stale else 0

    if not args.approve:
        for skill_id, old, new in stale:
            print(f"WOULD_UPDATE {skill_id}: {old or '-'} -> {new}")
        print("Dry run only. Use --approve with --ids or --all after reviewing the transaction.")
        return 0

    allowed = parse_exceptions(args.allow_scan_warning)
    updated = copy.deepcopy(lock)
    changes: list[dict] = []
    all_findings: list[dict] = []
    try:
        tree_cache: dict[tuple[str, str], list[dict]] = {}
        for skill_id in ids:
            original = lock["skills"][skill_id]
            head = heads.get(original["repo_url"])
            candidate_for_tree = copy.deepcopy(original)
            if candidate_for_tree.get("lifecycle") == "active":
                candidate_for_tree["pinned_commit"] = head
            tree_key = (candidate_for_tree["repo_url"], candidate_for_tree["pinned_commit"])
            if tree_key not in tree_cache:
                tree_cache[tree_key] = github_tree(candidate_for_tree)
            candidate, findings = refresh_entry(
                original,
                head,
                allowed,
                tree_cache[tree_key],
            )
            updated["skills"][skill_id] = candidate
            changes.append({
                "id": skill_id,
                "lifecycle": candidate["lifecycle"],
                "old": original.get("pinned_commit", ""),
                "new": candidate["pinned_commit"],
                "files": len(candidate["files"]),
                "bundle": candidate["bundle_sha256"],
            })
            for finding in findings:
                all_findings.append({"id": skill_id, **finding})
    except ExternalSkillError as exc:
        print(f"ERROR [{exc.code}]: {exc}", file=sys.stderr)
        print("No lock or report files were written.", file=sys.stderr)
        return 2

    accepted_pairs = {
        (finding["id"], finding["hash"])
        for finding in all_findings if finding["accepted"]
    }
    unused_exceptions = sorted(allowed - accepted_pairs)
    if unused_exceptions:
        print(
            "ERROR [UNUSED_SCAN_EXCEPTION]: "
            + ", ".join(f"{skill_id}:{finding_hash}" for skill_id, finding_hash in unused_exceptions),
            file=sys.stderr,
        )
        print("No lock or report files were written.", file=sys.stderr)
        return 2

    updated["generated_at"] = now_iso()
    write_json(LOCK, updated)
    write_report(changes, all_findings)
    print(f"Updated {len(changes)} entries in one verified transaction.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
