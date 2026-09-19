import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_benchmark
import benchmark_scorer


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def catalog_from_rules(data):
    rules = data["rules"]
    return {"rules": rules, "by_id": {rule["id"]: rule["category"] for rule in rules}, "rule_ids": {rule["id"] for rule in rules}}


def rule_data():
    return {
        "schema_version": 2,
        "rules": [
            {"id": "react.hook-correctness", "category": "hook-correctness", "title": "Hook correctness", "definition": "Find incorrect hook dependencies.", "exclusions": []},
            {"id": "react.other", "category": "other", "title": "Other correctness", "definition": "Find other concrete defects.", "exclusions": ["Do not report style preferences."]},
        ],
    }


def fixture_record(number=1, *, clean=False):
    code = "\n".join([
        'const endpoint = "https://example.test"; // preserve this exact source',
        f"const bad{number} = true;",
        f"const alternate{number} = true;",
        *[f"const decoy{number}_{index} = false;" for index in range(1, 25)],
    ])
    issues = [] if clean else [{
        "id": f"react-{number:02d}-missing-dependency",
        "rule_id": "react.hook-correctness",
        "category": "hook-correctness",
        "severity": "MAJOR",
        "description": "PRIVATE_GOLD_SENTINEL",
        "evidence_spans": [
            {"lines": [2], "rationale": "Primary exact evidence."},
            {"lines": [3], "rationale": "Accepted alternate exact evidence."},
        ],
    }]
    return {
        "schema_version": 2,
        "id": f"react-{number:02d}",
        "category": "hook-correctness",
        "description": "PRIVATE_INVENTORY_SENTINEL",
        "intentional_clean": clean,
        "public": {
            "file_path": f"src/Fixture{number}.jsx",
            "language": "jsx",
            "frameworks": {"react": "18.3.1"},
            "runtime": "browser",
            "assumptions": ["Imports are supplied."],
            "requirements": [],
            "code": code,
        },
        "metadata": {
            "provenance": {"kind": "synthetic", "origin": "unit-test fixture", "revision_reason": "Exercise schema and scorer contracts."},
            "difficulty": "ADVERSARIAL" if clean else "HAS-BUGS",
            "domains": ["hooks"],
            "adjudication": {
                "status": "reviewed",
                "method": "source-review-and-official-documentation",
                "reviewer": "test-suite",
                "reviewed_on": "2026-09-19",
                "sources": [{"url": "https://react.dev/reference/react/useEffect", "supports": "Effect dependency semantics."}],
                "notes": "Synthetic contract fixture.",
                "excluded_claims": [],
            },
        },
        "issues": issues,
    }


