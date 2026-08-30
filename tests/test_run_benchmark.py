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


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_benchmark


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def catalog_from_rules(data):
    rules = data["rules"]
    return {
        "by_category": {rule["category"]: next(item["id"] for item in rules if item["category"] == rule["category"]) for rule in rules},
        "rule_ids": {rule["id"] for rule in rules},
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
        self.root_patch = patch.object(run_benchmark, "REPO_ROOT", self.repo)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def write_inputs(self):
        (self.repo / "scripts").mkdir()
        (self.repo / "scripts/run_benchmark.py").write_text((SCRIPTS / "run_benchmark.py").read_text())
        skill = self.repo / run_benchmark.SKILL_PATHS[self.critic]
        skill.parent.mkdir(parents=True)
        skill.write_text("committed test skill\n")
        for path in run_benchmark.ROLE_TEMPLATE_PATHS.values():
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text((Path(__file__).resolve().parents[1] / path).read_text())
        rules = self.repo / "research/benchmarks/rules/react.yaml"
        rules.parent.mkdir(parents=True)
        rules.write_text("rules:\n  - {id: react.hook-correctness, category: hook-correctness}\n  - {id: react.other, category: other}\n")
        fixture_dir = self.repo / "research/benchmarks/fixtures/react"
        fixture_dir.mkdir(parents=True)
        fixtures = []
        for number in range(1, 9):
            code = "\n".join([f"const bad{number} = true;"] + [f"const decoy{number}_{i} = false;" for i in range(1, 25)])
            fixture = {"id": f"react-{number:02d}", "description": "PRIVATE_GOLD_SENTINEL", "code": code, "issues": [{"severity": "MAJOR", "category": "hook-correctness", "description": "PRIVATE_GOLD_SENTINEL", "evidence": f"const bad{number} = true;", "expected_checks": ["hook-correctness"]}]}
            fixtures.append(fixture)
            (fixture_dir / f"fixture-{number:02d}.yaml").write_text(yaml.safe_dump(fixture))
        git(self.repo, "init")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "Test")
        return fixtures

    def commit(self, message):
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", message)
        return git(self.repo, "rev-parse", "HEAD")

    def inputs(self):
        catalog = {"by_category": {"hook-correctness": "react.hook-correctness", "other": "react.other"}, "rule_ids": {"react.hook-correctness", "react.other"}}
        migrated = [run_benchmark.migrate_fixture(fixture, catalog) for fixture in self.fixtures]
        skill = "committed test skill\n"
        templates = {role: (self.repo / path).read_bytes() for role, path in run_benchmark.ROLE_TEMPLATE_PATHS.items()}
        return catalog, migrated, skill, templates

    def run_config(self, migrated, templates):
        config = {"schema_version": 1, "run_id": self.run_id, "critic": self.critic, "custody_classification": run_benchmark.CUSTODY_CLASSIFICATION, "provider": "self-attested", "model": "test-model", "runtime": "test-runtime", "parameters": {"temperature": 0}, "tools": [], "input_commit": self.input_commit, "fixture_ids": [item["id"] for item in migrated], "skill_sha256": run_benchmark.text_hash("committed test skill\n"), "rule_catalog_sha256": run_benchmark.bytes_hash((self.repo / "research/benchmarks/rules/react.yaml").read_bytes()), "scorer_id": run_benchmark.SCORER_ID, "scorer_version": run_benchmark.SCORER_VERSION, "template_hashes": {role: run_benchmark.bytes_hash(raw) for role, raw in templates.items()}, "public_fixture_hashes": {item["id"]: item["public_hash"] for item in migrated}, "gold_fixture_hashes": {item["id"]: item["gold_hash"] for item in migrated}}
        return config

    def capture_record(self, fixture, role, config_sha, catalog, templates, findings=None, response=None):
        prompt = run_benchmark.render_prompt(role, fixture, catalog, "committed test skill\n", templates)
        findings = findings if findings is not None else []
        response = response if response is not None else json.dumps({"findings": findings}, allow_nan=False)
        return {"schema_version": 4, "run_id": self.run_id, "critic": self.critic, "fixture_id": fixture["id"], "role": role, "run_config_sha256": config_sha, "rendered_prompt": prompt, "prompt_sha256": run_benchmark.text_hash(prompt), "response": response, "response_sha256": run_benchmark.text_hash(response)}

    def write_run_and_captures(self):
        catalog, migrated, _, templates = self.inputs()
        root = self.repo / "research/benchmarks/captures/react" / self.run_id
        root.mkdir(parents=True)
        config_raw = json.dumps(self.run_config(migrated, templates), sort_keys=True, allow_nan=False).encode()
        (root / "run.json").write_bytes(config_raw)
        config_sha = run_benchmark.bytes_hash(config_raw)
        for fixture in migrated:
            gold = fixture["gold"][0]
            finding = {"rule_id": gold["rule_id"], "evidence_lines": gold["evidence_lines"], "assertion": "present"}
            for role, findings in (("candidate", [finding]), ("baseline", [])):
                record = self.capture_record(fixture, role, config_sha, catalog, templates, findings)
                (root / f"{fixture['id']}.{role}.json").write_text(json.dumps(record, allow_nan=False))

    def capture_file(self, fixture_id, role):
        return self.repo / "research/benchmarks/captures/react" / self.run_id / f"{fixture_id}.{role}.json"

    def execute_benchmark(self, results=None, commit=None, run_id=None, capture_root="research/benchmarks/captures"):
        return run_benchmark.run_model_benchmark(self.critic, commit or self.capture_commit, run_id or self.run_id, capture_root, results or self.repo / "results")


