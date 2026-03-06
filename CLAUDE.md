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
python3 scripts/refresh_external_skills.py
python3 scripts/refresh_external_skills.py --check
python3 scripts/verify_no_copied_skills.py
python3 scripts/run_benchmark.py --all
python3 scripts/aggregate_stability.py
```

## Design Rules

- No-copy policy: external skills are referenced in manifests with pinned commits.
- Max 3 external skills loaded per run.
- Evidence required for CRITICAL/MAJOR findings.
- Shared JS-core rubric + critic-specific rubrics.

## Benchmark Infrastructure

- Fixtures: `research/benchmarks/fixtures/{react,next,react-native}/` (8 per critic)
- Results: `research/benchmarks/results/`
- Scoring: rubric-coverage evaluation (prompt checklist vs annotated fixture issues)
- Seeds: 3 jackknife windows per critic; aggregate stability in `stability-report.md`