class ExactBenchmarkRepo(unittest.TestCase):
    critic = "react"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.run_id = str(uuid.uuid4())
        self.fixtures = self.write_inputs()
        self.input_commit = self.commit("inputs")
        self.write_run_and_captures()
        self.capture_commit = self.commit("captures")
        self.root_patch = patch.object(benchmark_scorer, "REPO_ROOT", self.repo)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def write_inputs(self):
        (self.repo / "scripts").mkdir()
        for name in ("run_benchmark.py", "benchmark_scorer.py"):
            (self.repo / "scripts" / name).write_bytes((SCRIPTS / name).read_bytes())
        skill = self.repo / run_benchmark.SKILL_PATHS[self.critic]
        skill.parent.mkdir(parents=True)
        skill.write_text("committed test skill\n")
        for path in run_benchmark.ROLE_TEMPLATE_PATHS.values():
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / path).read_bytes())
        rules = self.repo / "research/benchmarks/rules/react.yaml"
        rules.parent.mkdir(parents=True)
        rules.write_text(yaml.safe_dump(rule_data(), sort_keys=False))
        fixture_dir = self.repo / "research/benchmarks/fixtures/react"
        fixture_dir.mkdir(parents=True)
        fixtures = [fixture_record(number) for number in range(1, 9)]
        for number, fixture in enumerate(fixtures, 1):
            (fixture_dir / f"fixture-{number:02d}.yaml").write_text(yaml.safe_dump(fixture, sort_keys=False))
        git(self.repo, "init")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "Test")
        return fixtures

    def commit(self, message):
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", message)
        return git(self.repo, "rev-parse", "HEAD")

    def inputs(self):
        catalog = catalog_from_rules(rule_data())
        migrated = [run_benchmark.migrate_fixture(fixture, catalog) for fixture in self.fixtures]
        templates = {role: (self.repo / path).read_bytes() for role, path in run_benchmark.ROLE_TEMPLATE_PATHS.items()}
        return catalog, migrated, "committed test skill\n", templates

    def run_config(self, migrated, templates):
        return {
            "schema_version": 2,
            "run_id": self.run_id,
            "critic": self.critic,
            "treatment": run_benchmark.TREATMENT,
            "custody_classification": run_benchmark.CUSTODY_CLASSIFICATION,
            "provider": "self-attested",
            "model": "test-model",
            "runtime": "test-runtime",
            "parameters": {"temperature": 0},
            "tools": [],
            "input_commit": self.input_commit,
            "fixture_ids": [item["id"] for item in migrated],
            "skill_sha256": run_benchmark.text_hash("committed test skill\n"),
            "rule_catalog_sha256": run_benchmark.bytes_hash((self.repo / "research/benchmarks/rules/react.yaml").read_bytes()),
            "scorer_id": run_benchmark.SCORER_ID,
            "scorer_version": run_benchmark.SCORER_VERSION,
            "scorer_sha256": run_benchmark.bytes_hash((self.repo / run_benchmark.SCORER_PATH).read_bytes()),
            "template_hashes": {role: run_benchmark.bytes_hash(raw) for role, raw in templates.items()},
            "public_fixture_hashes": {item["id"]: item["public_hash"] for item in migrated},
            "gold_fixture_hashes": {item["id"]: item["gold_hash"] for item in migrated},
        }

    def capture_record(self, fixture, role, config_sha, catalog, templates, findings=None, response=None):
        prompt = run_benchmark.render_prompt(role, fixture, catalog, "committed test skill\n", templates)
        response = response if response is not None else json.dumps({"findings": findings if findings is not None else []}, allow_nan=False)
        return {"schema_version": 5, "run_id": self.run_id, "critic": self.critic, "fixture_id": fixture["id"], "role": role, "run_config_sha256": config_sha, "rendered_prompt": prompt, "prompt_sha256": run_benchmark.text_hash(prompt), "response": response, "response_sha256": run_benchmark.text_hash(response)}

    def write_run_and_captures(self):
        catalog, migrated, _, templates = self.inputs()
        root = self.repo / "research/benchmarks/captures/react" / self.run_id
        root.mkdir(parents=True)
        config_raw = json.dumps(self.run_config(migrated, templates), sort_keys=True, allow_nan=False).encode()
        (root / "run.json").write_bytes(config_raw)
        config_sha = run_benchmark.bytes_hash(config_raw)
        for fixture in migrated:
            gold = fixture["gold"][0]
            finding = {"rule_id": gold["rule_id"], "evidence_lines": gold["accepted_evidence_lines"][0], "assertion": "present"}
            for role, findings in (("candidate", [finding]), ("baseline", [])):
                record = self.capture_record(fixture, role, config_sha, catalog, templates, findings)
                (root / f"{fixture['id']}.{role}.json").write_text(json.dumps(record, allow_nan=False))

    def capture_file(self, fixture_id, role):
        return self.repo / "research/benchmarks/captures/react" / self.run_id / f"{fixture_id}.{role}.json"

    def execute_benchmark(self, results=None, commit=None, run_id=None, capture_root="research/benchmarks/captures"):
        return run_benchmark.run_model_benchmark(self.critic, commit or self.capture_commit, run_id or self.run_id, capture_root, results or self.repo / "results")


