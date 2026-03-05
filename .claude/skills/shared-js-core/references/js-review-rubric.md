# Shared JS Review Rubric

## Security
- Input trust boundaries are explicit.
- Auth/session/token handling avoids unsafe defaults.
- Sensitive data exposure is prevented.

## Correctness and Architecture
- Data/state boundaries are explicit.
- Error paths are handled and observable.
- Layering is coherent and avoids hidden coupling.

## Operational Safety
- Failure mode and rollback path are defined.
- Upgrade/dependency risk is called out.

## Testing and Verification
- Critical paths have direct tests.
- Async/concurrency behavior is validated.

## Confidence
- CRITICAL/MAJOR findings are evidence-backed.
- Speculative concerns move to open questions.
