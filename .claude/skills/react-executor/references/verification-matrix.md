# Verification Matrix

Run the smallest applicable complete set and record commands plus outcomes.

| Change | Required validation |
|---|---|
| All | focused tests, lint/static checks, typecheck, reviewed diff |
| React UI | component/integration test and relevant accessibility checks |
| Next.js | build or production-equivalent compile, route/RSC/cache checks |
| React Native/Expo | platform-aware tests and config/build validation where available |
| Dependency/upgrade | lockfile integrity, migration checks, rollback evidence |
| Supply-chain tooling | offline unit tests plus explicit live verification when network inputs changed |

If a required check cannot run, report `UNVERIFIED` with the exact prerequisite. Do not silently substitute a weaker check.
