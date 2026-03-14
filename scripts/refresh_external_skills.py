#!/usr/bin/env python3
import argparse
import difflib
import hashlib
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MANIFESTS = sorted(ROOT.glob('.claude/skills/*/references/external-skills-manifest.yaml'))
REPORT = ROOT / 'research/javascript-skills/reports/external-skills-refresh-report.md'


def get_head_sha(repo_url: str) -> str:
    url = repo_url if repo_url.endswith('.git') else repo_url + '.git'
    out = subprocess.check_output(['git', 'ls-remote', url, 'HEAD'], text=True)
    return out.split()[0]


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


def show_diff(skill_id: str, old_content: str | None, new_content: str | None) -> None:
    old_lines = (old_content or '(content unavailable)\n').splitlines(keepends=True)
    new_lines = (new_content or '(content unavailable)\n').splitlines(keepends=True)
    diff = list(difflib.unified_diff(old_lines, new_lines, fromfile=f'{skill_id} (old)', tofile=f'{skill_id} (new)'))
    if diff:
        print(f'\n--- Diff for {skill_id} ---')
        print(''.join(diff), end='')
    else:
        print(f'  (no content diff for {skill_id})')


def main() -> int:
    parser = argparse.ArgumentParser(description='Refresh pinned commits in all critic manifests.')
    parser.add_argument('--check', action='store_true', help='Fail if updates are needed without writing files.')
    parser.add_argument('--approve', action='store_true', help='Apply pin and content hash updates (writes manifests).')
    args = parser.parse_args()

    changes = []
    checked = 0

    for manifest in MANIFESTS:
        data = yaml.safe_load(manifest.read_text(encoding='utf-8')) or {}
        skills = data.get('skills', [])
        checked += len(skills)
        local_changes = []

        for s in skills:
            latest = get_head_sha(s['repo_url'])
            current = s.get('pinned_commit', '')
            if latest == current:
                continue

            skill_name = s['id'].split('/')[-1]
            print(f'\nSkill {s["id"]}: {current or "-"} -> {latest}')

            old_content = fetch_skill_content(s['repo_url'], current, skill_name) if current else None
            new_content = fetch_skill_content(s['repo_url'], latest, skill_name)

            if not args.check:
                show_diff(s['id'], old_content, new_content)

            if new_content is not None:
                new_hash = sha256_of(new_content)
                print(f'  content_sha256 (new): {new_hash}')
            else:
                new_hash = None
                print(f'  WARNING: Could not fetch new content — content_sha256 will be unverified.')

            local_changes.append((s['id'], current, latest, new_hash))
            changes.append((manifest, s['id'], current, latest, new_hash))

            if args.approve:
                s['pinned_commit'] = latest
                if new_hash is not None:
                    s['content_sha256'] = new_hash
                else:
                    s.pop('content_sha256', None)

        if local_changes and args.approve:
            data['generated_at'] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
            manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')

    lines = [
        '# External Skill Refresh Report',
        '',
        f'Generated: {datetime.now(timezone.utc).isoformat()}',
        f'Checked skills: {checked}',
        f'Changed pins: {len(changes)}',
        '',
    ]

    if changes:
        lines.append('| Manifest | Skill | Old | New | Hash Verified |')
        lines.append('|---|---|---|---|---|')
        for m, sid, old, new, new_hash in changes:
            verified = 'yes' if new_hash else '# UNVERIFIED'
            lines.append(f'| `{m.relative_to(ROOT)}` | `{sid}` | `{old or "-"}` | `{new}` | {verified} |')
    else:
        lines.append('No pin changes detected.')

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    if args.check and changes:
        print(f'Manifest updates required for {len(changes)} skill entries.')
        return 1

    if changes and not args.approve and not args.check:
        print('\nRun with --approve to apply these changes.')

    print(f'Checked {checked} skill entries across {len(MANIFESTS)} manifests.')
    print(f'Wrote report: {REPORT}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
