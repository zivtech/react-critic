#!/usr/bin/env python3
import argparse
import hashlib
import re
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skill_security import TRUSTED_OWNERS, scan_content

ROOT = Path(__file__).resolve().parent.parent
MANIFESTS = sorted(ROOT.glob('.claude/skills/*/references/external-skills-manifest.yaml'))

ID_RE = re.compile(r'^[^/]+/[^/]+/[^/]+$')
SHA_RE = re.compile(r'^[0-9a-f]{40}$')
SHA256_RE = re.compile(r'^[0-9a-f]{64}$')


def fail(msg: str) -> None:
    print(f'ERROR: {msg}')
    raise SystemExit(1)


def fetch_skill_content(repo_url: str, commit: str, skill_name: str) -> str | None:
    """Fetch SKILL.md content from raw.githubusercontent.com. Returns None on failure."""
    owner_repo = repo_url.removeprefix('https://github.com/')
    raw_url = f'https://raw.githubusercontent.com/{owner_repo}/{commit}/{skill_name}/SKILL.md'
    try:
        with urllib.request.urlopen(raw_url, timeout=15) as resp:
            return resp.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        print(f'  WARNING: HTTP {e.code} fetching {raw_url}')
        return None
    except Exception as e:
        print(f'  WARNING: Failed to fetch {raw_url}: {e}')
        return None


def sha256_of(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description='Verify no copied skills in manifests.')
    parser.add_argument(
        '--verify-content',
        action='store_true',
        help='Fetch skill content from raw.githubusercontent.com and verify content_sha256 hashes.',
    )
    args = parser.parse_args()

    if not MANIFESTS:
        fail('No external-skills-manifest.yaml files found.')

    seen = {}
    content_errors = 0

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
            owner = sid.split('/')[0]
            if owner not in TRUSTED_OWNERS:
                fail(f'Untrusted owner "{owner}" for {sid}. Add to TRUSTED_OWNERS in scripts/skill_security.py if approved.')
            if not SHA_RE.match(str(s.get('pinned_commit', ''))):
                fail(f'Invalid pinned_commit for {sid}')
            if s.get('status') not in {'active', 'deprecated'}:
                fail(f'Invalid status for {sid}: {s.get("status")}')

            # Validate content_sha256 format if present
            stored_hash = s.get('content_sha256')
            if stored_hash is not None:
                if not SHA256_RE.match(str(stored_hash)):
                    fail(f'Invalid content_sha256 format for {sid} (must be 64-char hex): {stored_hash}')

            # Optionally verify content hash against live content
            if args.verify_content:
                skill_name = sid.split('/')[-1]
                commit = s.get('pinned_commit', '')
                repo_url = s.get('repo_url', '')
                content = fetch_skill_content(repo_url, commit, skill_name)
                if content is None:
                    print(f'  WARNING: Could not fetch content for {sid} — skipping hash verification.')
                elif stored_hash is None:
                    print(f'  WARNING: No content_sha256 stored for {sid} — run refresh_external_skills.py --approve to populate.')
                else:
                    actual_hash = sha256_of(content)
                    if actual_hash != stored_hash:
                        print(f'ERROR: content_sha256 mismatch for {sid}')
                        print(f'  expected: {stored_hash}')
                        print(f'  actual:   {actual_hash}')
                        content_errors += 1
                    else:
                        print(f'  OK: {sid} content hash verified.')

                if content is not None:
                    scan_warnings = scan_content(content, sid)
                    if scan_warnings:
                        print(f'  SCAN WARNINGS ({len(scan_warnings)}) for {sid}:')
                        for w in scan_warnings:
                            print(w)
                        content_errors += len(scan_warnings)

    git_ls = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files'], text=True).splitlines()
    forbidden_prefixes = [
        'research/javascript-skills/upstream/',
        'research/javascript-skills/extracted/',
    ]
    for f in git_ls:
        for prefix in forbidden_prefixes:
            if f.startswith(prefix):
                fail(f'Forbidden tracked file path: {f}')

    if content_errors:
        print(f'\n{content_errors} content hash mismatch(es) detected.')
        raise SystemExit(1)

    print(f'Validation passed for {len(MANIFESTS)} manifests and {len(seen)} unique skills.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
