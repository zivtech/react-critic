#!/usr/bin/env python3
"""Create the explicit manifest-v2 catalog and immutable lineage skeleton."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
V1_MANIFESTS = sorted(ROOT.glob(".claude/skills/*/references/external-skills-manifest.yaml"))
LOCK = ROOT / ".claude/skills/shared-js-core/references/external-skills-lock.json"
REPORT = ROOT / "research/javascript-skills/reports/external-skills-v2-migration.md"


SOURCE_PATHS = {
    "callstack/react-native-testing-library/react-native-testing": "skills/react-native-testing/SKILL.md",
    "callstackincubator/agent-skills/react-native-best-practices": "skills/react-native-best-practices/SKILL.md",
    "callstackincubator/agent-skills/upgrading-react-native": "skills/upgrading-react-native/SKILL.md",
    "clerk/skills/clerk-nextjs-patterns": "skills/frameworks/clerk-nextjs-patterns/SKILL.md",
    "dotneet/claude-code-marketplace/typescript-react-reviewer": "review-tool/skills/typescript-react-reviewer/SKILL.md",
    "github/awesome-copilot/javascript-typescript-jest": "skills/javascript-typescript-jest/SKILL.md",
    "millionco/react-doctor/react-doctor": "skills/react-doctor/SKILL.md",
    "mindrally/skills/nextauth-authentication": "nextauth-authentication/SKILL.md",
    "react-native-community/skills/upgrade-react-native": "upgrade-react-native/SKILL.md",
    "sickn33/antigravity-awesome-skills/api-security-best-practices": "skills/api-security-best-practices/SKILL.md",
    "wshobson/agents/javascript-testing-patterns": "plugins/javascript-typescript/skills/javascript-testing-patterns/SKILL.md",
    "wshobson/agents/modern-javascript-patterns": "plugins/javascript-typescript/skills/modern-javascript-patterns/SKILL.md",
    "wshobson/agents/nextjs-app-router-patterns": "plugins/frontend-mobile-development/skills/nextjs-app-router-patterns/SKILL.md",
    "wshobson/agents/react-modernization": "plugins/framework-migration/skills/react-modernization/SKILL.md",
    "wshobson/agents/react-native-architecture": "plugins/frontend-mobile-development/skills/react-native-architecture/SKILL.md",
    "wshobson/agents/react-native-design": "plugins/ui-design/skills/react-native-design/SKILL.md",
    "wshobson/agents/react-state-management": "plugins/frontend-mobile-development/skills/react-state-management/SKILL.md",
    "wsimmonds/claude-nextjs-skills/nextjs-app-router-fundamentals": "nextjs-app-router-fundamentals/SKILL.md",
}

DEPRECATED_PATHS = {
    "auth0/agent-skills/auth0-nextjs": "plugins/auth0-sdks/skills/auth0-nextjs/SKILL.md",
    "auth0/agent-skills/auth0-react-native": "plugins/auth0-sdks/skills/auth0-react-native/SKILL.md",
    "expo/skills/building-native-ui": "plugins/expo-app-design/skills/building-native-ui/SKILL.md",
    "expo/skills/expo-api-routes": "plugins/expo-app-design/skills/expo-api-routes/SKILL.md",
    "expo/skills/expo-cicd-workflows": "plugins/expo-deployment/skills/expo-cicd-workflows/SKILL.md",
    "expo/skills/native-data-fetching": "plugins/expo-app-design/skills/native-data-fetching/SKILL.md",
    "expo/skills/upgrading-expo": "plugins/upgrading-expo/skills/upgrading-expo/SKILL.md",
    "expo/skills/use-dom": "plugins/expo-app-design/skills/use-dom/SKILL.md",
    "getsentry/sentry-agent-skills/sentry-react-native-setup": "skills/sentry-react-native-sdk/SKILL.md",
    "vercel-labs/agent-skills/vercel-react-best-practices": "skills/react-best-practices/SKILL.md",
    "vercel-labs/agent-skills/vercel-react-native-skills": "skills/react-native-skills/SKILL.md",
    "vercel-labs/next-skills/next-best-practices": "skills/next-best-practices/SKILL.md",
    "vercel-labs/next-skills/next-cache-components": "skills/next-cache-components/SKILL.md",
    "vercel-labs/next-skills/next-upgrade": "skills/next-upgrade/SKILL.md",
}

REPLACEMENTS = {
    "auth0/agent-skills/auth0-nextjs": ["auth0/agent-skills/auth0"],
    "auth0/agent-skills/auth0-react-native": ["auth0/agent-skills/auth0"],
    "expo/skills/building-native-ui": ["expo/skills/expo-native-ui"],
    "expo/skills/expo-cicd-workflows": ["expo/skills/eas-workflows"],
    "expo/skills/native-data-fetching": ["expo/skills/expo-data-fetching"],
    "expo/skills/upgrading-expo": ["expo/skills/expo-upgrade"],
    "expo/skills/use-dom": ["expo/skills/expo-dom"],
    "getsentry/sentry-agent-skills/sentry-react-native-setup": ["getsentry/sentry-agent-skills/sentry-react-native-sdk"],
    "vercel-labs/agent-skills/vercel-react-best-practices": ["vercel-labs/agent-skills/react-best-practices"],
    "vercel-labs/agent-skills/vercel-react-native-skills": ["vercel-labs/agent-skills/react-native-skills"],
}

NEW_ENTRIES = {
    "auth0/agent-skills/auth0": (
        "https://github.com/auth0/agent-skills", "plugins/auth0/skills/auth0/SKILL.md",
    ),
    "expo/skills/eas-workflows": (
        "https://github.com/expo/skills", "plugins/expo/skills/eas-workflows/SKILL.md",
    ),
    "expo/skills/expo-data-fetching": (
        "https://github.com/expo/skills", "plugins/expo/skills/expo-data-fetching/SKILL.md",
    ),
    "expo/skills/expo-dom": (
        "https://github.com/expo/skills", "plugins/expo/skills/expo-dom/SKILL.md",
    ),
    "expo/skills/expo-native-ui": (
        "https://github.com/expo/skills", "plugins/expo/skills/expo-native-ui/SKILL.md",
    ),
    "expo/skills/expo-router": (
        "https://github.com/expo/skills", "plugins/expo/skills/expo-router/SKILL.md",
    ),
    "expo/skills/expo-upgrade": (
        "https://github.com/expo/skills", "plugins/expo/skills/expo-upgrade/SKILL.md",
    ),
    "getsentry/sentry-agent-skills/sentry-react-native-sdk": (
        "https://github.com/getsentry/sentry-agent-skills", "skills/sentry-react-native-sdk/SKILL.md",
    ),
    "vercel-labs/agent-skills/composition-patterns": (
        "https://github.com/vercel-labs/agent-skills", "skills/composition-patterns/SKILL.md",
    ),
    "vercel-labs/agent-skills/react-best-practices": (
        "https://github.com/vercel-labs/agent-skills", "skills/react-best-practices/SKILL.md",
    ),
    "vercel-labs/agent-skills/react-native-skills": (
        "https://github.com/vercel-labs/agent-skills", "skills/react-native-skills/SKILL.md",
    ),
    "vercel/next.js/next-cache-components-optimizer": (
        "https://github.com/vercel/next.js", "skills/next-cache-components-optimizer/SKILL.md",
    ),
    "vercel/next.js/next-dev-loop": (
        "https://github.com/vercel/next.js", "skills/next-dev-loop/SKILL.md",
    ),
}


def replacement_id(skill_id: str) -> str | None:
    replacements = REPLACEMENTS.get(skill_id, [])
    return replacements[0] if replacements else None


def migrate_consumer(consumer: str, skills: list[dict]) -> list[dict]:
    migrated: list[dict] = []
    seen: set[str] = set()
    for item in skills:
        old_id = item["id"]
        new_id = replacement_id(old_id)
        if old_id.startswith("vercel-labs/next-skills/") or old_id == "expo/skills/expo-api-routes":
            continue
        if consumer == "proposal-critic" and old_id == "wshobson/agents/react-native-architecture":
            continue
        next_item = {key: value for key, value in item.items() if key not in {
            "repo_url", "skills_url", "pinned_commit", "content_sha256", "status",
        }}
        next_item["id"] = new_id or old_id
        next_item["enabled"] = True
        if next_item["id"] not in seen:
            migrated.append(next_item)
            seen.add(next_item["id"])

    additions: dict[str, list[tuple[str, list[str], int, str]]] = {
        "react-critic": [
            ("vercel-labs/agent-skills/composition-patterns", ["react", "architecture"], 96,
             "Load for component API design, compound components, and state/provider boundaries."),
        ],
        "next-critic": [
            ("vercel-labs/agent-skills/react-best-practices", ["core-review", "next", "performance"], 100,
             "Core React and Next.js performance guidance after retirement of next-skills."),
            ("vercel-labs/agent-skills/composition-patterns", ["next", "architecture"], 94,
             "Load for component API and server/client composition decisions."),
            ("vercel/next.js/next-dev-loop", ["next", "runtime-verification"], 92,
             "Executor-only: Next 16.3+, Turbopack, running next dev, and agent-browser >=0.31.1."),
            ("vercel/next.js/next-cache-components-optimizer", ["next", "cache-components"], 90,
             "Executor-only: Next 16.3+ Cache Components instant-navigation work."),
        ],
        "react-native-critic": [
            ("expo/skills/expo-router", ["expo", "routing"], 88,
             "Load for Expo Router navigation and route structure; not an API-routes replacement."),
        ],
        "proposal-critic": [
            ("vercel-labs/agent-skills/composition-patterns", ["core-review", "proposal", "architecture"], 96,
             "Core React and Next.js component architecture planning reference."),
        ],
    }
    for skill_id, categories, priority, jtbd in additions.get(consumer, []):
        if skill_id in seen:
            continue
        migrated.append({
            "id": skill_id,
            "categories": categories,
            "audiences_supported": ["executor", "stakeholder", "skeptic"] if consumer == "proposal-critic" else ["new-hire", "ops"],
            "priority": priority,
            "jtbd": jtbd,
            "enabled": True,
        })
        seen.add(skill_id)
    return migrated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Required acknowledgement: replace the v2 skeleton and consumer manifests.",
    )
    args = parser.parse_args()
    if not args.write:
        print("Dry run only. Re-run with --write to replace the migration skeleton.")
        return 0
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    old_entries: dict[str, dict] = {}
    consumer_data: dict[str, list[dict]] = {}
    for manifest in V1_MANIFESTS:
        data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        consumer = manifest.parents[1].name
        consumer_data[consumer] = data["skills"]
        for entry in data["skills"]:
            old_entries.setdefault(entry["id"], entry)

    lock_entries: dict[str, dict] = {}
    replaced_ids = set(REPLACEMENTS)
    retired_ids = {skill_id for skill_id in old_entries if skill_id.startswith("vercel-labs/next-skills/")}
    retired_ids.add("expo/skills/expo-api-routes")

    for skill_id, old in sorted(old_entries.items()):
        if skill_id in replaced_ids or skill_id in retired_ids:
            lock_entries[skill_id] = {
                "id": skill_id,
                "repo_url": old["repo_url"],
                "skills_url": old["skills_url"],
                "source_path": DEPRECATED_PATHS[skill_id],
                "pinned_commit": old["pinned_commit"],
                "lifecycle": "deprecated",
                "replaced_by": REPLACEMENTS.get(skill_id, []),
                "deprecation_reason": "Renamed or consolidated upstream." if skill_id in replaced_ids else "Upstream skill retired without a like-for-like successor.",
                "entry_sha256": "",
                "bundle_sha256": "",
                "files": [],
            }
            continue
        lock_entries[skill_id] = {
            "id": skill_id,
            "repo_url": old["repo_url"],
            "skills_url": old["skills_url"],
            "source_path": SOURCE_PATHS[skill_id],
            "pinned_commit": old["pinned_commit"],
            "lifecycle": "active",
            "supersedes": [],
            "entry_sha256": "",
            "bundle_sha256": "",
            "files": [],
        }

    predecessors: dict[str, list[str]] = {}
    for old_id, new_ids in REPLACEMENTS.items():
        for new_id in new_ids:
            predecessors.setdefault(new_id, []).append(old_id)

    for skill_id, (repo_url, source_path) in sorted(NEW_ENTRIES.items()):
        lock_entries[skill_id] = {
            "id": skill_id,
            "repo_url": repo_url,
            "skills_url": f"https://skills.sh/{skill_id}",
            "source_path": source_path,
            "pinned_commit": "",
            "lifecycle": "active",
            "supersedes": sorted(predecessors.get(skill_id, [])),
            "entry_sha256": "",
            "bundle_sha256": "",
            "files": [],
        }

    lock = {"version": 2, "generated_at": now, "skills": lock_entries}
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    LOCK.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")

    for consumer, skills in consumer_data.items():
        output = ROOT / f".claude/skills/{consumer}/references/external-skills-manifest.json"
        value = {
            "version": 2,
            "consumer": consumer,
            "generated_at": now,
            "skills": migrate_consumer(consumer, skills),
        }
        output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# External Skills v2 Migration",
        "",
        f"Generated: {now}",
        "",
        "| Old ID | Result |",
        "|---|---|",
    ]
    for old_id in sorted(replaced_ids | retired_ids):
        replacements = REPLACEMENTS.get(old_id)
        result = ", ".join(f"`{item}`" for item in replacements) if replacements else "Deprecated; no like-for-like replacement"
        lines.append(f"| `{old_id}` | {result} |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {LOCK.relative_to(ROOT)} and {len(consumer_data)} consumer manifests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
