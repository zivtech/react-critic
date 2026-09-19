---
name: react-executor
description: Execute an accepted, fingerprinted React, Next.js, or React Native plan, verify the implementation, and require framework-critic review. Use only after react-planner produced a valid plan and receipt.
---

# React Executor

Implement only an approved plan. Preserve unrelated edits and stop on scope drift.

## Entry Gate

1. Read the plan, scope fingerprint, complete saved critic output, and critic receipt.
2. Recompute `plan_sha256` and the pre-implementation scope fingerprint with `../shared-js-core/scripts/artifact_receipt.py`.
3. Run `verify-receipt` with the saved review output and framework critic declared by the plan.
4. Refuse execution if the plan changed, scope changed, verdict is not accepted, critic does not match the framework, or reservations are not translated into bounded steps.

See [execution-gate.md](references/execution-gate.md) for receipt rules.

## Execution

1. Reconfirm branch, dirty state, authorized paths, and repository instructions.
2. Implement the ordered steps without expanding scope.
3. Add or update tests for changed behavior; target at least 80% coverage of new code where measurable.
4. Run the validation matrix in [verification-matrix.md](references/verification-matrix.md).
5. Generate a post-implementation scope fingerprint over exactly the reviewed paths.
6. Send the diff, validation evidence, plan digest, and post-implementation scope digest to the same framework critic and save its complete output.
7. Create and validate the implementation receipt from that saved output. A later edit or changed review invalidates the receipt and requires re-review.

## Boundaries

- Do not commit, push, open/update a PR, deploy, or publish by default.
- Never weaken a failing test to make the change pass.
- Do not treat local tests or critic acceptance as deployment, product acceptance, or release readiness.
- Stop and re-plan if repair becomes redesign, a new subsystem, or new product behavior.
