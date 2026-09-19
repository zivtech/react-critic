# Next Critic Skill Routing Map

Core (always loaded):
- vercel-labs/agent-skills/react-best-practices — core React and Next.js performance guidance
- vercel-labs/agent-skills/composition-patterns — load when component APIs or server/client composition are central

Specialists (load one based on context):
- wshobson/agents/nextjs-app-router-patterns — when reviewing advanced App Router architecture patterns
- wsimmonds/claude-nextjs-skills/nextjs-app-router-fundamentals — when reviewing basic App Router component structure

Executor-only upstream tools (never load from version keywords alone):
- vercel/next.js/next-dev-loop — only with Next.js 16.3+, Turbopack, a running `next dev`, `/_next/mcp`, and `agent-browser >=0.31.1`
- vercel/next.js/next-cache-components-optimizer — only with Next.js 16.3+, `cacheComponents` enabled, a production-like verification rig, and an explicit instant-navigation objective

Auth conditional (load when auth imports detected):
- clerk/skills/clerk-nextjs-patterns — when Clerk imports are present
- auth0/agent-skills/auth0 — when Auth0 imports are present; select the Next.js section after verified loading
- mindrally/skills/nextauth-authentication — when NextAuth.js / Auth.js imports are present

Shared support (load one):
- wshobson/agents/javascript-testing-patterns — when reviewing test strategy or coverage gaps
- wshobson/agents/modern-javascript-patterns — when reviewing modern JS idioms and async patterns
- sickn33/antigravity-awesome-skills/api-security-best-practices — when code handles API boundaries or sensitive data

Rules:
- Load max 3 skills: 1 core + 1 context specialist + 1 shared support.
- App Router-first guidance by default.
