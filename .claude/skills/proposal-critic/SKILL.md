---
name: proposal-critic
description: Plan-first harsh review orchestration for technical proposals, ADRs, RFCs, migration plans, and architecture decision records across the React ecosystem. Use when reviewing any pre-implementation artifact — proposals, specs, design docs, migration plans, feature briefs, or refactor RFCs — where evidence-backed plan critique is required.
---

# Proposal Critic

## Overview
Run a harsh-critic style plan review for technical proposals and decision records across the React, Next.js, and React Native/Expo ecosystem. This critic is plan-first by default: every review is a plan review. Never downgrade findings because code hasn't been written yet — underspecified proposals are a category of risk, not a grace period.

## External Skill References (No Copy Policy)
Use external skills as references only.

- Canonical reference file: [external-skills-manifest.yaml](references/external-skills-manifest.yaml)
- Routing policy: [skill-routing-map.md](references/skill-routing-map.md)

Rules:
- Do not copy external skill body content into this repository.
- Use manifest IDs/URLs and pinned commit metadata for traceability.
- If a referenced skill is unavailable in runtime, continue with local rubric fallback and state the limitation.

## References
- Shared rubric: [../shared-js-core/references/js-review-rubric.md](../shared-js-core/references/js-review-rubric.md)
- Shared audiences: [../shared-js-core/references/shared-audience-activation-matrix.md](../shared-js-core/references/shared-audience-activation-matrix.md)
- Proposal rubric: [references/proposal-review-rubric.md](references/proposal-review-rubric.md)
- Proposal audience triggers: [references/audience-activation-matrix.md](references/audience-activation-matrix.md)

## Workflow
1. Confirm review target and scope (proposal type, ecosystem target, stage: draft vs. final).
2. Make 3-5 pre-commitment predictions about likely gaps or failure points before deep review.
3. Extract key assumptions: list every assumption the proposal relies on, stated or implied.
4. Run plan-specific checks in order:
   a. Pre-mortem: top three failure modes at 6 months if implemented as written.
   b. Dependency audit: external teams, APIs, infrastructure, and skill gaps not owned by the author.
   c. Ambiguity scan: TBDs, undefined terms, vague success criteria, unresolved decisions.
   d. Feasibility check: timeline, resource, and complexity realism.
   e. Rollback analysis: what is the abort/fallback path if implementation fails or scope expands?
   f. Devil's-advocate challenge: argue against every major decision in the proposal.
5. Re-check through core proposal perspectives: Executor, Stakeholder, Skeptic.
6. Activate context-driven perspectives when triggered (see audience matrix).
7. Explicitly identify what is missing from the proposal.
8. Run mandatory self-audit:
   - LOW confidence or easily-refutable claims move to `Open Questions (unscored)`.
   - Preference/style-only points are downgraded or removed from scored sections.
   - Keep scored sections evidence-backed and high-confidence.
9. Run Realist Check on every surviving CRITICAL/MAJOR finding:
   - If implemented as written, what is the realistic worst-case outcome?
   - Which existing safeguard or context limits blast radius?
   - Is severity proportional to actual project risk?
   Recalibration rules:
   - Downgrade when a safeguard meaningfully limits impact.
   - Never downgrade data loss, security breach, or financial-impact findings.
   - Any downgrade must include `Mitigated by: ...` rationale.
10. Load at most 2-3 specialist external skills from the routing map.
11. Return structured verdict with evidence.

## Required Output Contract
Use this exact top-level structure:
- `VERDICT: [REJECT | REVISE | ACCEPT-WITH-RESERVATIONS | ACCEPT]`
- `Overall Assessment`
- `Pre-commitment Predictions`
- `Key Assumptions` (extracted and annotated)
- `Critical Findings`
- `Major Findings`
- `Minor Findings`
- `What's Missing`
- `Ambiguity Risks` (always present for proposals)
- `Pre-mortem: Top Failure Modes`
- `Multi-Perspective Notes`
- `Verdict Justification`
- `Open Questions (unscored)`

Rules:
- CRITICAL and MAJOR findings must include a specific section reference, direct quote, or explicit statement of absence (e.g., `"No rollback strategy mentioned in §4"` or `Proposal: "we'll figure out auth later"`).
- "No mention of X" is valid evidence for a gap finding.
- If a section has no items, write `None.`
- Keep speculative points in `Open Questions` only.
- In `Verdict Justification`, state whether escalation to adversarial review happened and why.
- `Ambiguity Risks` is always-on for proposals (not optional like code reviews).

## Perspectives
Always run:
- Executor (the team implementing the proposal)
- Stakeholder (PM/leadership approving and funding it)
- Skeptic (a senior engineer who wants to find the flaws)

Context-driven (activate when triggered; see audience matrix):
- Security Engineer
- Performance Engineer
- DX Maintainer

Perspective notes must appear in `Multi-Perspective Notes`.

## Proposal Must-Check List
Always verify before final verdict:
- Assumptions: are key assumptions stated explicitly, or are critical ones implied and unstated?
- Dependencies: are external team, API, infrastructure, and skill dependencies named with owners and risk mitigations?
- Rollback/abort: is there a clear fallback strategy if implementation fails or scope expands?
- Success criteria: are acceptance criteria concrete and measurable, not vague?
- Validation: is a testing or proof-of-concept strategy specified?
- Estimates: are timeline and resource estimates grounded with rationale, or optimistic placeholders?
- Alternatives: are alternative approaches considered and explicitly rejected with reasons?
- Scope risk: is scope creep risk acknowledged and bounded?
- Migration/breaking changes: are downstream consumers, breaking changes, and migration costs called out?
- Operability: is post-ship monitoring, alerting, and runbook coverage addressed?

## Skill Loading Rules
- Default: one architecture or design-review skill + one domain-specialist skill.
- Prefer skills that assess design and risk over skills that check runtime correctness (those belong in code critics).
- Load at most 3 skills per run.

## Severity Calibration
- CRITICAL: fundamental flaw that, if unaddressed, makes the proposal not implementable, creates a security or data risk, or ensures project failure.
- MAJOR: significant gap (missing owner, undefined scope, no rollback) that will likely cause rework, delay, or user-facing incident.
- MINOR: non-blocking gap, weak assumption, or underdeveloped section that should be tightened before final approval.
- Do not inflate severity for stylistic or organizational preferences.

## Stop Conditions
- If the proposal is too broad to review in one pass, narrow scope by section or decision.
- If a claim cannot be verified from proposal content, move to `Open Questions`.
