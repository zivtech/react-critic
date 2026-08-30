#!/usr/bin/env python3
"""Exact structured defect-detection scoring from immutable Git artifacts."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

import yaml


REPO_ROOT = Path(__file__).parent.parent
FIXTURE_DIR = "research/benchmarks/fixtures"
RULE_DIR = "research/benchmarks/rules"
TEMPLATE_DIR = "research/benchmarks/templates"
CAPTURE_ROOT = "research/benchmarks/captures"
RESULTS_DIR = REPO_ROOT / "research/benchmarks/results"
SKILL_PATHS = {"react": ".claude/skills/react-critic/SKILL.md", "next": ".claude/skills/next-critic/SKILL.md", "react-native": ".claude/skills/react-native-critic/SKILL.md"}
ROLE_TEMPLATE_PATHS = {"candidate": f"{TEMPLATE_DIR}/candidate.txt", "baseline": f"{TEMPLATE_DIR}/baseline.txt"}
JACKKNIFE_WINDOWS = {1: [0, 1, 2, 3, 4, 5], 2: [1, 2, 3, 4, 5, 6], 3: [2, 3, 4, 5, 6, 7]}
SEVERITY_WEIGHT = {"CRITICAL": 5.0, "MAJOR": 3.0, "MINOR": 1.0}
SCORER_ID = "exact-rule-line-defect-detection"
SCORER_VERSION = "4"
CUSTODY_CLASSIFICATION = "self-attested-repo-native"
HASH_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
RUN_ID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z")


class IntegrityError(ValueError):
    """Raised when exact scoring or artifact custody cannot be proven."""


def require_hash(value: object, label: str) -> str:
    if not isinstance(value, str) or not HASH_RE.fullmatch(value):
        raise IntegrityError(f"{label} must be a full lowercase SHA-256")
    return value


def canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def bytes_hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def text_hash(value: str) -> str:
    return bytes_hash(value.encode())


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise IntegrityError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_nonfinite(value: str) -> None:
    raise IntegrityError(f"Non-finite JSON number: {value}")


def strict_json_loads(value: str | bytes, label: str) -> object:
    try:
        return json.loads(value, object_pairs_hook=reject_duplicate_keys, parse_constant=reject_nonfinite)
    except IntegrityError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IntegrityError(f"{label} is not strict UTF-8 JSON") from error


def git_bytes(*args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True)
    if result.returncode:
        raise IntegrityError(result.stderr.decode().strip() or "Git command failed")
    return result.stdout


def git_text(*args: str) -> str:
    return git_bytes(*args).decode()


def head_commit() -> str:
    return git_text("rev-parse", "HEAD").strip()


def safe_repo_path(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise IntegrityError(f"Unsafe repo-relative path: {value!r}")
    return path.as_posix()


def verify_commit(value: str, flag: str = "--capture-commit") -> str:
    if not COMMIT_RE.fullmatch(value):
        raise IntegrityError(f"{flag} must be an exact 40-character lowercase SHA-1")
    if git_text("cat-file", "-t", value).strip() != "commit":
        raise IntegrityError(f"{flag} must identify a commit object, not a tag or another object")
    return value


def tree_entry(commit: str, path: str) -> tuple[str, str, str]:
    output = git_text("ls-tree", commit, "--", path).strip()
    if not output or "\t" not in output:
        raise IntegrityError(f"Missing committed path: {path}")
    metadata, found = output.split("\t", 1)
    parts = metadata.split()
    if len(parts) != 3 or found != path:
        raise IntegrityError(f"Ambiguous committed path: {path}")
    return parts[0], parts[1], parts[2]


def read_regular_blob(commit: str, path: str) -> tuple[bytes, str]:
    parts = safe_repo_path(path).split("/")
    for index in range(1, len(parts)):
        mode, kind, _ = tree_entry(commit, "/".join(parts[:index]))
        if mode != "040000" or kind != "tree":
            raise IntegrityError(f"Path has a non-tree component: {path}")
    mode, kind, oid = tree_entry(commit, path)
    if mode != "100644" or kind != "blob":
        raise IntegrityError(f"Path must be a regular blob, not mode {mode}: {path}")
    return git_bytes("show", f"{commit}:{path}"), oid


def assert_clean_inputs(critic: str, commit: str) -> None:
    paths = ["scripts/run_benchmark.py", SKILL_PATHS[critic], f"{FIXTURE_DIR}/{critic}", f"{RULE_DIR}/{critic}.yaml", *ROLE_TEMPLATE_PATHS.values()]
    dirty = subprocess.run(["git", "diff", "--quiet", commit, "--", *paths], cwd=REPO_ROOT).returncode
    untracked = git_text("ls-files", "--others", "--exclude-standard", "--", *paths).strip()
    if dirty or untracked:
        raise IntegrityError("Scorer, skill, rules, templates, or fixtures are dirty")


def fixture_paths(commit: str, critic: str) -> list[str]:
    prefix = safe_repo_path(f"{FIXTURE_DIR}/{critic}")
    return sorted(path for path in git_text("ls-tree", "-r", "--name-only", commit, "--", prefix).splitlines() if path.endswith(".yaml"))


def evidence_lines(code: str, evidence: str, explicit: object = None) -> list[int]:
    if explicit is not None:
        if not isinstance(explicit, list) or not explicit or any(type(line) is not int or line < 1 or line > len(code.splitlines()) for line in explicit):
            raise IntegrityError("Explicit evidence_lines are invalid")
        if explicit != sorted(set(explicit)) or not any(evidence in code.splitlines()[line - 1] for line in explicit):
            raise IntegrityError("Explicit evidence_lines do not ground the gold evidence")
        return explicit
    matches = [index for index, line in enumerate(code.splitlines(), 1) if evidence in line]
    if len(matches) != 1:
        raise IntegrityError("Gold evidence must occur on exactly one source line")
    return matches


def issue_id(fixture: dict, issue: dict, index: int) -> str:
    return f"issue-{canonical_hash({'fixture': fixture['id'], 'index': index, 'issue': issue})[:16]}"


def load_rule_catalog(commit: str, critic: str) -> tuple[dict, bytes, str]:
    raw, oid = read_regular_blob(commit, f"{RULE_DIR}/{critic}.yaml")
    data = yaml.safe_load(raw)
    rules = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(rules, list) or not rules:
        raise IntegrityError("Rule catalog must contain rules")
    by_category, rule_ids = {}, set()
    for rule in rules:
        if not isinstance(rule, dict) or not isinstance(rule.get("category"), str) or not isinstance(rule.get("id"), str):
            raise IntegrityError("Rule catalog has invalid rules")
        by_category.setdefault(rule["category"], rule["id"])
        rule_ids.add(rule["id"])
    if len(rule_ids) != len(rules):
        raise IntegrityError("Rule catalog has invalid or duplicate categories")
    return {"by_category": by_category, "rule_ids": rule_ids}, raw, oid


def migrate_fixture(fixture: dict, catalog: dict) -> dict:
    code = fixture.get("code")
    if not isinstance(code, str):
        raise IntegrityError("Fixture code must be text")
    gold = []
    for index, issue in enumerate(fixture.get("issues", [])):
        category = issue.get("category")
        evidence = issue.get("evidence")
        rule_id = issue.get("rule_id", catalog["by_category"].get(category))
        if rule_id not in catalog["rule_ids"] or not isinstance(evidence, str):
            raise IntegrityError(f"Fixture {fixture.get('id')} has an unmapped issue")
        gold.append({"issue_id": issue_id(fixture, issue, index), "rule_id": rule_id, "severity": issue.get("severity"), "category": category, "evidence_lines": evidence_lines(code, evidence, issue.get("evidence_lines"))})
    if len({(item['rule_id'], tuple(item['evidence_lines'])) for item in gold}) != len(gold):
        raise IntegrityError(f"Fixture {fixture.get('id')} has duplicate gold defects")
    return {"id": fixture.get("id"), "code": code, "gold": gold, "public_hash": canonical_hash(public_fixture(fixture)), "gold_hash": canonical_hash(gold), "full_hash": canonical_hash(fixture)}


def load_committed_fixtures(commit: str, critic: str, catalog: dict) -> list[dict]:
    paths = fixture_paths(commit, critic)
    fixtures = [migrate_fixture(yaml.safe_load(read_regular_blob(commit, path)[0]), catalog) for path in paths]
    if len(fixtures) != 8:
        raise IntegrityError(f"Expected exactly 8 fixtures, found {len(fixtures)}")
    return fixtures


def strip_answer_comments(line: str) -> str:
    line = re.sub(r"//.*$", "", line)
    return re.sub(r"/\*.*?\*/", "", line).rstrip()


def public_fixture(fixture: dict) -> dict:
    return {"source_lines": [{"line": index, "code": strip_answer_comments(line)} for index, line in enumerate(fixture["code"].splitlines(), 1)]}


def public_rule_catalog(catalog: dict) -> dict:
    return {"rule_ids": sorted(catalog["rule_ids"])}


def load_role_templates(commit: str) -> tuple[dict, dict, dict]:
    raw, oids, hashes = {}, {}, {}
    for role, path in ROLE_TEMPLATE_PATHS.items():
        raw[role], oids[role] = read_regular_blob(commit, path)
        hashes[role] = bytes_hash(raw[role])
    return raw, oids, hashes


def render_prompt(role: str, fixture: dict, catalog: dict, skill_text: str, templates: dict[str, bytes]) -> str:
    template = templates[role].decode()
    rendered = template.replace("{{RULE_CATALOG}}", json.dumps(public_rule_catalog(catalog), sort_keys=True, allow_nan=False)).replace("{{SOURCE_LINES}}", json.dumps(public_fixture(fixture), sort_keys=True, allow_nan=False))
    return rendered.replace("{{SKILL}}", skill_text if role == "candidate" else "")


def validate_response(response: str, fixture: dict, catalog: dict) -> set[tuple[str, tuple[int, ...]]]:
    payload = strict_json_loads(response, "response")
    if not isinstance(payload, dict) or set(payload) != {"findings"} or not isinstance(payload["findings"], list) or len(payload["findings"]) > 64:
        raise IntegrityError("response must be exactly a findings object with at most 64 findings")
    valid_rules = catalog["rule_ids"]
    max_line = len(fixture["code"].splitlines())
    predictions = set()
    for finding in payload["findings"]:
        if not isinstance(finding, dict) or set(finding) != {"rule_id", "evidence_lines", "assertion"} or finding.get("assertion") != "present":
            raise IntegrityError("Each finding must contain only rule_id, evidence_lines, assertion=present")
        rule_id, lines = finding.get("rule_id"), finding.get("evidence_lines")
        if rule_id not in valid_rules or not isinstance(lines, list) or not lines or any(type(line) is not int or line < 1 or line > max_line for line in lines):
            raise IntegrityError("Finding rule or evidence lines are invalid")
        if lines != sorted(set(lines)):
            raise IntegrityError("Finding evidence_lines must be sorted and unique")
        key = (rule_id, tuple(lines))
        if key in predictions:
            raise IntegrityError("Duplicate structured finding")
        predictions.add(key)
    return predictions


def run_config_path(root: str, critic: str, run_id: str) -> str:
    return safe_repo_path(f"{safe_repo_path(root)}/{critic}/{run_id}/run.json")


def capture_path(root: str, critic: str, run_id: str, fixture_id: str, role: str) -> str:
    return safe_repo_path(f"{safe_repo_path(root)}/{critic}/{run_id}/{fixture_id}.{role}.json")


def load_run_config(commit: str, root: str, critic: str, run_id: str, inputs: dict) -> tuple[dict, bytes, str]:
    raw, oid = read_regular_blob(commit, run_config_path(root, critic, run_id))
    config = strict_json_loads(raw, "run config")
    fields = {"schema_version", "run_id", "critic", "custody_classification", "provider", "model", "runtime", "parameters", "tools", "input_commit", "fixture_ids", "skill_sha256", "rule_catalog_sha256", "scorer_id", "scorer_version", "template_hashes", "public_fixture_hashes", "gold_fixture_hashes"}
    if not isinstance(config, dict) or set(config) != fields or config.get("schema_version") != 1:
        raise IntegrityError("run.json schema is invalid")
    if config["run_id"] != run_id or config["critic"] != critic or config["custody_classification"] != CUSTODY_CLASSIFICATION:
        raise IntegrityError("run.json does not bind the requested run")
    if not all(isinstance(config[field], str) and config[field] for field in ("provider", "model", "runtime")) or not isinstance(config["parameters"], dict) or not isinstance(config["tools"], list):
        raise IntegrityError("run.json execution configuration is invalid")
    require_hash(config["skill_sha256"], "run.json skill_sha256")
    require_hash(config["rule_catalog_sha256"], "run.json rule_catalog_sha256")
    if not isinstance(config["template_hashes"], dict) or not isinstance(config["public_fixture_hashes"], dict) or not isinstance(config["gold_fixture_hashes"], dict):
        raise IntegrityError("run.json hash maps are invalid")
    for mapping in (config["template_hashes"], config["public_fixture_hashes"], config["gold_fixture_hashes"]):
        for value in mapping.values():
            require_hash(value, "run.json mapped hash")
    verify_commit(config["input_commit"], "run.json input_commit")
    if config["input_commit"] != inputs["commit"]:
        raise IntegrityError("run.json input_commit is not the committed scoring-input authority")
    if config["fixture_ids"] != inputs["fixture_ids"] or config["public_fixture_hashes"] != inputs["public_hashes"] or config["gold_fixture_hashes"] != inputs["gold_hashes"]:
        raise IntegrityError("run.json fixture inputs do not match committed scoring inputs")
    if config["skill_sha256"] != inputs["skill_sha"] or config["rule_catalog_sha256"] != inputs["rule_sha"] or config["scorer_id"] != SCORER_ID or config["scorer_version"] != SCORER_VERSION or config["template_hashes"] != inputs["template_hashes"]:
        raise IntegrityError("run.json hashes or scorer identity do not match")
    return config, raw, oid


def capture_input_commit(capture_commit: str, root: str, critic: str, run_id: str) -> str:
    raw, _ = read_regular_blob(capture_commit, run_config_path(root, critic, run_id))
    config = strict_json_loads(raw, "run config")
    if not isinstance(config, dict) or not isinstance(config.get("input_commit"), str):
        raise IntegrityError("run.json must name an input_commit")
    input_commit = verify_commit(config["input_commit"], "run.json input_commit")
    require_ancestor(input_commit, capture_commit, "capture commit must equal or descend from run.json input_commit")
    return input_commit


def require_ancestor(ancestor: str, descendant: str, message: str) -> None:
    relation = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    if relation.returncode:
        raise IntegrityError(message)


def validate_capture(record: object, fixture: dict, critic: str, role: str, run_id: str, config_sha: str, prompt: str, catalog: dict) -> set[tuple[str, tuple[int, ...]]]:
    fields = {"schema_version", "run_id", "critic", "fixture_id", "role", "run_config_sha256", "rendered_prompt", "prompt_sha256", "response", "response_sha256"}
    if not isinstance(record, dict) or set(record) != fields or record.get("schema_version") != 4:
        raise IntegrityError("Capture schema must be exactly version 4")
    if (record.get("run_id"), record.get("critic"), record.get("fixture_id"), record.get("role")) != (run_id, critic, fixture["id"], role):
        raise IntegrityError("Capture identity does not bind the artifact")
    if record.get("run_config_sha256") != config_sha or record.get("rendered_prompt") != prompt or not isinstance(record.get("response"), str):
        raise IntegrityError("Capture run configuration or prompt binding is invalid")
    if record.get("prompt_sha256") != text_hash(prompt) or record.get("response_sha256") != text_hash(record.get("response", "")):
        raise IntegrityError("Capture prompt or response hash mismatch")
    return validate_response(record.get("response"), fixture, catalog)


def score_artifact(raw: bytes, oid: str, fixture: dict, critic: str, role: str, run_id: str, config_sha: str, prompt: str, catalog: dict, path: str) -> dict:
    record = strict_json_loads(raw, f"capture {path}")
    predicted = validate_capture(record, fixture, critic, role, run_id, config_sha, prompt, catalog)
    gold = {(item["rule_id"], tuple(item["evidence_lines"])) for item in fixture["gold"]}
    return {"fixture_id": fixture["id"], "role": role, "predicted": sorted(predicted), "gold": sorted(gold), "capture_path": path, "capture_blob_oid": oid, "capture_raw_sha256": bytes_hash(raw), "rendered_prompt_sha256": record["prompt_sha256"], "response_sha256": record["response_sha256"]}


def metric_summary(artifacts: list[dict], fixtures: list[dict], role: str) -> dict:
    by_id = {fixture["id"]: fixture for fixture in fixtures}
    tp = fp = fn = 0
    severity = {name: [0, 0] for name in SEVERITY_WEIGHT}
    per_fixture = []
    for artifact in [item for item in artifacts if item["role"] == role]:
        predicted, gold = set(map(tuple, artifact["predicted"])), set(map(tuple, artifact["gold"]))
        true = predicted & gold
        tp += len(true); fp += len(predicted - gold); fn += len(gold - predicted)
        per_fixture.append({"fixture_id": artifact["fixture_id"], "exact_set_f1": f1(len(true), len(predicted - gold), len(gold - predicted))})
        for issue in by_id[artifact["fixture_id"]]["gold"]:
            bucket = severity[issue["severity"]]
            bucket[1] += 1
            if (issue["rule_id"], tuple(issue["evidence_lines"])) in true:
                bucket[0] += 1
    return {"tp": tp, "fp": fp, "fn": fn, "precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn), "f1": f1(tp, fp, fn), "per_severity_recall": {name: ratio(hit, total) for name, (hit, total) in severity.items()}, "per_fixture_exact_set_f1": per_fixture, "clean_fixture_accuracy": "UNAVAILABLE: no adjudicated clean fixtures in the fixed eight-fixture corpus"}


def ratio(top: int, bottom: int) -> float:
    return round(top / bottom, 4) if bottom else 0.0


def f1(tp: int, fp: int, fn: int) -> float:
    return ratio(2 * tp, 2 * tp + fp + fn)


def build_window_references(run_id: str, artifacts: list[dict], fixtures: list[dict]) -> list[dict]:
    by_key = {(item["fixture_id"], item["role"]): item for item in artifacts}
    refs = []
    for window, indices in JACKKNIFE_WINDOWS.items():
        for index in indices:
            for role in ("candidate", "baseline"):
                artifact = by_key[(fixtures[index]["id"], role)]
                refs.append({"cell_id": f"{run_id}:window-{window}:{fixture['id'] if False else fixtures[index]['id']}:{role}", "window": window, "fixture_id": fixtures[index]["id"], "role": role, "capture_blob_oid": artifact["capture_blob_oid"]})
    if len(refs) != 36 or len({ref["cell_id"] for ref in refs}) != 36:
        raise IntegrityError("Expected 36 unique window references")
    return refs


def atomic_publish(bundle: Path, report: str, manifest: dict) -> tuple[Path, Path]:
    if os.path.lexists(bundle):
        raise IntegrityError(f"Refusing to overwrite existing bundle: {bundle}")
    bundle.parent.mkdir(parents=True, exist_ok=True)
    try:
        bundle.mkdir()
    except FileExistsError as error:
        raise IntegrityError(f"Refusing to overwrite existing bundle: {bundle}") from error
    temp = None
    try:
        temp = Path(tempfile.mkdtemp(prefix=".pending-model-benchmark-", dir=bundle.parent))
        (temp / "report.md").write_text(report + "\n")
        (temp / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
        (temp / "COMPLETE").write_text("complete\n")
        for name in ("report.md", "manifest.json", "COMPLETE"):
            os.replace(temp / name, bundle / name)
        temp.rmdir()
    except Exception:
        if temp is not None:
            shutil.rmtree(temp, ignore_errors=True)
        shutil.rmtree(bundle, ignore_errors=True)
        raise
    return bundle / "report.md", bundle / "manifest.json"


def report_text(critic: str, run_id: str, candidate: dict, baseline: dict) -> str:
    delta = round(candidate["f1"] - baseline["f1"], 4)
    lines = [f"# {critic} Exact Structured Defect-Detection Benchmark", "", f"- Run ID: `{run_id}`", f"- Custody: `{CUSTODY_CLASSIFICATION}`; provider labels are self-attested, not independently verified.", "- Primary sample: 8 unique captures per role. Jackknife windows are sensitivity references only.", "- This is not proof of prose quality, remediation quality, severity judgment, novel-finding ability, provider authenticity, or statistical superiority.", "", "## Micro exact-match metrics", "", "| Role | TP | FP | FN | Precision | Recall | F1 |", "|---|---:|---:|---:|---:|---:|---:|", f"| Candidate | {candidate['tp']} | {candidate['fp']} | {candidate['fn']} | {candidate['precision']} | {candidate['recall']} | {candidate['f1']} |", f"| Baseline | {baseline['tp']} | {baseline['fp']} | {baseline['fn']} | {baseline['precision']} | {baseline['recall']} | {baseline['f1']} |", f"| Candidate minus baseline F1 |  |  |  |  |  | {delta} |", "", "## Per-severity recall", "", "| Severity | Candidate | Baseline |", "|---|---:|---:|"]
    lines += [f"| {severity} | {candidate['per_severity_recall'][severity]} | {baseline['per_severity_recall'][severity]} |" for severity in SEVERITY_WEIGHT]
    lines += ["", "## Per-fixture exact-set F1", "", "| Fixture | Candidate | Baseline |", "|---|---:|---:|"]
    baseline_f1 = {item["fixture_id"]: item["exact_set_f1"] for item in baseline["per_fixture_exact_set_f1"]}
    lines += [f"| {item['fixture_id']} | {item['exact_set_f1']} | {baseline_f1[item['fixture_id']]} |" for item in candidate["per_fixture_exact_set_f1"]]
    lines += ["", f"Clean-fixture accuracy: {candidate['clean_fixture_accuracy']}"]
    return "\n".join(lines)


def run_model_benchmark(critic: str, capture_commit: str, run_id: str, capture_root: str, results_dir: Path) -> tuple[Path, Path]:
    capture_commit = verify_commit(capture_commit)
    if not RUN_ID_RE.fullmatch(run_id):
        raise IntegrityError("--run-id must be an RFC4122 UUID")
    input_commit = capture_input_commit(capture_commit, capture_root, critic, run_id)
    current = head_commit()
    require_ancestor(capture_commit, current, "current HEAD must equal or descend from capture commit")
    assert_clean_inputs(critic, input_commit)
    catalog, rule_raw, rule_oid = load_rule_catalog(input_commit, critic)
    fixtures = load_committed_fixtures(input_commit, critic, catalog)
    skill_raw, skill_oid = read_regular_blob(input_commit, SKILL_PATHS[critic])
    templates, template_oids, template_hashes = load_role_templates(input_commit)
    inputs = {"commit": input_commit, "fixture_ids": [fixture["id"] for fixture in fixtures], "skill_sha": bytes_hash(skill_raw), "rule_sha": bytes_hash(rule_raw), "template_hashes": template_hashes, "public_hashes": {fixture["id"]: fixture["public_hash"] for fixture in fixtures}, "gold_hashes": {fixture["id"]: fixture["gold_hash"] for fixture in fixtures}}
    _, config_raw, config_oid = load_run_config(capture_commit, capture_root, critic, run_id, inputs)
    config_sha = bytes_hash(config_raw)
    artifacts = []
    for fixture in fixtures:
        for role in ("candidate", "baseline"):
            prompt = render_prompt(role, fixture, catalog, skill_raw.decode(), templates)
            path = capture_path(capture_root, critic, run_id, fixture["id"], role)
            raw, oid = read_regular_blob(capture_commit, path)
            artifacts.append(score_artifact(raw, oid, fixture, critic, role, run_id, config_sha, prompt, catalog, path))
    if len(artifacts) != 16 or len({(item['fixture_id'], item['role']) for item in artifacts}) != 16:
        raise IntegrityError("Expected exactly 16 unique capture artifacts")
    candidate, baseline = metric_summary(artifacts, fixtures, "candidate"), metric_summary(artifacts, fixtures, "baseline")
    refs = build_window_references(run_id, artifacts, fixtures)
    manifest = {"schema_version": 4, "benchmark": "exact-structured-defect-detection", "custody_classification": CUSTODY_CLASSIFICATION, "run_id": run_id, "critic": critic, "capture_commit": capture_commit, "input_commit": input_commit, "run_config": {"path": run_config_path(capture_root, critic, run_id), "blob_oid": config_oid, "sha256": config_sha}, "scoring_code": {"commit": current, "sha256": bytes_hash(read_regular_blob(current, "scripts/run_benchmark.py")[0])}, "skill": {"path": SKILL_PATHS[critic], "blob_oid": skill_oid, "sha256": inputs['skill_sha']}, "rule_catalog": {"path": f"{RULE_DIR}/{critic}.yaml", "blob_oid": rule_oid, "sha256": inputs['rule_sha']}, "templates": {role: {"path": ROLE_TEMPLATE_PATHS[role], "blob_oid": template_oids[role], "sha256": template_hashes[role]} for role in templates}, "fixtures": [{"id": item["id"], "public_sha256": item["public_hash"], "gold_sha256": item["gold_hash"], "full_sha256": item["full_hash"]} for item in fixtures], "capture_artifacts": artifacts, "capture_artifact_count": 16, "window_references": refs, "jackknife_window_reference_count": 36, "metrics": {"candidate": candidate, "baseline": baseline, "candidate_minus_baseline_f1": round(candidate['f1'] - baseline['f1'], 4)}}
    return atomic_publish(results_dir / f"model-benchmark-{critic}-{run_id}", report_text(critic, run_id, candidate, baseline), manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score exact structured defect-detection captures")
    parser.add_argument("--critic", choices=sorted(SKILL_PATHS), required=True)
    parser.add_argument("--capture-commit", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--capture-root", default=CAPTURE_ROOT)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args()
    report, manifest = run_model_benchmark(args.critic, args.capture_commit, args.run_id, args.capture_root, args.results_dir)
    print(f"Wrote {report} and {manifest}")


if __name__ == "__main__":
    main()
