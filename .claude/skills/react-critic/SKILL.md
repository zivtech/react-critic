---
name: react-critic
description: React-focused harsh review orchestration for plans and code. Use when reviewing React components, state management, rendering/performance, hook usage, refactors, and React migration work where evidence-backed critique is required.
---

# React Critic

## Overview
Run a harsh-critic style review with React-specific checks and evidence requirements.

## References
- Shared rubric: [../shared-js-core/references/js-review-rubric.md](../shared-js-core/references/js-review-rubric.md)
- Shared audiences: [../shared-js-core/references/shared-audience-activation-matrix.md](../shared-js-core/references/shared-audience-activation-matrix.md)
- React rubric: [references/react-review-rubric.md](references/react-review-rubric.md)
- Routing map: [references/skill-routing-map.md](references/skill-routing-map.md)
- External skill manifest: [references/external-skills-manifest.yaml](references/external-skills-manifest.yaml)

## Workflow
1. Confirm review target and scope.
2. Make pre-commitment predictions.
3. Verify claims against code or plan details.
4. Run perspective analysis and explicit gap analysis.
5. Apply shared and React rubrics.
6. Load max 3 external skills using routing map.
7. Enforce confidence-gated self-audit and realist check.
8. Return structured verdict.

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
