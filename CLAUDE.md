# CLAUDE.md

## Project Overview

react-critic is a critic-gated planner/executor and review repo for JavaScript ecosystems:
- react-planner
- react-executor
- react-critic
- next-critic
- react-native-critic
- proposal-critic

Each critic is read-only and uses external specialist skills by reference only.

A router agent (`js-critic-router`) dispatches plans and implementations to the correct framework critic. Framework signals take precedence over generic proposal routing.

## Commands

```bash
python3 scripts/refresh_external_skills.py                        # dry-run: show moved pins
python3 scripts/refresh_external_skills.py --approve --ids ID     # explicit focused transaction
python3 scripts/refresh_external_skills.py --approve --all        # explicit full transaction
python3 scripts/refresh_external_skills.py --check                 # fail if active pins moved
python3 scripts/verify_no_copied_skills.py               # validate manifest structure
python3 scripts/verify_no_copied_skills.py --verify-content  # fetch + hash verification
python3 scripts/run_benchmark.py --critic react --capture-commit <40-hex-commit> --run-id <uuid>
python3 -m unittest discover
python3 scripts/run_agent_eval.py
```

## Design Rules

- No-copy policy: external skills are referenced in manifests with pinned commits.
- Max 3 external skills loaded per run.
- Evidence required for CRITICAL/MAJOR findings.
- Security Exploitability Gate: security findings must demonstrate a concrete exploit path reachable by non-privileged users. Unconfirmed findings tagged `[UNCONFIRMED]` and moved to Open Questions.
- Shared JS-core rubric + critic-specific rubrics.

## Supply Chain Security

[Visual explainer](https://zivtech.github.io/react-critic/) — interactive architecture diagram hosted on GitHub Pages.

External skills are loaded only through the verified v2 resolver (explicit source path, pinned commit, per-file size/SHA-256, and deterministic bundle digest).

- The central v2 lock stores immutable lineage and instruction-bundle hashes; per-critic v2 manifests only route enabled IDs.
- `refresh_external_skills.py` is dry-run by default and requires `--approve --ids ...` or `--approve --all` to write an all-or-nothing transaction.
- Prompt-injection exceptions are exact ID/finding-hash pairs; there is no global force switch.
- `verify_no_copied_skills.py --verify-content` fetches and re-hashes to detect tampering.
- CI validates offline structure on every change, verifies live content when lock/resolver inputs change, and runs weekly freshness/content checks.

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
- Corpus status: reviewed descriptive foundation only; no provider pilot or committed captures exist.
- Controls: `react-06`, `next-02`, `rn-01`, `rn-02`, and `rn-07` are intentional-clean restraint controls.
- Candidate treatment: only the committed inline `SKILL.md`; referenced rubrics, agents, router material, and external skills are excluded.
- Future model scoring: exact rule-and-line response matching from self-attested repository-native capture blobs at an exact Git commit.
- Windows: deterministic jackknife sensitivity references, never additional samples or provider/model seeds.
- Boundaries: this corpus supports no performance, authenticity, severity-quality, full-skill, or statistical claim. Historical reports remain rejected.
