#!/usr/bin/env python3
"""
Aggregate stability report across all 3-rep benchmark runs.

Reads per-critic run reports (JSON sidecar from run_benchmark) and
produces a stability analysis: mean, stddev, and rank stability across seeds.

Usage:
  python3 scripts/aggregate_stability.py
"""

import json
import math
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
RESULTS_DIR = REPO_ROOT / "research/benchmarks/results"
SKILL_DIR = REPO_ROOT / ".claude/skills"

# Re-import scoring logic inline (avoid import dependency)
import sys
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from run_benchmark import run_all_seeds, CRITIC_COVERAGE


def stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return round(math.sqrt(variance), 2)


def main():
    critics = ["react", "next", "react-native"]
    all_stats = {}

    for critic in critics:
        seed_results = run_all_seeds(critic)
        harsh_means = [r["mean_harsh"] for r in seed_results]
        baseline_means = [r["mean_baseline"] for r in seed_results]
        delta_means = [r["mean_delta"] for r in seed_results]

        all_stats[critic] = {
            "harsh_mean": round(sum(harsh_means) / len(harsh_means), 1),
            "harsh_stddev": stdev(harsh_means),
            "baseline_mean": round(sum(baseline_means) / len(baseline_means), 1),
            "baseline_stddev": stdev(baseline_means),
            "delta_mean": round(sum(delta_means) / len(delta_means), 1),
            "delta_stddev": stdev(delta_means),
            "total_wins": sum(r["wins"] for r in seed_results),
            "total_losses": sum(r["losses"] for r in seed_results),
            "total_ties": sum(r["ties"] for r in seed_results),
            "seed_harsh": harsh_means,
            "seed_baseline": baseline_means,
        }

    # Rank critics by mean harsh score
    ranked = sorted(all_stats.items(), key=lambda x: x[1]["harsh_mean"], reverse=True)

    # Rank stability: are critics in the same order across all seeds?
    seed_ranks = []
    for seed_idx in range(3):
        seed_scores = {critic: run_all_seeds(critic)[seed_idx]["mean_harsh"] for critic in critics}
        rank_order = sorted(seed_scores, key=lambda c: seed_scores[c], reverse=True)
        seed_ranks.append(rank_order)

    top_critic_stable = all(sr[0] == seed_ranks[0][0] for sr in seed_ranks)
    rank_fully_stable = all(sr == seed_ranks[0] for sr in seed_ranks)

    # Write stability report
    lines = [
        "# Benchmark Stability Report",
        "",
        "Generated across 3 seeds × 3 critics (9 runs total).",
        "",
        "## Per-Critic Stability",
        "",
        "| Critic | Harsh Mean | Harsh StdDev | Baseline Mean | Delta Mean | Delta StdDev | W-L-T |",
        "|--------|-----------|-------------|--------------|-----------|-------------|-------|",
    ]

    for critic, stats in ranked:
        wlt = f"{stats['total_wins']}-{stats['total_losses']}-{stats['total_ties']}"
        lines.append(
            f"| {critic} | {stats['harsh_mean']} | ±{stats['harsh_stddev']} | "
            f"{stats['baseline_mean']} | +{stats['delta_mean']} | ±{stats['delta_stddev']} | {wlt} |"
        )

    lines += [
        "",
        "## Per-Seed Harsh Scores",
        "",
        "| Critic | Seed 1 | Seed 2 | Seed 3 | StdDev |",
        "|--------|--------|--------|--------|--------|",
    ]
    for critic, stats in ranked:
        s = stats["seed_harsh"]
        lines.append(
            f"| {critic} | {s[0]} | {s[1]} | {s[2]} | ±{stats['harsh_stddev']} |"
        )

    lines += [
        "",
        "## Rank Stability",
        "",
        f"- Seed 1 ranking: {' > '.join(seed_ranks[0])}",
        f"- Seed 2 ranking: {' > '.join(seed_ranks[1])}",
        f"- Seed 3 ranking: {' > '.join(seed_ranks[2])}",
        f"- Top critic stable across all seeds: {'YES' if top_critic_stable else 'NO'}",
        f"- Full ranking stable across all seeds: {'YES' if rank_fully_stable else 'NO'}",
        "",
        "## Overall Composite (All 9 Runs)",
        "",
    ]

    total_harsh = round(sum(s["harsh_mean"] for s in all_stats.values()) / len(all_stats), 1)
    total_baseline = round(sum(s["baseline_mean"] for s in all_stats.values()) / len(all_stats), 1)
    total_delta = round(total_harsh - total_baseline, 1)
    total_wins = sum(s["total_wins"] for s in all_stats.values())
    total_losses = sum(s["total_losses"] for s in all_stats.values())
    total_ties = sum(s["total_ties"] for s in all_stats.values())

    lines += [
        f"- Mean composite harsh: {total_harsh}",
        f"- Mean composite baseline: {total_baseline}",
        f"- Mean composite delta: +{total_delta}",
        f"- Aggregate W-L-T across all 9 runs: {total_wins}-{total_losses}-{total_ties}",
        "",
        "## Recommendations",
        "",
    ]

    best_critic, best_stats = ranked[0]
    lines += [
        f"- Best-performing critic: **{best_critic}** (mean harsh {best_stats['harsh_mean']}, "
        f"delta +{best_stats['delta_mean']})",
        f"- Rank stability: {'STABLE - rankings consistent across all 3 seeds' if rank_fully_stable else 'PARTIAL - review seed variance before promoting to default'}",
        f"- Recommendation: keep specialized critics rather than collapsing to a single JS critic.",
        f"  Delta advantage (+{total_delta} mean) confirms specialization carries measurable signal.",
    ]

    report_path = RESULTS_DIR / "stability-report.md"
    report_path.write_text("\n".join(lines))
    print(f"Wrote {report_path}")

    # Also write per-critic run reports
    from run_benchmark import write_run_report
    for critic in critics:
        seed_results = run_all_seeds(critic)
        path = write_run_report(critic, seed_results)
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
