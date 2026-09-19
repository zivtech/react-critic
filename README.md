# react-critic

A multi-critic review suite for React, Next.js, and React Native/Expo work, built in the same orchestration style as drupal-critic.

[**Architecture Visual Explainer**](https://zivtech.github.io/react-critic/) &mdash; interactive diagram of the critic system and supply chain security model.

## Included Critics

- `react-critic`: React component and architecture review (9 external skills)
- `next-critic`: Next.js App Router and cache/runtime review (11 external skills)
- `react-native-critic`: React Native + Expo review (18 external skills)
- `proposal-critic`: Plan-first review for proposals, ADRs, RFCs, and migration specs (5 external skills)

All four critics:
- enforce harsh-critic style structured output
- require evidence for CRITICAL/MAJOR findings
- load a maximum of 3 external specialist skills per run
- apply a Security Exploitability Gate to all security findings

A router agent (`js-critic-router`) dispatches to the correct critic based on framework signals.

## Install

```bash
git clone git@github.com:zivtech/react-critic.git
cp -r react-critic/.claude/skills/react-critic ~/.claude/skills/
cp -r react-critic/.claude/skills/next-critic ~/.claude/skills/
cp -r react-critic/.claude/skills/react-native-critic ~/.claude/skills/
cp -r react-critic/.claude/skills/proposal-critic ~/.claude/skills/
cp -r react-critic/.claude/skills/shared-js-core ~/.claude/skills/
cp react-critic/.claude/agents/js-critic-router.md ~/.claude/agents/
cp react-critic/.claude/agents/react-critic.md ~/.claude/agents/
cp react-critic/.claude/agents/next-critic.md ~/.claude/agents/
cp react-critic/.claude/agents/react-native-critic.md ~/.claude/agents/
cp react-critic/.claude/agents/proposal-critic.md ~/.claude/agents/
```

## Supply Chain Security

External skills are prompt text loaded from third-party GitHub repos into Claude's context. A compromised upstream repo means arbitrary prompt injection. This repo hardens against that:

- **Org allowlist**: `TRUSTED_OWNERS` (15 orgs) in `scripts/skill_security.py` — unknown owners are rejected
- **Pinned commits + content hashes**: each skill pinned to a commit SHA with SHA-256 of the SKILL.md content
- **Injection scanning**: 10 prompt injection patterns checked on every refresh
- **Scan gate**: manifest updates blocked if scan warnings found (`--force` to override after review)
- **Approval gate**: `refresh_external_skills.py` is dry-run by default — shows diffs, requires `--approve`
- **Compare URLs**: refresh report includes clickable GitHub diff links for every pin change

See the [visual explainer](https://zivtech.github.io/react-critic/) for the full architecture diagram.

## Commands

```bash
python3 scripts/refresh_external_skills.py              # dry-run: show diffs
python3 scripts/refresh_external_skills.py --approve     # apply pin + hash updates
python3 scripts/refresh_external_skills.py --check       # CI: fail if updates needed
python3 scripts/verify_no_copied_skills.py               # validate manifest structure
python3 scripts/verify_no_copied_skills.py --verify-content  # fetch + hash verification
python3 scripts/run_benchmark.py --critic react --capture-commit <40-hex-commit> --run-id <uuid>
python3 -m unittest discover
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

Publication reserves the exact bundle directory before writing and adds a final
`COMPLETE` marker only after both report and manifest are in place. This is a
fail-closed local publication guard; it does not claim crash-durable or
independently witnessed publication.

## License

Apache 2.0
