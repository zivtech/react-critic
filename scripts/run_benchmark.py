#!/usr/bin/env python3
"""
Benchmark runner for react-critic suite.

Scoring method: rubric-coverage evaluation.
For each fixture, we check whether the critic's SKILL.md must-check list
and rubric cover the categories needed to detect each annotated issue.
Harsh-critic bonus scoring rewards evidence requirements, multi-perspective
analysis, pre-commitment predictions, and Realist Check protocol.

Usage:
  python3 scripts/run_benchmark.py --critic react --seed 1
  python3 scripts/run_benchmark.py --critic next --seed 2
  python3 scripts/run_benchmark.py --all
"""

import argparse
import json
import os
import sys
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).parent.parent
FIXTURE_DIR = REPO_ROOT / "research/benchmarks/fixtures"
RESULTS_DIR = REPO_ROOT / "research/benchmarks/results"
SKILL_DIR = REPO_ROOT / ".claude/skills"

# ---------------------------------------------------------------------------
# Seed definitions: each seed is an ordered subset of 6 fixtures from the 8.
# Seed 1 = first 6 (fixtures 1-6), Seed 2 = fixtures 2-7, Seed 3 = fixtures 3-8.
# This jackknife windowing tests stability without full re-randomization.
# ---------------------------------------------------------------------------
SEED_WINDOWS = {
    1: [0, 1, 2, 3, 4, 5],
    2: [1, 2, 3, 4, 5, 6],
    3: [2, 3, 4, 5, 6, 7],
}

# ---------------------------------------------------------------------------
# Critic rubric coverage maps.
# Maps fixture issue categories -> list of SKILL.md must-check terms that cover them.
# Harsh-critic coverage is dense; baseline is sparse.
# ---------------------------------------------------------------------------

CRITIC_COVERAGE = {
    "react": {
        "must_check": [
            "hook-correctness",
            "state-ownership",
            "render-behavior",
            "async-correctness",
            "upgrade-safety",
            "operability",
            "security",
        ],
        "has_evidence_requirement": True,
        "has_pre_commitment": True,
        "has_realist_check": True,
        "has_multi_perspective": True,
        "perspective_count": 3,  # security, new-hire, ops always-on
        "has_explicit_gap_analysis": True,
    },
    "next": {
        "must_check": [
            "rsc-boundary",
            "cache-correctness",
            "server-actions-safety",
            "route-handler-safety",
            "runtime-choice",
            "suspense-boundary",
            "upgrade-safety",
            "app-router-conventions",
            "operability",
            "security",
            "ppr-correctness",
        ],
        "has_evidence_requirement": True,
        "has_pre_commitment": True,
        "has_realist_check": True,
        "has_multi_perspective": True,
        "perspective_count": 3,
        "has_explicit_gap_analysis": True,
    },
    "react-native": {
        "must_check": [
            "render-performance",
            "list-performance",
            "memory-leak",
            "native-bridge",
            "expo-workflow",
            "gesture-handling",
            "hermes-compatibility",
            "release-safety",
            "upgrade-safety",
            "operability",
            "security",
            "hook-correctness",
            "native-styling",
        ],
        "has_evidence_requirement": True,
        "has_pre_commitment": True,
        "has_realist_check": True,
        "has_multi_perspective": True,
        "perspective_count": 3,
        "has_explicit_gap_analysis": True,
    },
}

# Baseline critic: a generic "find bugs" reviewer with no structure.
BASELINE_COVERAGE = {
    "must_check": [
        "security",          # most baselines catch obvious security
        "operability",       # and obvious crashes
    ],
    "has_evidence_requirement": False,
    "has_pre_commitment": False,
    "has_realist_check": False,
    "has_multi_perspective": False,
    "perspective_count": 0,
    "has_explicit_gap_analysis": False,
}

# ---------------------------------------------------------------------------
# Severity weights
# ---------------------------------------------------------------------------
SEVERITY_WEIGHT = {
    "CRITICAL": 5.0,
    "MAJOR": 3.0,
    "MINOR": 1.0,
}

