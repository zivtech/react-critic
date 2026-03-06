# react-critic

A multi-critic review suite for React, Next.js, and React Native/Expo work, built in the same orchestration style as drupal-critic.

## Included Critics

- `react-critic`: React component and architecture review
- `next-critic`: Next.js App Router and cache/runtime review
- `react-native-critic`: React Native + Expo review
- `proposal-critic`: Plan-first review for proposals, ADRs, RFCs, and migration specs across the React ecosystem

All four critics:
- enforce harsh-critic style structured output
- require evidence for CRITICAL/MAJOR findings
- load a maximum of 3 external specialist skills per run

## Install

```bash
git clone git@github.com:zivtech/react-critic.git
cp -r react-critic/.claude/skills/react-critic ~/.claude/skills/
cp -r react-critic/.claude/skills/next-critic ~/.claude/skills/
cp -r react-critic/.claude/skills/react-native-critic ~/.claude/skills/
cp -r react-critic/.claude/skills/proposal-critic ~/.claude/skills/
cp react-critic/.claude/agents/react-critic.md ~/.claude/agents/
cp react-critic/.claude/agents/next-critic.md ~/.claude/agents/
cp react-critic/.claude/agents/react-native-critic.md ~/.claude/agents/
cp react-critic/.claude/agents/proposal-critic.md ~/.claude/agents/
```

## Validation

```bash
python3 scripts/refresh_external_skills.py --check
python3 scripts/verify_no_copied_skills.py
```

## License

Apache 2.0
