# Proposal Review Rubric

## Completeness
- All major sections present: problem statement, proposed solution, alternatives considered, success criteria, rollback plan.
- Every key decision is accompanied by explicit rationale.
- Dependencies are named with owners and risk mitigations.

## Assumption Quality
- Key assumptions are stated, not implied.
- Assumptions are validated or acknowledged as risks.
- Optimistic assumptions in timeline and resource estimates are flagged.

## Risk and Rollback
- Pre-mortem coverage: failure modes are anticipated, not ignored.
- A rollback or abort strategy is defined for implementation failure and scope expansion.
- Blast radius of failure is assessed.

## Scope and Feasibility
- Scope is bounded: what is explicitly out of scope is stated.
- Scope creep vectors are identified.
- Timeline estimates are grounded in prior art or complexity analysis, not wishful thinking.

## Operability
- Post-ship monitoring and alerting strategy is specified.
- Runbook or escalation path is referenced or planned.
- Breaking changes and migration costs to downstream consumers are called out.

## Testability and Validation
- A proof-of-concept or testing strategy is included.
- Acceptance criteria are measurable, not vague.
- Validation gates before full rollout are specified.

## React Ecosystem Considerations
- React version, Next.js App Router, or React Native/Expo version constraints are stated if relevant.
- Compatibility risk with existing dependency tree is assessed.
- Server/client boundary or bundle size impact is addressed if the proposal touches rendering.
