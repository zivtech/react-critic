# Proposal Critic Skill Routing Map

Core:
- wshobson/agents/react-native-architecture

Specialists:
- dotneet/claude-code-marketplace/typescript-react-reviewer

Shared support:
- wshobson/agents/modern-javascript-patterns
- sickn33/antigravity-awesome-skills/api-security-best-practices
- wshobson/agents/javascript-testing-patterns

Rules:
- Load max 3 skills: 1 core + 1 specialist + 1 shared support.
- Prefer architecture skill as core for most proposals.
- Activate security shared support when proposal touches auth, APIs, or infrastructure.
- Activate testing shared support when proposal makes testability claims.
