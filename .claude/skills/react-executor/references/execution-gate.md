# Execution Gate

An accepted receipt is necessary but not sufficient: it must bind the current artifact and current scope.

Required fields are `schema_version`, `critic`, `verdict`, `artifact_sha256`, `scope_sha256`, and `review_sha256`. Create the receipt from the complete saved critic output; the adapter accepts exactly one `VERDICT:` line and only `ACCEPT` or `ACCEPT-WITH-RESERVATIONS`.

Fail closed on:

- missing or malformed fields;
- framework/critic mismatch;
- changed plan digest;
- changed pre-implementation scope digest;
- changed or missing saved critic output;
- `REVISE` or `REJECT`;
- paths outside the authorized scope;
- an implementation receipt generated before the final edit.

The receipt binds bytes; it is not an identity signature. Repository permissions and the surrounding agent/tool trust model still control who may run a critic or create a receipt.
