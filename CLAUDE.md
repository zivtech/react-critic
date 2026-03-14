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

## TODO: Supply Chain Security for External Skills

The external skills manifests (`external-skills-manifest.yaml`) pin upstream skills by commit SHA, but the current tooling has supply chain gaps that need to be addressed:

1. **No diff review on refresh** — `refresh_external_skills.py` updates pins to HEAD silently. No changelog or diff of what changed in upstream SKILL.md files between the old and new pin.
2. **No content scanning** — nothing checks incoming skill content for suspicious patterns (prompt injection markers, instruction overrides, encoded payloads). These skills are prompt text injected into Claude's context.
3. **No signature/author verification** — anyone with push access to an upstream repo can change what gets loaded.
4. **No approval gate** — refresh runs and updates pins automatically with no PR/review step.

Minimum next steps:
- Add diff output to `refresh_external_skills.py` so changes are visible before committing new pins.
- Add basic content scanning rules (flag suspicious patterns like "ignore previous instructions", base64 blocks, etc.).
- Consider requiring a PR for pin updates rather than committing directly.

See also: drupal-critic has the same gaps and the same TODO.