class ExactMetricTests(ExactBenchmarkRepo):
    def test_correct_rule_and_lines_produce_primary_metrics(self):
        _, manifest_path = self.execute_benchmark()
        metrics = json.loads(manifest_path.read_text())["metrics"]
        self.assertEqual({"tp": 8, "fp": 0, "fn": 0}, {key: metrics["candidate"][key] for key in ("tp", "fp", "fn")})
        self.assertEqual(1.0, metrics["candidate"]["f1"])
        self.assertEqual(0.0, metrics["baseline"]["f1"])

    def test_alternative_evidence_span_matches_once(self):
        path = self.capture_file("react-01", "candidate")
        record = json.loads(path.read_text())
        record["response"] = json.dumps({"findings": [{"rule_id": "react.hook-correctness", "evidence_lines": [3], "assertion": "present"}]})
        record["response_sha256"] = run_benchmark.text_hash(record["response"])
        path.write_text(json.dumps(record))
        commit = self.commit("alternative evidence")
        _, manifest_path = self.execute_benchmark(commit=commit)
        metrics = json.loads(manifest_path.read_text())["metrics"]["candidate"]
        self.assertEqual((8, 0, 0), (metrics["tp"], metrics["fp"], metrics["fn"]))

    def test_two_alternatives_for_one_issue_penalize_surplus_prediction(self):
        path = self.capture_file("react-01", "candidate")
        record = json.loads(path.read_text())
        record["response"] = json.dumps({"findings": [
            {"rule_id": "react.hook-correctness", "evidence_lines": [2], "assertion": "present"},
            {"rule_id": "react.hook-correctness", "evidence_lines": [3], "assertion": "present"},
        ]})
        record["response_sha256"] = run_benchmark.text_hash(record["response"])
        path.write_text(json.dumps(record))
        commit = self.commit("surplus alternative")
        _, manifest_path = self.execute_benchmark(commit=commit)
        metrics = json.loads(manifest_path.read_text())["metrics"]["candidate"]
        self.assertEqual((8, 1, 0), (metrics["tp"], metrics["fp"], metrics["fn"]))

    def test_wrong_rule_or_wrong_lines_are_fp_and_fn(self):
        path = self.capture_file("react-01", "candidate")
        record = json.loads(path.read_text())
        record["response"] = json.dumps({"findings": [{"rule_id": "react.other", "evidence_lines": [2], "assertion": "present"}]})
        record["response_sha256"] = run_benchmark.text_hash(record["response"])
        path.write_text(json.dumps(record))
        commit = self.commit("wrong rule")
        _, manifest_path = self.execute_benchmark(commit=commit)
        metrics = json.loads(manifest_path.read_text())["metrics"]["candidate"]
        self.assertEqual((7, 1, 1), (metrics["tp"], metrics["fp"], metrics["fn"]))

    def test_twenty_false_positives_penalize_precision(self):
        catalog, migrated, _, _ = self.inputs()
        predictions = {("react.hook-correctness", (line,)) for line in range(2, 23)}
        artifact = {"fixture_id": "react-01", "role": "candidate", "predicted": sorted(predictions), "matched_predictions": [("react.hook-correctness", (2,))], "matched_issue_ids": [migrated[0]["gold"][0]["issue_id"]]}
        metrics = run_benchmark.metric_summary([artifact], [migrated[0]], "candidate")
        self.assertEqual((1, 20, 0), (metrics["tp"], metrics["fp"], metrics["fn"]))
        self.assertLess(metrics["precision"], 0.1)

    def test_clean_fixture_empty_prediction_has_exact_match_accuracy(self):
        fixture = run_benchmark.migrate_fixture(fixture_record(clean=True), catalog_from_rules(rule_data()))
        artifact = {"fixture_id": fixture["id"], "role": "candidate", "predicted": [], "matched_predictions": [], "matched_issue_ids": []}
        metrics = run_benchmark.metric_summary([artifact], [fixture], "candidate")
        self.assertEqual({"correct": 1, "total": 1, "accuracy": 1.0}, metrics["clean_fixture_accuracy"])
        self.assertEqual(1.0, metrics["per_fixture"][0]["f1"])


