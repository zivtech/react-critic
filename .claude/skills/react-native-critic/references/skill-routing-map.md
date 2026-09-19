# React Native Critic Skill Routing Map

Core (always loaded):
- vercel-labs/agent-skills/react-native-skills — core cross-platform patterns and native rendering guidance

RN specialists (load one based on context):
- callstackincubator/agent-skills/react-native-best-practices — when reviewing RN performance or native module usage
- callstackincubator/agent-skills/upgrading-react-native — when reviewing RN version upgrades or native dependency alignment
- react-native-community/skills/upgrade-react-native — when reviewing community RN upgrade patterns and tooling
- wshobson/agents/react-native-architecture — when reviewing RN app architecture or module boundaries
- wshobson/agents/react-native-design — when reviewing RN UI/UX patterns or cross-platform styling
- callstack/react-native-testing-library/react-native-testing — when reviewing RN test implementations or native module mocking

Expo specialists (load one when Expo detected):
- expo/skills/expo-native-ui — when reviewing Expo native UI components or platform APIs
- expo/skills/expo-data-fetching — when reviewing Expo data fetching, caching, or offline patterns
- expo/skills/expo-upgrade — when reviewing Expo SDK version upgrades
- expo/skills/eas-workflows — when reviewing Expo CI/CD pipelines or release automation
- expo/skills/expo-dom — when reviewing Expo DOM components or web-native bridging
- expo/skills/expo-router — when reviewing Expo Router navigation and route structure; it is not an API-routes replacement

Platform integrations (load when specific SDK detected):
- getsentry/sentry-agent-skills/sentry-react-native-sdk — when Sentry imports are detected
- auth0/agent-skills/auth0 — when Auth0 imports are detected; select the React Native section after verified loading

Shared support (load one):
- wshobson/agents/javascript-testing-patterns — when reviewing test strategy or coverage gaps
- wshobson/agents/modern-javascript-patterns — when reviewing modern JS idioms and async patterns
- sickn33/antigravity-awesome-skills/api-security-best-practices — when code handles API boundaries or sensitive data

Rules:
- Load max 3 skills: 1 core + 1 RN/Expo specialist + 1 shared support.
