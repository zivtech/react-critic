# Claude Handoff: React Planner, Executor, and External Skill Pins

Date: 2026-09-19
Repository: `/Users/AlexUA_1/claude/react-critic`
Branch: `codex/react-suite-upgrade-20260919`
Base HEAD before task: `5ed06f6e2667835912dc1b6cf1c40cc7da6dd07c`
Target: `origin/main`
Delivery status: The user authorized commit, push, and merge on 2026-09-19. Verify the branch and PR state live before continuing.

## Read This First

The requested implementation is present in the dirty working tree. Do not reset, clean, blanket-stage, or overwrite unrelated files. Reopen `AGENTS.md`, `CLAUDE.md`, `git status --short`, and the files named below before acting.

Three critic agent files were already locally modified before this implementation and were deliberately preserved byte-for-byte:

| File | Required SHA-256 |
|---|---|
| `.claude/agents/react-critic.md` | `c51d2983d8e4e88e220f08ee54a01199f744fb1bd94269d8025709ac37d3cc6b` |
| `.claude/agents/next-critic.md` | `16cd4fb07f7774413c7228e162ada52149a301971a37e17369fd8cc426fd9f5b` |
| `.claude/agents/react-native-critic.md` | `0315cc3bae30071057ebabeb4b6f39a494263eb7741514b023bdc959342f577e` |

Do not edit those three files unless the user explicitly changes this boundary. Their `M` status relative to `HEAD` is pre-existing user work, not part of this implementation.

Pre-existing untracked paths also remain user-owned and must not be removed or staged accidentally:

- `.claude/settings.local.json`
- `.omc/`
- `scripts/__pycache__/`

## What Was Implemented

### Planner and executor

- Added `.claude/skills/react-planner/` and `.claude/agents/react-planner.md`.
- Added `.claude/skills/react-executor/` and `.claude/agents/react-executor.md`.
- Framework signals route plans to `react-critic`, `next-critic`, or `react-native-critic` before generic proposal review.
- Planning and execution are gated by deterministic plan, scope, critic-output, and receipt hashes.
- `artifact_receipt.py` binds the complete saved critic output to the artifact and scope. It accepts exactly one `VERDICT:` line and only an accepted verdict.
- Receipts are integrity bindings, not reviewer identity signatures.
- Executor defaults prohibit commit, push, PR mutation, deployment, and publication.

Primary files:

- `.claude/skills/react-planner/SKILL.md`
- `.claude/skills/react-executor/SKILL.md`
- `.claude/skills/shared-js-core/scripts/artifact_receipt.py`
- `.claude/agents/js-critic-router.md`

### External skill supply chain

- Added authoritative v2 lock: `.claude/skills/shared-js-core/references/external-skills-lock.json`.
- Added four per-consumer v2 JSON routing manifests.
- Retained v1 YAML manifests as read-only compatibility inputs.
- Current lock state:
  - 45 identities
  - 31 active
  - 14 deprecated lineage tombstones
  - 521 locked text instruction/resource files
  - 0 scan exceptions
  - `generated_at`: `2026-09-19T18:43:05Z`
- Runtime loading now requires the verified resolver; inferred raw GitHub paths are forbidden.
- Bundle refreshes use explicit source paths, current commit pins, per-file size/SHA-256, deterministic bundle hashes, prompt-injection scanning, and atomic lock writes.
- Scan exceptions require an exact `ID:FINDING_HASH`; no global force flag exists.
- `--approve` requires explicit `--ids ...` or `--all`.
- Deprecated identities cannot be enabled by consumers.

Primary files:

- `.claude/skills/shared-js-core/scripts/external_skill_lib.py`
- `.claude/skills/shared-js-core/scripts/resolve_external_skill.py`
- `scripts/refresh_external_skills.py`
- `scripts/verify_no_copied_skills.py`
- `scripts/migrate_external_skills_v2.py`

### Research and routing decisions

See `research/javascript-skills/reports/react-next-skill-research-2026-09-19.md`.

Implemented decisions include:

- Adopt `vercel-labs/agent-skills/react-best-practices`.
- Add `vercel-labs/agent-skills/composition-patterns`.
- Add conditional executor-only `vercel/next.js/next-dev-loop`.
- Add conditional executor-only `vercel/next.js/next-cache-components-optimizer`.
- Consolidate Auth0 routing into `auth0/agent-skills/auth0`.
- Migrate renamed Expo and Sentry identities.
- Retire `vercel-labs/next-skills/*` and `expo/skills/expo-api-routes` as tombstones without pretending they have like-for-like replacements.

### CI and documentation

- Every PR/push runs unit tests, coverage, and offline lock/lineage checks.
- Live content verification runs when lock/resolver inputs change.
- Weekly workflow checks every locked file and detects upstream HEAD movement.
- README, CLAUDE instructions, routing maps, and `docs/index.html` describe v2 rather than the obsolete `content_sha256`/`--force` model.

## Verification Completed

The following passed in this checkout:

```bash
python3 -m unittest discover -s tests -v
# 22 tests passed

coverage run -m unittest discover -s tests
coverage report --fail-under=80
# 82% measured coverage

python3 scripts/verify_no_copied_skills.py
# 4 v1 manifests, 4 v2 consumers, 45 locked skills

python3 scripts/verify_no_copied_skills.py --verify-content
# all 45 identities / 521 locked files passed live verification

python3 scripts/refresh_external_skills.py --check
# 31 active entries checked; 0 pins moved at the final check

actionlint .github/workflows/*.yml
python3 -m py_compile .claude/skills/shared-js-core/scripts/*.py scripts/*.py tests/*.py
git diff --check
python3 -m unittest discover
```

