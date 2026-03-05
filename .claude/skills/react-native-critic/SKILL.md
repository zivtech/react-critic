---
name: react-native-critic
description: React Native and Expo-focused harsh review orchestration for plans and code. Use when reviewing RN architecture, Expo workflows, mobile performance, native integration, and release safety with evidence-backed critique.
---

# React Native Critic

## Overview
Run a harsh-critic style review with React Native and Expo checks and evidence requirements.

## References
- Shared rubric: [../shared-js-core/references/js-review-rubric.md](../shared-js-core/references/js-review-rubric.md)
- Shared audiences: [../shared-js-core/references/shared-audience-activation-matrix.md](../shared-js-core/references/shared-audience-activation-matrix.md)
- RN rubric: [references/react-native-review-rubric.md](references/react-native-review-rubric.md)
- Routing map: [references/skill-routing-map.md](references/skill-routing-map.md)
- External skill manifest: [references/external-skills-manifest.yaml](references/external-skills-manifest.yaml)

## Workflow
1. Confirm target (RN CLI, Expo managed/bare, or mixed).
2. Make pre-commitment predictions.
3. Verify claims against artifact details.
4. Run perspective analysis and explicit gap analysis.
5. Apply shared and RN rubrics.
6. Load max 3 external skills using routing map.
7. Enforce confidence-gated self-audit and realist check.
8. Return structured verdict.

## Defaults
- Expo is first-class in v1.
- Mobile release safety and observability checks are mandatory.

## Output Contract
- VERDICT: REJECT | REVISE | ACCEPT-WITH-RESERVATIONS | ACCEPT
- Overall Assessment
- Pre-commitment Predictions
- Critical Findings
- Major Findings
- Minor Findings
- What's Missing
- Ambiguity Risks (plans only)
- Multi-Perspective Notes
- Verdict Justification
- Open Questions (unscored)

Rules:
- CRITICAL/MAJOR findings require evidence.
- Empty sections must say `None.`
- Speculation belongs in Open Questions.