class SchemaAndPromptTests(unittest.TestCase):
    def setUp(self):
        self.catalog = catalog_from_rules(rule_data())

    def test_public_projection_preserves_source_and_hides_private_fields(self):
        fixture = run_benchmark.migrate_fixture(fixture_record(), self.catalog)
        public = run_benchmark.public_fixture(fixture)
        self.assertIn('https://example.test', public["source_lines"][0]["code"])
        self.assertIn("// preserve this exact source", public["source_lines"][0]["code"])
        self.assertNotIn("PRIVATE_GOLD_SENTINEL", json.dumps(public))
        self.assertNotIn("intentional_clean", public)
        self.assertNotIn("metadata", public)

    def test_missing_issues_and_clean_disagreement_are_rejected(self):
        missing = fixture_record(); missing.pop("issues")
        with self.assertRaises(run_benchmark.IntegrityError):
            run_benchmark.migrate_fixture(missing, self.catalog)
        disagreement = fixture_record(); disagreement["intentional_clean"] = True
        with self.assertRaises(run_benchmark.IntegrityError):
            run_benchmark.migrate_fixture(disagreement, self.catalog)

    def test_bad_severity_rule_category_and_ambiguous_span_are_rejected(self):
        severity = fixture_record(); severity["issues"][0]["severity"] = "UNKNOWN"
        mismatch = fixture_record(); mismatch["issues"][0]["category"] = "other"
        ambiguous = fixture_record(); second = copy.deepcopy(ambiguous["issues"][0]); second["id"] = "second"; ambiguous["issues"].append(second)
        for fixture in (severity, mismatch, ambiguous):
            with self.assertRaises(run_benchmark.IntegrityError):
                run_benchmark.migrate_fixture(fixture, self.catalog)

    def test_duplicate_yaml_keys_and_unsafe_paths_are_rejected(self):
        with self.assertRaises(run_benchmark.IntegrityError):
            run_benchmark.strict_yaml_load("schema_version: 2\nschema_version: 2\n", "fixture")
        for path in ("../captures", "a//b", "a/./b", "a\\b"):
            with self.assertRaises(run_benchmark.IntegrityError):
                run_benchmark.safe_repo_path(path)

    def test_catalog_definitions_are_public_for_both_roles(self):
        fixture = run_benchmark.migrate_fixture(fixture_record(), self.catalog)
        templates = {role: (ROOT / path).read_bytes() for role, path in run_benchmark.ROLE_TEMPLATE_PATHS.items()}
        candidate = run_benchmark.render_prompt("candidate", fixture, self.catalog, "skill text", templates)
        baseline = run_benchmark.render_prompt("baseline", fixture, self.catalog, "skill text", templates)
        for prompt in (candidate, baseline):
            self.assertIn("Find incorrect hook dependencies", prompt)
            self.assertIn("Return strict JSON", prompt)
        self.assertIn("skill text", candidate)
        self.assertNotIn("skill text", baseline)