The resolver also passed in an isolated temporary layout matching `~/.claude/skills/`, not only in the repository checkout.

Because upstream HEADs can move at any time, rerun `refresh_external_skills.py --check` before claiming current freshness.

## Remaining Gate: Real Claude-Agent Evaluation

Status: **UNVERIFIED**. Do not call it passed.

The six-case real Claude CLI harness exists at `scripts/run_agent_eval.py`, with cases under `research/agent-evals/cases/`. It includes three framework-routing cases, two refusal/no-mutation cases, and one accepted executor case that must make a real fixture edit.

Evidence is in `research/agent-evals/latest-run.md`:

1. The batch run returned CLI exit code 1 for `executor-accepted`; the CLI reported authentication-source precedence disabling claude.ai connectors.
2. A separate `planner-react` run timed out after 180 seconds without model output.
3. After these two failed approaches, further retries were stopped. No synthetic benchmark was substituted.

Do not redesign the agents to work around this environment failure. First diagnose the Claude CLI authentication/runtime path outside the implementation. Then rerun one bounded case:

```bash
python3 -u scripts/run_agent_eval.py \
  --run \
  --ids planner-react \
  --max-budget-usd 0.50 \
  --timeout 180
```

If that passes, run the remaining cases individually so every result is visible. Preserve the per-case budget and timeout. If a behavioral eval exposes an implementation defect, stop and re-plan before making a repair that expands into redesign.

## Meta-Skills and Router Pointer Worktrees

To avoid both dirty source checkouts, related pointer changes were prepared in
isolated worktrees on branch `codex/react-suite-pointers-20260919`:

- `/tmp/react-meta-pointers.vU754h/zivtech-meta-skills`
  - Based on `847301bc344b44b6392396c2f05b282a12f7a5a5`.
  - The installer now links `shared-js-core` explicitly before the three
    framework critics. The support bundle has no `SKILL.md`, so the old named
    skill loop silently omitted a runtime dependency.
  - A required-file gate skips the entire upgraded React integration unless
    the sibling contains the lock, resolver, and receipt helper. A dry run
    against published HEAD `5ed06f6e2667835912dc1b6cf1c40cc7da6dd07c`
    correctly skipped it; a dry run against this upgraded working tree linked
    the shared core and three critics. Therefore, publish/merge the React suite
    before landing or operating the meta-skills installer change.
  - The local Markdown planner now uses the current Vercel skill identities:
    `composition-patterns`, `react-best-practices`, and
    `react-native-skills`.
  - AGENTS/CLAUDE/README and the canonical catalog document the planner
    identity collision and withhold the external planner/executor route.
  - `python3 scripts/catalog.py --write`, `--check`, manifest generation,
    manifest verification, `git diff --check`, and both Codex/Claude dry-run
    install inspections completed. The Claude dry run correctly refused
    pre-existing unowned links; it still demonstrated the intended source
    targets and made no filesystem changes.

- `/tmp/react-meta-pointers.vU754h/meta-router`
  - Based on `e245fd01830b34965af787ab3073bf3d6f515c0f`.
  - Registry and top-level docs explicitly keep the incompatible external
    planner/executor unrouted.
    Critic-row descriptions were deliberately left unchanged so generated
    YAML/JSON do not become stale while the baseline validator is broken.
  - `git diff --check` passes.
  - `python3 scripts/generate-registry.py` is blocked by a pre-existing source
    mismatch: the registry parses 121 skills while `EXPECTED_SKILL_COUNT` is
    119. Do not change that global count as part of this React pointer task
    without reconciling the two unrelated entries first.

The canonical external route/evidence snapshots were intentionally not moved.
This `react-critic` implementation is still an uncommitted working tree, so
there is no immutable revision for those evidence records to pin. Updating
them now would falsely present local state as published canonical state.

An independent critic initially returned `REVISE` for stale generated registry
descriptions and the missing installer compatibility gate. After the row edits
were reverted and the gate was added, the bounded re-review returned `PASS` on
both findings.

## Recommended Next Actions

1. Reconfirm branch, HEAD, dirty state, preservation hashes, and repository instructions.
2. Review the complete unstaged diff, separating pre-existing critic-agent modifications from task changes.
3. Diagnose the Claude CLI runtime/authentication blocker without changing planner/executor behavior.
4. Run the six real-agent cases individually and record actual PASS/FAIL evidence.
5. Rerun unit, offline, live-content, freshness, workflow-lint, and secret checks after any change.
6. Review the two isolated meta worktree diffs and resolve the meta-router
   119-vs-121 baseline mismatch without folding unrelated registry work into
   this change.
7. After an immutable React-suite revision exists, refresh the meta-skills
   external route/evidence snapshots to that exact revision.
8. Land/publish the React suite before the meta-skills installer change; the
   compatibility gate intentionally skips the old published sibling.
9. After merge, verify the three repository default branches and preserve the unrelated local critic-agent edits—never blanket-stage them.

## Completion Boundary

The planner/executor, v2 resolver/lock, migrated routing, CI, tests, research record, and documentation are implemented and locally/live verified. Real Claude-agent behavioral acceptance remains unverified because of the CLI environment failure. Nothing here claims deployment, publication, merge, or product acceptance.
