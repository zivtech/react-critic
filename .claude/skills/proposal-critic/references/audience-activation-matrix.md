# Proposal Critic Audience Activation Matrix

Core audiences are always active for all proposal reviews:
- Executor (the team that will implement the proposal)
- Stakeholder (PM, tech lead, or leadership approving the work)
- Skeptic (a senior engineer looking to find fatal flaws)

Context-driven audiences:

## Security Engineer
Activate when:
- Proposal involves authentication, authorization, session management, or token handling.
- Proposal involves new API surfaces, data persistence, or user PII.
- Proposal involves infrastructure changes (CDN, edge runtime, third-party integrations).

Must-check prompts:
- Are trust boundaries across the proposed system explicitly defined?
- Are auth and data exposure risks addressed or deferred with acknowledged risk?

## Performance Engineer
Activate when:
- Proposal involves rendering-path changes (RSC boundaries, hydration, bundle splitting).
- Proposal involves data fetching strategy, caching changes, or large data sets.
- Proposal estimates performance improvement without baseline measurements.

Must-check prompts:
- Are performance goals stated with measurable baselines and targets?
- Could this proposal introduce new waterfalls, re-render pressure, or cache invalidation storms?

## DX Maintainer
Activate when:
- Proposal involves developer tooling, CI/CD, build pipeline, or local dev environment changes.
- Proposal involves a major refactor or architectural migration affecting many files.
- Proposal changes conventions that downstream teams or new hires must learn.

Must-check prompts:
- Can a new engineer understand, modify, and maintain the proposed system safely?
- Is the migration or upgrade path documented and incremental?

## Output Convention
When active, include one line per audience in `Multi-Perspective Notes`:
- `- Executor: ...`
- `- Stakeholder: ...`
- `- Skeptic: ...`
- `- Security Engineer: ...` (only when activated)
- `- Performance Engineer: ...` (only when activated)
- `- DX Maintainer: ...` (only when activated)