class ContractAndCustodyTests(ExactBenchmarkRepo):
    def test_not_present_extra_explanation_and_duplicate_findings_are_rejected(self):
        catalog, migrated, _, _ = self.inputs()
        cases = [
            {"findings": [{"rule_id": "react.hook-correctness", "evidence_lines": [2], "assertion": "not_present"}]},
            {"findings": [{"rule_id": "react.hook-correctness", "evidence_lines": [2], "assertion": "present", "explanation": "forbidden"}]},
            {"findings": [{"rule_id": "react.hook-correctness", "evidence_lines": [2], "assertion": "present"}] * 2},
        ]
        for payload in cases:
            with self.assertRaises(run_benchmark.IntegrityError):
                run_benchmark.validate_response(json.dumps(payload), migrated[0], catalog)

    def test_manifest_records_verified_scorer_and_custody_hashes(self):
        _, manifest_path = self.execute_benchmark()
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual("complete\n", (manifest_path.parent / "COMPLETE").read_text())
        self.assertEqual(run_benchmark.TREATMENT, manifest["treatment"])
        self.assertEqual(run_benchmark.bytes_hash((self.repo / run_benchmark.SCORER_PATH).read_bytes()), manifest["scoring_code"]["sha256"])
        self.assertEqual("verified-working-tree-unit-path", manifest["scoring_code"]["execution"])
        self.assertTrue(all(len(item["public_sha256"]) == 64 and len(item["gold_sha256"]) == 64 for item in manifest["fixtures"]))

    def test_mixed_config_and_nonempty_tools_are_rejected(self):
        path = self.repo / "research/benchmarks/captures/react" / self.run_id / "run.json"
        for label, mutate in (("mixed config", lambda config: config.update(skill_sha256="0" * 64)), ("tools", lambda config: config.update(tools=["browser"]))):
            config = json.loads(path.read_text()); mutate(config); path.write_text(json.dumps(config, sort_keys=True))
            commit = self.commit(label)
            with self.assertRaises(run_benchmark.IntegrityError):
                self.execute_benchmark(commit=commit)
            path.write_bytes(git(self.repo, "show", f"{self.capture_commit}:{path.relative_to(self.repo)}").encode())

    def test_invalid_commit_run_id_and_traversal_fail(self):
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark(commit="HEAD")
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark(run_id="bad")
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark(capture_root="../captures")

    def test_publication_failure_preserves_incomplete_reservation(self):
        results = self.repo / "fault-results"
        with patch.object(run_benchmark.os, "replace", side_effect=OSError("fault")):
            with self.assertRaises(OSError):
                self.execute_benchmark(results)
        bundle = results / f"model-benchmark-{self.critic}-{self.run_id}"
        self.assertTrue(bundle.is_dir())
        self.assertFalse((bundle / "COMPLETE").exists())
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark(results)

    def test_substituted_bundle_is_never_deleted_or_completed(self):
        results = self.repo / "substitution-results"
        bundle = results / f"model-benchmark-{self.critic}-{self.run_id}"
        moved = results / "original-reservation"
        original_replace = os.replace
        replaced = False

        def substitute(source, destination, *args, **kwargs):
            nonlocal replaced
            if not replaced:
                replaced = True
                original_replace(bundle, moved)
                bundle.mkdir()
                (bundle / "other-writer.txt").write_text("preserve\n")
                raise OSError("substituted")
            return original_replace(source, destination, *args, **kwargs)

        with patch.object(run_benchmark.os, "replace", side_effect=substitute):
            with self.assertRaises(OSError):
                self.execute_benchmark(results)
        self.assertEqual("preserve\n", (bundle / "other-writer.txt").read_text())
        self.assertFalse((bundle / "COMPLETE").exists())
        self.assertTrue(moved.is_dir())

    def test_bundle_substituted_before_open_is_rejected_before_writes(self):
        results = self.repo / "pre-open-substitution-results"
        bundle = results / f"model-benchmark-{self.critic}-{self.run_id}"
        moved = results / "original-reservation"
        original_open = os.open
        replaced = False

        def substitute(path, flags, *args, **kwargs):
            nonlocal replaced
            if not replaced and Path(path) == bundle:
                replaced = True
                os.replace(bundle, moved)
                bundle.mkdir()
                (bundle / "other-writer.txt").write_text("preserve\n")
            return original_open(path, flags, *args, **kwargs)

        with patch.object(run_benchmark.os, "open", side_effect=substitute):
            with self.assertRaises(run_benchmark.IntegrityError):
                self.execute_benchmark(results)
        self.assertEqual("preserve\n", (bundle / "other-writer.txt").read_text())
        self.assertFalse((bundle / "COMPLETE").exists())
        self.assertEqual([], list(moved.iterdir()))

    def test_annotated_tag_and_unrelated_capture_commit_are_rejected(self):
        git(self.repo, "tag", "-a", "capture-tag", "-m", "capture", self.capture_commit)
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark(commit=git(self.repo, "rev-parse", "capture-tag"))
        unrelated = git(self.repo, "commit-tree", f"{self.capture_commit}^{{tree}}", "-m", "unrelated")
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark(commit=unrelated)

    def test_later_head_scorer_cannot_be_misreported_as_executed(self):
        scorer = self.repo / run_benchmark.SCORER_PATH
        original = scorer.read_bytes()
        scorer.write_bytes(original + b"\n# changed scorer\n")
        self.commit("changed scorer")
        scorer.write_bytes(original)
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark()

    def test_dirty_bootstrap_skill_fixture_rule_and_template_fail(self):
        paths = [
            self.repo / run_benchmark.BOOTSTRAP_PATH,
            self.repo / run_benchmark.SKILL_PATHS[self.critic],
            self.repo / "research/benchmarks/fixtures/react/fixture-01.yaml",
            self.repo / "research/benchmarks/rules/react.yaml",
            self.repo / run_benchmark.ROLE_TEMPLATE_PATHS["candidate"],
        ]
        for path in paths:
            original = path.read_bytes(); path.write_bytes(original + b"\n# dirty\n")
            with self.assertRaises(run_benchmark.IntegrityError):
                self.execute_benchmark()
            path.write_bytes(original)

    def test_run_and_capture_json_reject_duplicate_and_nonfinite_values(self):
        run_path = self.repo / "research/benchmarks/captures/react" / self.run_id / "run.json"
        capture_path = self.capture_file("react-01", "candidate")
        cases = [
            (run_path, lambda raw: raw[:-1] + ', "run_id": "duplicate"}'),
            (run_path, lambda raw: raw.replace('"temperature": 0', '"temperature": NaN')),
            (capture_path, lambda raw: raw[:-1] + ', "response": "{}"}'),
            (capture_path, lambda raw: raw.replace('"schema_version": 5', '"schema_version": Infinity')),
        ]
        for index, (path, mutate) in enumerate(cases):
            original = path.read_text(); path.write_text(mutate(original)); commit = self.commit(f"invalid json {index}")
            with self.assertRaises(run_benchmark.IntegrityError):
                self.execute_benchmark(commit=commit)
            path.write_text(original)

    def test_cli_bootstrap_executes_committed_blob_and_rejects_dirty_core(self):
        command = [sys.executable, str(self.repo / run_benchmark.BOOTSTRAP_PATH), "--help"]
        clean = subprocess.run(command, cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(0, clean.returncode, clean.stderr)
        scorer = self.repo / run_benchmark.SCORER_PATH
        scorer.write_text(scorer.read_text() + "\n# dirty\n")
        dirty = subprocess.run(command, cwd=self.repo, capture_output=True, text=True)
        self.assertNotEqual(0, dirty.returncode)
        self.assertIn("Refusing to execute dirty scorer", dirty.stderr)


class RealRepoIntegrationTests(unittest.TestCase):
    def test_real_catalogs_and_all_twenty_four_fixtures_validate(self):
        total = 0
        for critic in run_benchmark.SKILL_PATHS:
            rule_raw = (ROOT / f"research/benchmarks/rules/{critic}.yaml").read_bytes()
            with patch.object(benchmark_scorer, "read_regular_blob", return_value=(rule_raw, "f" * 40)):
                catalog, loaded_raw, _ = run_benchmark.load_rule_catalog("0" * 40, critic)
            self.assertEqual(rule_raw, loaded_raw)
            paths = sorted((ROOT / f"research/benchmarks/fixtures/{critic}").glob("*.yaml"))
            self.assertEqual(8, len(paths))
            for path in paths:
                run_benchmark.migrate_fixture(run_benchmark.strict_yaml_load(path.read_bytes(), path.name), catalog)
                total += 1
        self.assertEqual(24, total)

    def test_real_corpus_has_five_explicit_clean_controls(self):
        clean = []
        for critic in run_benchmark.SKILL_PATHS:
            for path in (ROOT / f"research/benchmarks/fixtures/{critic}").glob("*.yaml"):
                fixture = run_benchmark.strict_yaml_load(path.read_bytes(), path.name)
                if fixture["intentional_clean"]:
                    clean.append(fixture["id"])
        self.assertEqual(["next-02", "react-06", "rn-01", "rn-02", "rn-07"], sorted(clean))

    def test_corrected_real_gold_and_hermes_control_are_pinned(self):
        def fixture(group, number):
            path = ROOT / f"research/benchmarks/fixtures/{group}/fixture-{number:02d}.yaml"
            return run_benchmark.strict_yaml_load(path.read_bytes(), path.name)

        react_01 = fixture("react", 1)
        self.assertEqual(
            ["react-01-missing-page-dependency", "react-01-stale-response"],
            [issue["id"] for issue in react_01["issues"]],
        )
        self.assertEqual([[5, 7], [4, 5, 7]], [span["lines"] for span in react_01["issues"][1]["evidence_spans"]])
        self.assertEqual([[8]], [span["lines"] for span in fixture("react", 2)["issues"][0]["evidence_spans"]])
        next_03 = fixture("next", 3)
        self.assertEqual([[[4, 9]], [[6, 10]]], [[span["lines"] for span in issue["evidence_spans"]] for issue in next_03["issues"]])
        hermes = fixture("react-native", 7)
        self.assertEqual({"react-native": "0.66", "hermes": "0.9.0"}, hermes["public"]["frameworks"])

    def test_legacy_reports_remain_rejected(self):
        for name in ("react-run-report.md", "next-run-report.md", "react-native-run-report.md", "stability-report.md"):
            self.assertTrue((ROOT / "research/benchmarks/results" / name).read_text().startswith("# REJECTED-INTEGRITY"))


if __name__ == "__main__":
    unittest.main()
