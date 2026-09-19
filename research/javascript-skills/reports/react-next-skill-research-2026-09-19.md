# React / Next.js External Skill Research

Date: 2026-09-19

This is the implementation record of the delegated skills.sh/GitHub research. Inclusion here means “locked as a reference under explicit routing conditions,” not blanket endorsement of all upstream advice.

## Adopt

| Skill | Decision | Boundary |
|---|---|---|
| [vercel-labs/agent-skills/react-best-practices](https://skills.sh/vercel-labs/agent-skills/react-best-practices) | Replace the renamed `vercel-react-best-practices` identity and use as React/Next core guidance. | External guidance remains subordinate to repository and user instructions. |
| [vercel-labs/agent-skills/composition-patterns](https://skills.sh/vercel-labs/agent-skills/composition-patterns) | Add for component API, compound-component, and state/provider boundary work. | Load only when architecture/composition is material. |
| [vercel/next.js/next-dev-loop](https://skills.sh/vercel/next.js/next-dev-loop) | Add as executor-only runtime support. | Require Next.js 16.3+, Turbopack, a running `next dev`, `/_next/mcp`, and `agent-browser >=0.31.1`. |
| [vercel/next.js/next-cache-components-optimizer](https://skills.sh/vercel/next.js/next-cache-components-optimizer) | Add as executor-only navigation optimization support. | Require Next.js 16.3+, `cacheComponents`, a production-like rig, and an explicit instant-navigation objective. |

## Migrate

- Consolidate Auth0 framework-specific identities into [auth0/agent-skills/auth0](https://skills.sh/auth0/agent-skills/auth0), selecting the relevant framework section after verified loading.
- Move Expo routes to the renamed `expo-native-ui`, `expo-data-fetching`, `expo-upgrade`, `eas-workflows`, and `expo-dom` identities.
- Add `expo-router` for navigation/route structure. It is not a successor to the retired Expo API-routes skill.
- Move Sentry routing to `getsentry/sentry-agent-skills/sentry-react-native-sdk`.

## Retire or Reject

- Retire all `vercel-labs/next-skills/*` entries: upstream has removed them and there is no like-for-like general Next.js successor.
- Retire `expo/skills/expo-api-routes` without replacement.
- Do not use broad generic React skills from lower-authority catalogs as engineering-core guidance when the Vercel/Callstack sources cover the job more precisely.
- Do not use a visual frontend-design skill as a substitute for framework correctness, testing, or runtime evidence.

## Verification Status

The adopted and migrated identities are represented in the v2 lock by explicit GitHub source paths, current pinned commits, per-file hashes, and bundle digests. Deprecated identities remain as immutable lineage tombstones. This verifies fetched bytes and routing integrity; it does not certify upstream correctness or future compatibility.
