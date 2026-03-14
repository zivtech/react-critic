# react-critic

A multi-critic review suite for React, Next.js, and React Native/Expo work, built in the same orchestration style as drupal-critic.

[**Architecture Visual Explainer**](https://zivtech.github.io/react-critic/) &mdash; interactive diagram of the critic system and supply chain security model.

## Included Critics

- `react-critic`: React component and architecture review (9 external skills)
- `next-critic`: Next.js App Router and cache/runtime review (11 external skills)
- `react-native-critic`: React Native + Expo review (18 external skills)
- `proposal-critic`: Plan-first review for proposals, ADRs, RFCs, and migration specs (5 external skills)

All four critics:
- enforce harsh-critic style structured output
- require evidence for CRITICAL/MAJOR findings
- load a maximum of 3 external specialist skills per run
- apply a Security Exploitability Gate to all security findings

A router agent (`js-critic-router`) dispatches to the correct critic based on framework signals.

## Install

```bash
git clone git@github.com:zivtech/react-critic.git
cp -r react-critic/.claude/skills/react-critic ~/.claude/skills/
cp -r react-critic/.claude/skills/next-critic ~/.claude/skills/
cp -r react-critic/.claude/skills/react-native-critic ~/.claude/skills/
cp -r react-critic/.claude/skills/proposal-critic ~/.claude/skills/
cp -r react-critic/.claude/skills/shared-js-core ~/.claude/skills/
cp react-critic/.claude/agents/js-critic-router.md ~/.claude/agents/
cp react-critic/.claude/agents/react-critic.md ~/.claude/agents/
cp react-critic/.claude/agents/next-critic.md ~/.claude/agents/
cp react-critic/.claude/agents/react-native-critic.md ~/.claude/agents/
cp react-critic/.claude/agents/proposal-critic.md ~/.claude/agents/
```

## Supply Chain Security

External skills are prompt text loaded from third-party GitHub repos into Claude's context. A compromised upstream repo means arbitrary prompt injection. This repo hardens against that:

- **Org allowlist**: `TRUSTED_OWNERS` (15 orgs) in `scripts/skill_security.py` — unknown owners are rejected
- **Pinned commits + content hashes**: each skill pinned to a commit SHA with SHA-256 of the SKILL.md content
- **Injection scanning**: 10 prompt injection patterns checked on every refresh
- **Scan gate**: manifest updates blocked if scan warnings found (`--force` to override after review)
- **Approval gate**: `refresh_external_skills.py` is dry-run by default — shows diffs, requires `--approve`
- **Compare URLs**: refresh report includes clickable GitHub diff links for every pin change

See the [visual explainer](https://zivtech.github.io/react-critic/) for the full architecture diagram.

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

## License

Apache 2.0