class ExactMetricTests(ExactBenchmarkRepo):
    def test_correct_rule_and_lines_produce_tp_and_primary_metrics(self):
        _, manifest_path = self.execute_benchmark()
        metrics = json.loads(manifest_path.read_text())["metrics"]
        self.assertEqual({"tp": 8, "fp": 0, "fn": 0}, {key: metrics["candidate"][key] for key in ("tp", "fp", "fn")})
        self.assertEqual(1.0, metrics["candidate"]["f1"])
        self.assertEqual(0.0, metrics["baseline"]["f1"])
        self.assertIn("UNAVAILABLE", metrics["candidate"]["clean_fixture_accuracy"])

    def test_unrelated_rule_or_wrong_lines_are_fp_and_fn(self):
        path = self.capture_file("react-01", "candidate")
        record = json.loads(path.read_text())
        record["response"] = json.dumps({"findings": [{"rule_id": "react.hook-correctness", "evidence_lines": [2], "assertion": "present"}]})
        record["response_sha256"] = run_benchmark.text_hash(record["response"])
        path.write_text(json.dumps(record))
        commit = self.commit("wrong lines")
        _, manifest_path = self.execute_benchmark(commit=commit)
        metrics = json.loads(manifest_path.read_text())["metrics"]["candidate"]
        self.assertEqual((7, 1, 1), (metrics["tp"], metrics["fp"], metrics["fn"]))

    def test_known_unrelated_rule_on_exact_lines_is_fp_and_fn(self):
        path = self.capture_file("react-01", "candidate")
        record = json.loads(path.read_text())
        record["response"] = json.dumps({"findings": [{"rule_id": "react.other", "evidence_lines": [1], "assertion": "present"}]})
        record["response_sha256"] = run_benchmark.text_hash(record["response"])
        path.write_text(json.dumps(record))
        commit = self.commit("unrelated rule")
        _, manifest_path = self.execute_benchmark(commit=commit)
        metrics = json.loads(manifest_path.read_text())["metrics"]["candidate"]
        self.assertEqual((7, 1, 1), (metrics["tp"], metrics["fp"], metrics["fn"]))

    def test_twenty_false_positives_penalize_precision_and_f1(self):
        fixture = self.fixtures[0]
        catalog, migrated, _, _ = self.inputs()
        gold = migrated[0]["gold"][0]
        findings = [{"rule_id": gold["rule_id"], "evidence_lines": [line], "assertion": "present"} for line in range(1, 22)]
        predicted = run_benchmark.validate_response(json.dumps({"findings": findings}), migrated[0], catalog)
        artifact = {"fixture_id": fixture["id"], "role": "candidate", "predicted": sorted(predicted), "gold": [(gold["rule_id"], tuple(gold["evidence_lines"]))]}
        metrics = run_benchmark.metric_summary([artifact], [migrated[0]], "candidate")
        self.assertEqual((1, 20, 0), (metrics["tp"], metrics["fp"], metrics["fn"]))
        self.assertLess(metrics["precision"], 0.1)
        self.assertLess(metrics["f1"], 0.1)


