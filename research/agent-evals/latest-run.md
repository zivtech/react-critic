# Real-Agent Eval Status

Date: 2026-09-19
Status: UNVERIFIED

The six-case harness loads successfully, but the behavioral gate did not complete in this environment.

## Attempts

1. `python3 scripts/run_agent_eval.py --run --max-budget-usd 0.50 --timeout 300`
   - `executor-accepted` returned CLI exit code 1.
   - The CLI reported that claude.ai connectors were disabled because another authentication source took precedence.
   - The next case was interrupted after the original batch runner failed to flush per-case output; result not scored.
2. `python3 -u scripts/run_agent_eval.py --run --ids planner-react --max-budget-usd 0.50 --timeout 180`
   - Timed out after 180 seconds without model output.

The runner now flushes each result immediately. No case is marked passed, and no synthetic benchmark is accepted as a substitute. Retry requires a working Claude CLI authentication/runtime path; the configured per-case budget and timeout remain enforced.