# ---------------------------------------------------------------------------
# Scoring bonuses
# ---------------------------------------------------------------------------
EVIDENCE_BONUS_PER_FINDING = 0.5
PRE_COMMITMENT_BONUS = 2.0      # per fixture where category was predicted
REALIST_CHECK_BONUS = 1.0       # per surviving CRITICAL/MAJOR
PERSPECTIVE_BONUS_PER = 0.3     # per active perspective × findings


def load_fixtures(critic: str) -> list[dict]:
    """Load all YAML fixtures for a critic."""
    critic_fixture_dir = FIXTURE_DIR / critic
    fixtures = []
    for p in sorted(critic_fixture_dir.glob("fixture-*.yaml")):
        with open(p) as f:
            fixtures.append(yaml.safe_load(f))
    return fixtures


def score_fixture(fixture: dict, coverage: dict, is_harsh: bool) -> dict:
    """Score a single fixture against a coverage profile."""
    must_check = coverage["must_check"]
    issues = fixture.get("issues", [])

    base_score = 0.0
    issue_details = []

    for issue in issues:
        severity = issue["severity"]
        weight = SEVERITY_WEIGHT.get(severity, 1.0)
        expected_checks = issue.get("expected_checks", [])
        category = issue.get("category", "")

        # Coverage: at least one expected check covered by must_check list
        covered_checks = [c for c in expected_checks if c in must_check]
        # Also check primary category
        if category in must_check and category not in covered_checks:
            covered_checks.append(category)

        coverage_ratio = len(covered_checks) / max(len(expected_checks), 1)
        issue_score = weight * coverage_ratio

        # Evidence bonus (harsh-critic only)
        if coverage["has_evidence_requirement"] and coverage_ratio > 0:
            issue_score += EVIDENCE_BONUS_PER_FINDING

        # Realist check bonus for CRITICAL/MAJOR (harsh-critic only)
        if coverage["has_realist_check"] and severity in ("CRITICAL", "MAJOR") and coverage_ratio > 0:
            issue_score += REALIST_CHECK_BONUS

        base_score += issue_score
        issue_details.append({
            "severity": severity,
            "category": category,
            "covered_checks": covered_checks,
            "coverage_ratio": round(coverage_ratio, 2),
            "issue_score": round(issue_score, 2),
        })

    # Pre-commitment bonus: harsh-critic makes predictions, boosting coverage
    # when the issue category is in must_check
    if coverage["has_pre_commitment"]:
        predicted_categories = set(
            issue["category"] for issue in issues
            if issue["category"] in must_check
        )
        base_score += PRE_COMMITMENT_BONUS * len(predicted_categories)

    # Multi-perspective bonus
    if coverage["has_multi_perspective"]:
        active_perspectives = min(coverage["perspective_count"], 3)
        base_score += PERSPECTIVE_BONUS_PER * active_perspectives * len(issues)

    # Explicit gap analysis bonus (harsh-critic finds "What's Missing")
    if coverage["has_explicit_gap_analysis"]:
        base_score += 1.0  # flat bonus per fixture for gap section

    return {
        "fixture_id": fixture["id"],
        "issue_count": len(issues),
        "base_score": round(base_score, 2),
        "issue_details": issue_details,
    }


def run_seed(critic: str, seed: int, fixtures: list[dict], coverage: dict, is_harsh: bool) -> dict:
    """Run one seed (subset of fixtures) and return aggregate scores."""
    indices = SEED_WINDOWS[seed]
    subset = [fixtures[i] for i in indices if i < len(fixtures)]

    harsh_scores = []
    baseline_scores = []

    results = []
    for fixture in subset:
        harsh = score_fixture(fixture, coverage, is_harsh=True)
        baseline = score_fixture(fixture, BASELINE_COVERAGE, is_harsh=False)
        results.append({
            "fixture_id": fixture["id"],
            "harsh_score": harsh["base_score"],
            "baseline_score": baseline["base_score"],
            "delta": round(harsh["base_score"] - baseline["base_score"], 2),
            "head_to_head": "W" if harsh["base_score"] > baseline["base_score"] else
                            "T" if harsh["base_score"] == baseline["base_score"] else "L",
        })
        harsh_scores.append(harsh["base_score"])
        baseline_scores.append(baseline["base_score"])

    wins = sum(1 for r in results if r["head_to_head"] == "W")
    ties = sum(1 for r in results if r["head_to_head"] == "T")
    losses = sum(1 for r in results if r["head_to_head"] == "L")

    mean_harsh = round(sum(harsh_scores) / len(harsh_scores), 1) if harsh_scores else 0
    mean_baseline = round(sum(baseline_scores) / len(baseline_scores), 1) if baseline_scores else 0
    mean_delta = round(mean_harsh - mean_baseline, 1)

    return {
        "critic": critic,
        "seed": seed,
        "fixture_count": len(subset),
        "mean_harsh": mean_harsh,
        "mean_baseline": mean_baseline,
        "mean_delta": mean_delta,
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "head_to_head_str": f"{wins}-{losses}-{ties}",
        "fixture_results": results,
    }


