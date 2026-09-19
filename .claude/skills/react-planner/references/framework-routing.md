# Framework Routing

Use the first applicable framework-specific signal, but report mixed scopes rather than hiding them.

| Framework | Strong signals | Required critic |
|---|---|---|
| React Native | `react-native`, Expo, Metro, `ios/`, `android/`, EAS | `react-native-critic` |
| Next.js | `next` dependency, `app/` or `pages/` conventions, Next APIs/config | `next-critic` |
| React | React/JSX/hooks without Next.js or React Native signals | `react-critic` |

For a monorepo change spanning frameworks, split it into separately fingerprinted plans when feasible. If it cannot be split, require every applicable critic and list all receipts; the primary `framework` field names the highest-risk scope.
