---
name: next-critic
description: Next.js App Router-focused harsh review orchestration for plans and code. Use when reviewing RSC boundaries, caching/revalidation, route handlers/server actions, runtime decisions, and upgrade plans with evidence-backed critique.
---

# Next Critic

## Overview
Run a harsh-critic style review with Next.js App Router checks and evidence requirements.

## References
- Shared rubric: [../shared-js-core/references/js-review-rubric.md](../shared-js-core/references/js-review-rubric.md)
- Shared audiences: [../shared-js-core/references/shared-audience-activation-matrix.md](../shared-js-core/references/shared-audience-activation-matrix.md)
- Next rubric: [references/next-review-rubric.md](references/next-review-rubric.md)
- Routing map: [references/skill-routing-map.md](references/skill-routing-map.md)
- External skill manifest: [references/external-skills-manifest.yaml](references/external-skills-manifest.yaml)

## Workflow
1. Confirm review target and whether App Router assumptions apply.
2. Make pre-commitment predictions.
3. Verify technical claims against artifact details.
4. Run perspective analysis and explicit gap analysis.
5. Apply shared and Next rubrics.
6. Load max 3 external skills using routing map.
7. Enforce confidence-gated self-audit and realist check.
8. Return structured verdict.

## Defaults
- App Router-first by default.
- Treat Pages Router patterns as legacy unless explicitly required.

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