class ContractAndCustodyTests(ExactBenchmarkRepo):
    def test_not_present_and_extra_explanation_are_rejected(self):
        fixture = self.fixtures[0]
        catalog, migrated, _, _ = self.inputs()
        bad = {"findings": [{"rule_id": migrated[0]["gold"][0]["rule_id"], "evidence_lines": [1], "assertion": "not_present"}]}
        with self.assertRaises(run_benchmark.IntegrityError):
            run_benchmark.validate_response(json.dumps(bad), migrated[0], catalog)
        extra = {"findings": [{"rule_id": migrated[0]["gold"][0]["rule_id"], "evidence_lines": [1], "assertion": "present", "explanation": "forbidden"}]}
        with self.assertRaises(run_benchmark.IntegrityError):
            run_benchmark.validate_response(json.dumps(extra), migrated[0], catalog)

    def test_public_prompt_hides_private_sentinel_and_strips_comments(self):
        catalog, migrated, skill, templates = self.inputs()
        prompt = run_benchmark.render_prompt("candidate", migrated[0], catalog, skill, templates)
        self.assertNotIn("PRIVATE_GOLD_SENTINEL", prompt)
        self.assertNotIn("issues", prompt)
        self.assertNotIn("expected_checks", prompt)
        self.assertNotIn("//", run_benchmark.public_fixture(migrated[0])["source_lines"][0]["code"])

    def test_template_hashes_and_all_custody_hashes_are_manifested(self):
        _, manifest_path = self.execute_benchmark()
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual("complete\n", (manifest_path.parent / "COMPLETE").read_text())
        self.assertEqual(64, len(manifest["run_config"]["sha256"]))
        self.assertEqual(64, len(manifest["skill"]["sha256"]))
        self.assertEqual(64, len(manifest["rule_catalog"]["sha256"]))
        self.assertTrue(all(len(value["sha256"]) == 64 for value in manifest["templates"].values()))
        self.assertEqual(run_benchmark.bytes_hash((self.repo / run_benchmark.ROLE_TEMPLATE_PATHS["candidate"]).read_bytes()), manifest["templates"]["candidate"]["sha256"])
        self.assertTrue(all(len(item["public_sha256"]) == 64 and len(item["gold_sha256"]) == 64 for item in manifest["fixtures"]))
        self.assertTrue(all(len(item["rendered_prompt_sha256"]) == 64 and len(item["response_sha256"]) == 64 for item in manifest["capture_artifacts"]))

    def test_mixed_config_is_rejected_and_artifacts_do_not_inflate_windows(self):
        path = self.capture_file("react-01", "baseline")
        record = json.loads(path.read_text())
        record["run_config_sha256"] = "0" * 64
        path.write_text(json.dumps(record))
        mixed = self.commit("mixed config")
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark(commit=mixed)
        git(self.repo, "checkout", self.capture_commit, "--", str(path.relative_to(self.repo)))
        restored = self.commit("restore config")
        _, manifest_path = self.execute_benchmark(commit=restored)
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(16, manifest["capture_artifact_count"])
        self.assertEqual(36, manifest["jackknife_window_reference_count"])
        self.assertEqual(16, len({(item["fixture_id"], item["role"]) for item in manifest["capture_artifacts"]}))

    def test_commit_path_and_atomic_controls_remain_fail_closed(self):
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark(commit="HEAD")
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark(run_id="bad")
        results = self.repo / "results"
        with patch.object(run_benchmark.os, "replace", side_effect=OSError("fault")):
            with self.assertRaises(OSError):
                self.execute_benchmark(results)
        self.assertEqual([], list(results.glob("model-benchmark-*")))
        self.execute_benchmark(results)
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark(results)

    def test_empty_directory_and_symlink_bundle_collisions_are_rejected(self):
        results = self.repo / "collisions"
        bundle = results / f"model-benchmark-{self.critic}-{self.run_id}"
        bundle.mkdir(parents=True)
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark(results)
        bundle.rmdir()
        os.symlink("missing-target", bundle)
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark(results)

    def test_racing_bundle_creation_is_not_replaced(self):
        results = self.repo / "race"
        bundle = results / f"model-benchmark-{self.critic}-{self.run_id}"
        original_mkdir = Path.mkdir

        def create_collision(path, *args, **kwargs):
            if path == bundle:
                original_mkdir(path, *args, **kwargs)
            return original_mkdir(path, *args, **kwargs)

        with patch.object(Path, "mkdir", new=create_collision):
            with self.assertRaises(run_benchmark.IntegrityError):
                self.execute_benchmark(results)
        self.assertTrue(bundle.is_dir())
        self.assertEqual([], list(bundle.iterdir()))

    def test_annotated_tag_object_id_is_not_a_commit(self):
        git(self.repo, "tag", "-a", "capture-tag", "-m", "capture", self.capture_commit)
        tag_oid = git(self.repo, "rev-parse", "capture-tag")
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark(commit=tag_oid)

    def test_unrelated_capture_commit_is_rejected(self):
        unrelated = git(self.repo, "commit-tree", f"{self.capture_commit}^{{tree}}", "-m", "unrelated")
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark(commit=unrelated)

    def test_current_head_must_descend_from_capture_commit(self):
        git(self.repo, "checkout", "--detach", self.input_commit)
        self.assertEqual(self.input_commit, git(self.repo, "rev-parse", "HEAD"))
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark(commit=self.capture_commit)

    def test_mismatched_input_commit_hashes_are_rejected(self):
        skill = self.repo / run_benchmark.SKILL_PATHS[self.critic]
        skill.write_text("different committed skill\n")
        changed_input = self.commit("different input")
        config_path = self.repo / "research/benchmarks/captures/react" / self.run_id / "run.json"
        config = json.loads(config_path.read_text())
        config["input_commit"] = changed_input
        config_path.write_text(json.dumps(config, sort_keys=True, allow_nan=False))
        capture = self.commit("mismatched input authority")
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark(commit=capture)

    def test_symlink_and_gitlink_artifacts_are_rejected(self):
        path = self.capture_file("react-01", "candidate")
        path.unlink()
        os.symlink("react-01.baseline.json", path)
        symlink_commit = self.commit("symlink artifact")
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark(commit=symlink_commit)
        relative = str(path.relative_to(self.repo))
        git(self.repo, "rm", "--cached", relative)
        git(self.repo, "update-index", "--add", "--cacheinfo", f"160000,{self.capture_commit},{relative}")
        git(self.repo, "commit", "-m", "gitlink artifact")
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark(commit=git(self.repo, "rev-parse", "HEAD"))

    def test_dirty_scorer_and_dirty_fixture_fail_separately(self):
        scorer = self.repo / "scripts/run_benchmark.py"
        scorer.write_text("dirty\n")
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark()
        git(self.repo, "checkout", "--", "scripts/run_benchmark.py")
        fixture = self.repo / "research/benchmarks/fixtures/react/fixture-01.yaml"
        fixture.write_text(fixture.read_text() + "\n# dirty\n")
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark()

    def test_dirty_committed_skill_fails(self):
        skill = self.repo / run_benchmark.SKILL_PATHS[self.critic]
        skill.write_text(skill.read_text() + "dirty\n")
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark()

    def test_dirty_rule_catalog_fails(self):
        rules = self.repo / "research/benchmarks/rules/react.yaml"
        rules.write_text(rules.read_text() + "# dirty\n")
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark()

    def test_dirty_prompt_template_fails(self):
        template = self.repo / run_benchmark.ROLE_TEMPLATE_PATHS["candidate"]
        template.write_text(template.read_text() + "dirty\n")
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark()

    def test_run_and_capture_json_reject_duplicate_and_nonfinite_values(self):
        run_path = self.repo / "research/benchmarks/captures/react" / self.run_id / "run.json"
        capture_path = self.capture_file("react-01", "candidate")
        cases = [
            ("duplicate run key", run_path, lambda raw: raw[:-1] + ', "run_id": "duplicate"}'),
            ("nonfinite run value", run_path, lambda raw: raw.replace('"temperature": 0', '"temperature": NaN')),
            ("duplicate capture key", capture_path, lambda raw: raw[:-1] + ', "response": "{}"}'),
            ("nonfinite capture value", capture_path, lambda raw: raw.replace('"schema_version": 4', '"schema_version": Infinity')),
        ]
        for label, path, mutate in cases:
            raw = path.read_text()
            changed = mutate(raw)
            self.assertNotEqual(raw, changed, label)
            path.write_text(changed)
            commit = self.commit(label)
            with self.assertRaises(run_benchmark.IntegrityError):
                self.execute_benchmark(commit=commit)
            git(self.repo, "checkout", self.capture_commit, "--", str(path.relative_to(self.repo)))

    def test_late_invalid_and_traversal_leave_no_partial_bundle(self):
        path = self.capture_file("react-08", "baseline")
        record = json.loads(path.read_text())
        record["response"] = "not-json"
        record["response_sha256"] = run_benchmark.text_hash("not-json")
        path.write_text(json.dumps(record))
        bad = self.commit("late invalid")
        results = self.repo / "late-results"
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark(results, bad)
        self.assertFalse(results.exists())
        with self.assertRaises(run_benchmark.IntegrityError):
            self.execute_benchmark(self.repo / "escape-results", self.capture_commit, capture_root="../captures")


