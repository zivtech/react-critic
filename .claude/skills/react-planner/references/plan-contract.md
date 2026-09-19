# Plan Contract v1

Emit one JSON object with these required fields:

```json
{
  "schema_version": 1,
  "objective": "Concrete outcome",
  "framework": "react | next | react-native",
  "scope": ["repository-relative/path"],
  "assumptions": ["Verified fact or explicit uncertainty"],
  "steps": ["Ordered implementation step"],
  "validation": ["Command and expected result"],
  "rollback": "Recoverable rollback boundary",
  "out_of_scope": ["Explicit negative-space item"],
  "critic": "react-critic | next-critic | react-native-critic",
  "plan_sha256": "Digest returned by artifact_receipt.py"
}
```

The digest is SHA-256 over canonical JSON (UTF-8, sorted keys, compact separators) after omitting `plan_sha256`. The scope fingerprint is a separate artifact because the same plan can become stale when the working tree changes.

A critic receipt must contain:

```json
{
  "schema_version": 1,
  "critic": "react-critic",
  "verdict": "ACCEPT",
  "artifact_sha256": "plan digest",
  "scope_sha256": "pre-implementation scope digest",
  "review_sha256": "SHA-256 of the complete saved critic output"
}
```

Create this object with `artifact_receipt.py create-receipt`; do not transcribe or mint it by hand.
