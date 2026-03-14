# CLAUDE.md

## Project Overview

react-critic is a multi-critic orchestration repo for JavaScript ecosystems:
- react-critic
- next-critic
- react-native-critic
- proposal-critic

Each critic is read-only and uses external specialist skills by reference only.

A router agent (`js-critic-router`) dispatches to the correct critic based on framework signals.

## Commands

```bash
python3 scripts/refresh_external_skills.py              # dry-run: show diffs
python3 scripts/refresh_external_skills.py --approve     # apply pin + hash updates
python3 scripts/refresh_external_skills.py --check       # CI: fail if updates needed
python3 scripts/verify_no_copied_skills.py               # validate manifest structure
python3 scripts/verify_no_copied_skills.py --verify-content  # fetch + hash verification
python3 scripts/run_benchmark.py --all
python3 scripts/aggregate_stability.py
```

## Design Rules

- No-copy policy: external skills are referenced in manifests with pinned commits.
- Max 3 external skills loaded per run.
- Evidence required for CRITICAL/MAJOR findings.
- Security Exploitability Gate: security findings must demonstrate a concrete exploit path reachable by non-privileged users. Unconfirmed findings tagged `[UNCONFIRMED]` and moved to Open Questions.
- Shared JS-core rubric + critic-specific rubrics.

## Supply Chain Security

[Visual explainer](https://zivtech.github.io/react-critic/) — interactive architecture diagram hosted on GitHub Pages.

External skills are loaded by reference (pinned commit SHA + content SHA-256 hash).

- `content_sha256` in manifests stores the SHA-256 of each skill's SKILL.md at the pinned commit.
- `refresh_external_skills.py` shows content diffs and requires `--approve` to write updates.
- `verify_no_copied_skills.py --verify-content` fetches and re-hashes to detect tampering.
- CI validates manifest structure; full content verification available via `--verify-content`.

### GitHub Repository Settings (manual setup)

Upstream skill repos should be configured with:
- **Signed commits**: require commit signature verification on default branch.
- **Branch protection**: require PR reviews and status checks before merge to default branch.
- **No force push**: disable force push to default branch to preserve commit history integrity.

These are manual configurations on each upstream repo — they cannot be enforced from this repo,
but should be verified before adding a new owner to `TRUSTED_OWNERS`.

## Benchmark Infrastructure

- Fixtures: `research/benchmarks/fixtures/{react,next,react-native}/` (8 per critic)
- Results: `research/benchmarks/results/`
- Scoring: rubric-coverage evaluation (prompt checklist vs annotated fixture issues)
- Seeds: 3 jackknife windows per critic; aggregate stability in `stability-report.md`
