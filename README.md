# react-critic

A critic-gated planner, executor, and review suite for React, Next.js, and React Native/Expo work.

[**Architecture Visual Explainer**](https://zivtech.github.io/react-critic/) &mdash; interactive diagram of the critic system and supply chain security model.

## Included Critics

- `react-planner`: inspect and emit a deterministic framework-routed plan contract
- `react-executor`: validate an accepted receipt, implement the bounded plan, verify, and re-submit for review
- `react-critic`: React component and architecture review (10 external skills)
- `next-critic`: Next.js App Router and cache/runtime review (12 external skills)
- `react-native-critic`: React Native + Expo review (18 external skills)
- `proposal-critic`: Plan-first review for proposals, ADRs, RFCs, and migration specs (5 external skills)

All four critics:
- enforce harsh-critic style structured output
- require evidence for CRITICAL/MAJOR findings
- load a maximum of 3 external specialist skills per run
- apply a Security Exploitability Gate to all security findings

A router agent (`js-critic-router`) dispatches plans and implementations to the framework critic based on repository signals. Framework routing precedes generic proposal routing.

## Install

```bash
git clone git@github.com:zivtech/react-critic.git
cp -r react-critic/.claude/skills/react-critic ~/.claude/skills/
cp -r react-critic/.claude/skills/next-critic ~/.claude/skills/
cp -r react-critic/.claude/skills/react-native-critic ~/.claude/skills/
cp -r react-critic/.claude/skills/proposal-critic ~/.claude/skills/
cp -r react-critic/.claude/skills/react-planner ~/.claude/skills/
cp -r react-critic/.claude/skills/react-executor ~/.claude/skills/
cp -r react-critic/.claude/skills/shared-js-core ~/.claude/skills/
cp react-critic/.claude/agents/js-critic-router.md ~/.claude/agents/
cp react-critic/.claude/agents/react-critic.md ~/.claude/agents/
cp react-critic/.claude/agents/next-critic.md ~/.claude/agents/
cp react-critic/.claude/agents/react-native-critic.md ~/.claude/agents/
cp react-critic/.claude/agents/proposal-critic.md ~/.claude/agents/
cp react-critic/.claude/agents/react-planner.md ~/.claude/agents/
cp react-critic/.claude/agents/react-executor.md ~/.claude/agents/
```

## Supply Chain Security

External skills are prompt text loaded from third-party GitHub repos into Claude's context. A compromised upstream repo means arbitrary prompt injection. This repo hardens against that:

- **Org allowlist**: `TRUSTED_OWNERS` in `scripts/skill_security.py`; unknown owners are rejected.
- **Explicit source paths**: no raw-content path is inferred from a skills.sh ID.
- **Pinned instruction bundles**: the v2 lock records every text instruction/resource file, its size and SHA-256, plus a deterministic bundle digest.
- **Runtime verification**: critics load external text only through `resolve_external_skill.py`, which rechecks consumer enablement, lifecycle, hashes, and injection findings.
- **Immutable lineage**: renamed and retired IDs remain as deprecated tombstones linked to active replacements.
- **Scan gate**: refresh is all-or-nothing. Exact, human-reviewed findings can be accepted only by ID and finding hash; there is no global force switch.
- **Approval gate**: refresh is dry-run by default and writes only with `--approve`.
- **CI split**: offline structure and unit tests run on every change; live content verification runs when lock/resolver inputs change and weekly freshness checks detect upstream movement.

See the [visual explainer](https://zivtech.github.io/react-critic/) for the full architecture diagram.

## Commands

```bash
python3 scripts/refresh_external_skills.py                        # dry-run: report moved active pins
python3 scripts/refresh_external_skills.py --approve --ids ID     # focused verified refresh
python3 scripts/refresh_external_skills.py --approve --all        # explicit full transaction
python3 scripts/refresh_external_skills.py --check                 # fail when active upstream HEADs moved
python3 scripts/verify_no_copied_skills.py                         # offline schema, lineage, and no-copy checks
python3 scripts/verify_no_copied_skills.py --verify-content  # fetch + hash verification
python3 scripts/run_benchmark.py --critic react --capture-commit <40-hex-commit> --run-id <uuid>
python3 -m unittest discover
python3 .claude/skills/shared-js-core/scripts/resolve_external_skill.py doctor
python3 scripts/run_agent_eval.py                            # list real-agent eval cases without spending
python3 scripts/run_agent_eval.py --run --ids planner-react  # opt-in Claude CLI run with a per-case budget
python3 scripts/migrate_external_skills_v2.py                # dry-run guard; one-time migration requires --write
```

## Reviewed benchmark corpus and future exact scorer

`research/benchmarks/` is a reviewed descriptive foundation for a future exact
structured defect-detection benchmark. It has eight synthetic fixtures per
critic, including five intentional-clean restraint controls: `react-06`,
`next-02`, `rn-01`, `rn-02`, and `rn-07`. Each fixture exposes the source
context, assumptions, requirements, rule, span-level evidence, and official
source used for adjudication. It does not represent provider execution or human
expert certification.

Candidate and baseline prompts have identical substantive instructions, rule
definitions, source context, evidence-span contract, anti-speculation guard,
and permission to return no findings. Candidate treatment adds only the
committed inline `SKILL.md`; referenced rubrics, agents, router material, and
external skills are excluded from both treatments. Each response is strict JSON
containing only findings with a known `rule_id`, sorted unique in-range
`evidence_lines`, and `assertion: "present"`.

The future runner never calls a provider. It requires run-specific immutable
captures before it can score any execution; provider/model/runtime/tool labels
would remain self-attested repository-native custody rather than independent
proof of authenticity. No provider pilot or capture set exists now. The corpus
therefore supports no performance, full-skill, prose/remediation, severity,
provider-authenticity, or statistical-superiority claim. Historical reports
remain rejected.

Publication builds the complete bundle in a private sibling staging directory,
then exposes all three files at once with the platform's atomic no-replace
directory rename. macOS uses `renamex_np(RENAME_EXCL)` and Linux uses
`renameat2(RENAME_NOREPLACE)`; unsupported platforms, kernels, or filesystems
fail closed. A concurrent destination is never replaced. On handled publication
failures, `COMPLETE` is removed before staging evidence is retained, and because
the canonical name remains free, a later retry is allowed. A marker-removal
failure is reported explicitly. Published bundles inherit the staging
directory's owner-only permissions; on macOS, inherited ACLs are removed and
verified before payload creation. This guard does not claim crash durability,
protection from an arbitrary malicious same-user process, or independent
witnessing.

## License

Apache 2.0