class RealRepoIntegrationTests(unittest.TestCase):
    def test_explicit_real_skill_paths_exist(self):
        root = Path(__file__).resolve().parents[1]
        expected = {"react": ".claude/skills/react-critic/SKILL.md", "next": ".claude/skills/next-critic/SKILL.md", "react-native": ".claude/skills/react-native-critic/SKILL.md"}
        self.assertEqual(expected, run_benchmark.SKILL_PATHS)
        self.assertTrue(all((root / path).is_file() for path in expected.values()))

    def test_real_catalogs_cover_real_fixture_categories(self):
        root = Path(__file__).resolve().parents[1]
        for critic in run_benchmark.SKILL_PATHS:
            catalog = yaml.safe_load((root / f"research/benchmarks/rules/{critic}.yaml").read_text())
            categories = {rule["category"] for rule in catalog["rules"]}
            fixture_categories = {issue["category"] for path in (root / f"research/benchmarks/fixtures/{critic}").glob("*.yaml") for issue in yaml.safe_load(path.read_text())["issues"]}
            self.assertTrue(fixture_categories <= categories)

    def test_real_corpus_migrates_all_twenty_four_fixtures(self):
        root = Path(__file__).resolve().parents[1]
        total = 0
        for critic in run_benchmark.SKILL_PATHS:
            catalog = catalog_from_rules(yaml.safe_load((root / f"research/benchmarks/rules/{critic}.yaml").read_text()))
            paths = sorted((root / f"research/benchmarks/fixtures/{critic}").glob("*.yaml"))
            self.assertEqual(8, len(paths))
            for path in paths:
                migrated = run_benchmark.migrate_fixture(yaml.safe_load(path.read_text()), catalog)
                keys = {(item["rule_id"], tuple(item["evidence_lines"])) for item in migrated["gold"]}
                self.assertEqual(len(keys), len(migrated["gold"]), path.name)
                total += 1
        self.assertEqual(24, total)

    def test_fixture_migration_binds_private_gold_and_strips_answer_comments(self):
        fixture = {"id": "demo", "code": "const x = true; // answer\n", "issues": [{"severity": "MAJOR", "category": "hook-correctness", "description": "private", "evidence": "const x = true;", "expected_checks": []}]}
        migrated = run_benchmark.migrate_fixture(fixture, {"by_category": {"hook-correctness": "react.hook-correctness"}, "rule_ids": {"react.hook-correctness"}})
        gold = migrated["gold"][0]
        self.assertEqual(("react.hook-correctness", [1], "MAJOR", "hook-correctness"), (gold["rule_id"], gold["evidence_lines"], gold["severity"], gold["category"]))
        self.assertTrue(gold["issue_id"].startswith("issue-"))
        self.assertNotIn("answer", run_benchmark.public_fixture(migrated)["source_lines"][0]["code"])

    def test_legacy_reports_remain_rejected(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("react-run-report.md", "next-run-report.md", "react-native-run-report.md", "stability-report.md"):
            self.assertTrue((root / "research/benchmarks/results" / name).read_text().startswith("# REJECTED-INTEGRITY"))


if __name__ == "__main__":
    unittest.main()