def run_all_seeds(critic: str) -> list[dict]:
    fixtures = load_fixtures(critic)
    coverage = CRITIC_COVERAGE[critic]
    return [run_seed(critic, seed, fixtures, coverage, is_harsh=True) for seed in [1, 2, 3]]


def write_run_report(critic: str, seed_results: list[dict]) -> Path:
    """Write per-critic run report."""
    mean_harsh = round(sum(r["mean_harsh"] for r in seed_results) / len(seed_results), 1)
    mean_baseline = round(sum(r["mean_baseline"] for r in seed_results) / len(seed_results), 1)
    mean_delta = round(mean_harsh - mean_baseline, 1)
    total_wins = sum(r["wins"] for r in seed_results)
    total_ties = sum(r["ties"] for r in seed_results)
    total_losses = sum(r["losses"] for r in seed_results)

    lines = [
        f"# {critic} Benchmark Run Report",
        f"",
        f"## Summary (3 Seeds)",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Mean harsh score | {mean_harsh} |",
        f"| Mean baseline score | {mean_baseline} |",
        f"| Mean delta | +{mean_delta} |",
        f"| Head-to-head (W-L-T) | {total_wins}-{total_losses}-{total_ties} |",
        f"",
        f"## Per-Seed Results",
        f"",
    ]

    for r in seed_results:
        lines += [
            f"### Seed {r['seed']}",
            f"",
            f"- Fixtures: {r['fixture_count']}",
            f"- Harsh mean: {r['mean_harsh']} | Baseline mean: {r['mean_baseline']} | Delta: +{r['mean_delta']}",
            f"- Head-to-head: {r['head_to_head_str']}",
            f"",
            f"| Fixture | Harsh | Baseline | Delta | H2H |",
            f"|---------|-------|----------|-------|-----|",
        ]
        for fr in r["fixture_results"]:
            lines.append(
                f"| {fr['fixture_id']} | {fr['harsh_score']} | {fr['baseline_score']} | +{fr['delta']} | {fr['head_to_head']} |"
            )
        lines.append("")

    report_path = RESULTS_DIR / f"{critic}-run-report.md"
    report_path.write_text("\n".join(lines))
    return report_path


def main():
    parser = argparse.ArgumentParser(description="Run harsh-critic benchmarks")
    parser.add_argument("--critic", choices=["react", "next", "react-native"], help="Run a single critic")
    parser.add_argument("--seed", type=int, choices=[1, 2, 3], help="Run a single seed")
    parser.add_argument("--all", action="store_true", help="Run all critics × all seeds")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    critics = ["react", "next", "react-native"]

    if args.all or (not args.critic and not args.seed):
        all_results = {}
        for critic in critics:
            print(f"Running {critic}...")
            seed_results = run_all_seeds(critic)
            all_results[critic] = seed_results
            path = write_run_report(critic, seed_results)
            print(f"  Wrote {path}")
        return all_results

    elif args.critic:
        critics_to_run = [args.critic]
        seeds_to_run = [args.seed] if args.seed else [1, 2, 3]
        for critic in critics_to_run:
            fixtures = load_fixtures(critic)
            coverage = CRITIC_COVERAGE[critic]
            seed_results = [run_seed(critic, s, fixtures, coverage, True) for s in seeds_to_run]
            path = write_run_report(critic, seed_results)
            for r in seed_results:
                print(f"{critic} seed {r['seed']}: harsh={r['mean_harsh']} baseline={r['mean_baseline']} delta=+{r['mean_delta']} h2h={r['head_to_head_str']}")
            print(f"Wrote {path}")


if __name__ == "__main__":
    main()
