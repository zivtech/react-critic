#!/usr/bin/env python3
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MANIFESTS = sorted(ROOT.glob('.claude/skills/*/references/external-skills-manifest.yaml'))

ID_RE = re.compile(r'^[^/]+/[^/]+/[^/]+$')
SHA_RE = re.compile(r'^[0-9a-f]{40}$')


def fail(msg: str) -> None:
    print(f'ERROR: {msg}')
    raise SystemExit(1)


def main() -> int:
    if not MANIFESTS:
        fail('No external-skills-manifest.yaml files found.')

    seen = {}
    for manifest in MANIFESTS:
        data = yaml.safe_load(manifest.read_text(encoding='utf-8')) or {}
        skills = data.get('skills', [])
        if not isinstance(skills, list) or not skills:
            fail(f'{manifest} has no skills list.')

        seen_in_manifest = set()
        for s in skills:
            sid = s.get('id', '')
            if not ID_RE.match(sid):
                fail(f'Invalid skill id in {manifest}: {sid}')
            if sid in seen_in_manifest:
                fail(f'Duplicate skill id within {manifest}: {sid}')
            seen_in_manifest.add(sid)

            if sid in seen:
                prev = seen[sid]
                if prev['repo_url'] != s.get('repo_url') or prev['skills_url'] != s.get('skills_url'):
                    fail(f'Inconsistent metadata for shared skill id {sid}')
            else:
                seen[sid] = {
                    'repo_url': s.get('repo_url'),
                    'skills_url': s.get('skills_url'),
                }

            if not str(s.get('skills_url', '')).startswith('https://skills.sh/'):
                fail(f'Invalid skills_url for {sid}')
            if not str(s.get('repo_url', '')).startswith('https://github.com/'):
                fail(f'Invalid repo_url for {sid}')
            if not SHA_RE.match(str(s.get('pinned_commit', ''))):
                fail(f'Invalid pinned_commit for {sid}')
            if s.get('status') not in {'active', 'deprecated'}:
                fail(f'Invalid status for {sid}: {s.get("status")}')

    git_ls = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files'], text=True).splitlines()
    forbidden_prefixes = [
        'research/javascript-skills/upstream/',
        'research/javascript-skills/extracted/',
    ]
    for f in git_ls:
        for prefix in forbidden_prefixes:
            if f.startswith(prefix):
                fail(f'Forbidden tracked file path: {f}')

    print(f'Validation passed for {len(MANIFESTS)} manifests and {len(seen)} unique skills.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
