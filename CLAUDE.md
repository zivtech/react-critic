# CLAUDE.md

## Project Overview

react-critic is a multi-critic orchestration repo for JavaScript ecosystems:
- react-critic
- next-critic
- react-native-critic

Each critic is read-only and uses external specialist skills by reference only.

## Commands

```bash
python3 scripts/refresh_external_skills.py
python3 scripts/refresh_external_skills.py --check
python3 scripts/verify_no_copied_skills.py
```

## Design Rules

- No-copy policy: external skills are referenced in manifests with pinned commits.
- Max 3 external skills loaded per run.
- Evidence required for CRITICAL/MAJOR findings.
- Shared JS-core rubric + critic-specific rubrics.
