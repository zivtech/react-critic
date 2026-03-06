# Benchmark Stability Report

Generated across 3 seeds × 3 critics (9 runs total).

## Per-Critic Stability

| Critic | Harsh Mean | Harsh StdDev | Baseline Mean | Delta Mean | Delta StdDev | W-L-T |
|--------|-----------|-------------|--------------|-----------|-------------|-------|
| next | 16.6 | ±0.97 | 2.1 | +14.5 | ±0.75 | 18-0-0 |
| react | 15.6 | ±0.67 | 1.7 | +13.9 | ±1.0 | 18-0-0 |
| react-native | 14.7 | ±0.35 | 1.0 | +13.7 | ±0.49 | 18-0-0 |

## Per-Seed Harsh Scores

| Critic | Seed 1 | Seed 2 | Seed 3 | StdDev |
|--------|--------|--------|--------|--------|
| next | 15.8 | 16.4 | 17.7 | ±0.97 |
| react | 16.2 | 15.8 | 14.9 | ±0.67 |
| react-native | 15.1 | 14.4 | 14.7 | ±0.35 |

## Rank Stability

- Seed 1 ranking: react > next > react-native
- Seed 2 ranking: next > react > react-native
- Seed 3 ranking: next > react > react-native
- Top critic stable across all seeds: NO
- Full ranking stable across all seeds: NO

## Overall Composite (All 9 Runs)

- Mean composite harsh: 15.6
- Mean composite baseline: 1.6
- Mean composite delta: +14.0
- Aggregate W-L-T across all 9 runs: 54-0-0

## Recommendations

- Best-performing critic: **next** (mean harsh 16.6, delta +14.5)
- Rank stability: PARTIAL - review seed variance before promoting to default
- Recommendation: keep specialized critics rather than collapsing to a single JS critic.
  Delta advantage (+14.0 mean) confirms specialization carries measurable signal.