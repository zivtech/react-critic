#!/usr/bin/env python3
import argparse
import subprocess
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


def main() -> int:
    parser = argparse.ArgumentParser(description='Refresh pinned commits in all critic manifests.')
    parser.add_argument('--check', action='store_true', help='Fail if updates are needed without writing files.')
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
            if latest != current:
                s['pinned_commit'] = latest
                local_changes.append((s['id'], current, latest))
                changes.append((manifest, s['id'], current, latest))

        if local_changes and not args.check:
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
        lines.append('| Manifest | Skill | Old | New |')
        lines.append('|---|---|---|---|')
        for m, sid, old, new in changes:
            lines.append(f'| `{m.relative_to(ROOT)}` | `{sid}` | `{old or "-"}` | `{new}` |')
    else:
        lines.append('No pin changes detected.')

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    if args.check and changes:
        print(f'Manifest updates required for {len(changes)} skill entries.')
        return 1

    print(f'Checked {checked} skill entries across {len(MANIFESTS)} manifests.')
    print(f'Wrote report: {REPORT}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
