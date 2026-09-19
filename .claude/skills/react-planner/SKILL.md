---
name: react-planner
description: Plan bounded React, Next.js, or React Native work and produce a critic-ready, immutable JSON plan contract. Use before implementation when framework-specific design, migration, or multi-file work needs independent review.
---

# React Planner

Plan only. Do not edit application files, install dependencies, commit, push, or deploy.

## Workflow

1. Inspect the repository, current branch, dirty state, framework versions, tests, and relevant instructions.
2. Classify the target as `react`, `next`, or `react-native` using [framework-routing.md](references/framework-routing.md).
3. Search for existing implementations before proposing new ones.
4. Produce the exact JSON contract in [plan-contract.md](references/plan-contract.md).
5. Compute `plan_sha256` with `../shared-js-core/scripts/artifact_receipt.py plan-digest`.
6. Compute the pre-implementation scope fingerprint with `scope-fingerprint`, using the current base commit and every authorized path.
7. Save the complete framework critic output. Generic proposal review is supplemental, never a substitute for the framework critic.
8. Create the receipt with `artifact_receipt.py create-receipt`; this accepts only one exact accepted `VERDICT:` line and binds the review bytes, plan digest, and scope digest.
9. Continue only after `verify-receipt` validates the saved review and all three bindings.

If the critic returns `REVISE` or `REJECT`, revise the plan and generate new digests. An earlier receipt never approves a changed plan or changed scope.

## Boundaries

- Name assumptions and negative space explicitly.
- Separate local verification, deployment, and acceptance.
- Default to no commit, push, PR mutation, or deployment unless the user authorizes it.
- Do not claim that a digest authenticates an agent or reviewer; it only binds bytes and scope.
- Stop when the requested work expands into a new subsystem or product behavior.
