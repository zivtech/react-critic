#!/usr/bin/env python3
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / 'research/javascript-skills/reports'
MANIFESTS = sorted(ROOT.glob('.claude/skills/*/references/external-skills-manifest.yaml'))


def main() -> None:
    rows = []
    for m in MANIFESTS:
        critic = m.parts[-4]
        data = yaml.safe_load(m.read_text(encoding='utf-8')) or {}
        for s in data.get('skills', []):
            rows.append({
                'critic': critic,
                'id': s['id'],
                'skills_url': s['skills_url'],
                'repo_url': s['repo_url'],
                'pinned_commit': s['pinned_commit'],
                'categories': ','.join(s.get('categories', [])),
                'priority': s.get('priority', ''),
                'status': s.get('status', ''),
            })

    rows.sort(key=lambda x: (x['critic'], -int(x['priority']), x['id']))

    md = [
        '# Critics External Skills Inventory',
        '',
        f'- Critics: {len(set(r["critic"] for r in rows))}',
        f'- Total references: {len(rows)}',
        f'- Unique skill IDs: {len(set(r["id"] for r in rows))}',
        '',
        '| Critic | Skill ID | Priority | Categories | Status |',
        '|---|---|---:|---|---|',
    ]
    for r in rows:
        md.append(f"| `{r['critic']}` | `{r['id']}` | {r['priority']} | `{r['categories']}` | `{r['status']}` |")

    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / 'skills-inventory.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    (REPORTS / 'inventory-summary.json').write_text(json.dumps({
        'critics': sorted(set(r['critic'] for r in rows)),
        'total_references': len(rows),
        'unique_skill_ids': len(set(r['id'] for r in rows)),
    }, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
