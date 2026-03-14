# Proposal Critic Skill Routing Map

Core (always loaded):
- wshobson/agents/react-native-architecture — cross-framework architectural patterns for proposal evaluation

Specialists (load one based on proposal focus):
- dotneet/claude-code-marketplace/typescript-react-reviewer — when proposal involves TypeScript API design or type system decisions

Shared support (load one):
- wshobson/agents/modern-javascript-patterns — when evaluating JS/TS pattern choices
- sickn33/antigravity-awesome-skills/api-security-best-practices — when proposal involves API design, auth, or data handling
- wshobson/agents/javascript-testing-patterns — when evaluating test strategy feasibility

Rules:
- Load max 3 skills: 1 core + 1 specialist + 1 shared support.
- Uses executor/stakeholder/skeptic perspectives instead of security/new-hire/ops.
