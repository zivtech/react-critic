# JavaScript Critics Architecture Decision

## Date
2026-03-05

## Context
We evaluated live skills.sh inventories for React, Next.js, JavaScript, React Native, and Expo.

Observed:
- React and Next.js have low overlap in query results and materially different failure modes.
- React Native and Expo have their own high-signal specialist ecosystem.
- Generic `next` query has substantial noise and requires strict canonical filtering.

## Decision
Use a split architecture in one repository:
- `react-critic`
- `next-critic` (App Router-first)
- `react-native-critic` (Expo first-class)

## Rationale
- Better domain signal and lower prompt noise than one monolithic JavaScript critic.
- Keeps routing explicit and testable.
- Matches drupal-critic orchestration pattern: strict manifests + max 3 skills per run + evidence-first verdicting.

## Guardrails
- No-copy policy for external skills.
- Pinned commits in manifests.
- Max 3 external skills loaded per review run.
- CRITICAL/MAJOR findings require evidence.
