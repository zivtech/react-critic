#!/usr/bin/env python3
"""Exact structured defect-detection scoring from immutable Git artifacts.

Production execution is bootstrapped by ``scripts/run_benchmark.py`` from the
exact committed bytes of this module.
"""

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
SCORER_PATH = "scripts/benchmark_scorer.py"
BOOTSTRAP_PATH = "scripts/run_benchmark.py"
FIXTURE_DIR = "research/benchmarks/fixtures"
RULE_DIR = "research/benchmarks/rules"
TEMPLATE_DIR = "research/benchmarks/templates"
CAPTURE_ROOT = "research/benchmarks/captures"
RESULTS_DIR = REPO_ROOT / "research/benchmarks/results"
SKILL_PATHS = {"react": ".claude/skills/react-critic/SKILL.md", "next": ".claude/skills/next-critic/SKILL.md", "react-native": ".claude/skills/react-native-critic/SKILL.md"}
ROLE_TEMPLATE_PATHS = {"candidate": f"{TEMPLATE_DIR}/candidate.txt", "baseline": f"{TEMPLATE_DIR}/baseline.txt"}
JACKKNIFE_WINDOWS = {1: [0, 1, 2, 3, 4, 5], 2: [1, 2, 3, 4, 5, 6], 3: [2, 3, 4, 5, 6, 7]}
SEVERITY_WEIGHT = {"CRITICAL": 5.0, "MAJOR": 3.0, "MINOR": 1.0}
DIFFICULTIES = {"CLEAN", "HAS-BUGS", "FUNDAMENTALLY-FLAWED", "ADVERSARIAL"}
SCORER_ID = "exact-rule-line-defect-detection"
SCORER_VERSION = "5"
TREATMENT = "inline-skill-only"
CUSTODY_CLASSIFICATION = "self-attested-repo-native"
HASH_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
RUN_ID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z")
EXECUTED_SCORER_AUTHORITY = globals().get("EXECUTED_SCORER_AUTHORITY")


class IntegrityError(ValueError):
    """Raised when exact scoring or artifact custody cannot be proven."""


class StrictLoader(yaml.SafeLoader):
    """YAML loader that rejects duplicate mapping keys."""


def construct_unique_mapping(loader: StrictLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise IntegrityError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_unique_mapping)


def strict_yaml_load(value: str | bytes, label: str) -> object:
    try:
        return yaml.load(value, Loader=StrictLoader)
    except IntegrityError:
        raise
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise IntegrityError(f"{label} is not strict UTF-8 YAML") from error


def require_exact_mapping(value: object, fields: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        raise IntegrityError(f"{label} must contain exactly {sorted(fields)}")
    return value


def require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IntegrityError(f"{label} must be nonempty text")
    return value


def require_text_list(value: object, label: str, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise IntegrityError(f"{label} must be a {'possibly empty ' if allow_empty else 'nonempty '}list of text")
    return value


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
    if not isinstance(value, str):
        raise IntegrityError(f"Unsafe repo-relative path: {value!r}")
    path = PurePosixPath(value)
    raw_parts = value.split("/")
    if not value or "\\" in value or path.is_absolute() or any(part in ("", ".", "..") for part in raw_parts):
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


def verified_scorer_authority(input_commit: str, current: str) -> dict:
    input_raw, input_oid = read_regular_blob(input_commit, SCORER_PATH)
    current_raw, current_oid = read_regular_blob(current, SCORER_PATH)
    if input_raw != current_raw or input_oid != current_oid:
        raise IntegrityError("Scorer differs between input authority and current HEAD")
    try:
        working_raw = (REPO_ROOT / SCORER_PATH).read_bytes()
    except OSError as error:
        raise IntegrityError(f"Cannot read working scorer: {SCORER_PATH}") from error
    if working_raw != current_raw:
        raise IntegrityError("Working scorer differs from the committed scorer authority")
    expected = {"commit": current, "path": SCORER_PATH, "blob_oid": current_oid, "sha256": bytes_hash(current_raw)}
    if EXECUTED_SCORER_AUTHORITY is not None:
        if not isinstance(EXECUTED_SCORER_AUTHORITY, dict) or any(EXECUTED_SCORER_AUTHORITY.get(key) != value for key, value in expected.items()):
            raise IntegrityError("Executed scorer authority does not match the verified Git blob")
        if EXECUTED_SCORER_AUTHORITY.get("execution") != "compiled-from-committed-blob":
            raise IntegrityError("Executed scorer was not compiled from the committed blob")
        return dict(EXECUTED_SCORER_AUTHORITY)
    return {**expected, "execution": "verified-working-tree-unit-path"}


def assert_clean_inputs(critic: str, input_commit: str, current: str) -> dict:
    inputs = [SKILL_PATHS[critic], f"{FIXTURE_DIR}/{critic}", f"{RULE_DIR}/{critic}.yaml", *ROLE_TEMPLATE_PATHS.values()]
    if subprocess.run(["git", "diff", "--quiet", input_commit, "--", *inputs], cwd=REPO_ROOT).returncode:
        raise IntegrityError("Skill, rules, templates, or fixtures differ from the input authority")
    current_paths = [BOOTSTRAP_PATH, SCORER_PATH]
    if subprocess.run(["git", "diff", "--quiet", current, "--", *current_paths], cwd=REPO_ROOT).returncode:
        raise IntegrityError("Benchmark bootstrap or scorer differs from current HEAD")
    untracked = git_text("ls-files", "--others", "--exclude-standard", "--", *inputs, *current_paths).strip()
    if untracked:
        raise IntegrityError("Benchmark inputs contain untracked files")
    bootstrap_raw, bootstrap_oid = read_regular_blob(current, BOOTSTRAP_PATH)
    if (REPO_ROOT / BOOTSTRAP_PATH).read_bytes() != bootstrap_raw:
        raise IntegrityError("Working benchmark bootstrap differs from current HEAD")
    authority = verified_scorer_authority(input_commit, current)
    authority["bootstrap"] = {"path": BOOTSTRAP_PATH, "blob_oid": bootstrap_oid, "sha256": bytes_hash(bootstrap_raw)}
    return authority


def fixture_paths(commit: str, critic: str) -> list[str]:
    prefix = safe_repo_path(f"{FIXTURE_DIR}/{critic}")
    return sorted(path for path in git_text("ls-tree", "-r", "--name-only", commit, "--", prefix).splitlines() if path.endswith(".yaml"))


def load_rule_catalog(commit: str, critic: str) -> tuple[dict, bytes, str]:
    raw, oid = read_regular_blob(commit, f"{RULE_DIR}/{critic}.yaml")
    data = require_exact_mapping(strict_yaml_load(raw, "rule catalog"), {"schema_version", "rules"}, "Rule catalog")
    if data["schema_version"] != 2 or not isinstance(data["rules"], list) or not data["rules"]:
        raise IntegrityError("Rule catalog must contain rules")
    rules, by_id = [], {}
    for index, value in enumerate(data["rules"]):
        rule = require_exact_mapping(value, {"id", "category", "title", "definition", "exclusions"}, f"Rule {index}")
        for field in ("id", "category", "title", "definition"):
            require_text(rule[field], f"Rule {index} {field}")
        require_text_list(rule["exclusions"], f"Rule {index} exclusions", allow_empty=True)
        if rule["id"] in by_id:
            raise IntegrityError(f"Duplicate rule id: {rule['id']}")
        by_id[rule["id"]] = rule["category"]
        rules.append(rule)
    return {"rules": rules, "by_id": by_id, "rule_ids": set(by_id)}, raw, oid


def validate_public_fixture(value: object, fixture_id: str) -> dict:
    public = require_exact_mapping(value, {"file_path", "language", "frameworks", "runtime", "assumptions", "requirements", "code"}, f"Fixture {fixture_id} public")
    for field in ("file_path", "language", "runtime", "code"):
        require_text(public[field], f"Fixture {fixture_id} public {field}")
    safe_repo_path(public["file_path"])
    if not isinstance(public["frameworks"], dict) or not public["frameworks"] or any(not isinstance(key, str) or not key.strip() or not isinstance(item, str) or not item.strip() for key, item in public["frameworks"].items()):
        raise IntegrityError(f"Fixture {fixture_id} frameworks must be a nonempty text mapping")
    require_text_list(public["assumptions"], f"Fixture {fixture_id} assumptions")
    require_text_list(public["requirements"], f"Fixture {fixture_id} requirements", allow_empty=True)
    return public


def validate_fixture_metadata(value: object, fixture_id: str) -> dict:
    metadata = require_exact_mapping(value, {"provenance", "difficulty", "domains", "adjudication"}, f"Fixture {fixture_id} metadata")
    provenance = require_exact_mapping(metadata["provenance"], {"kind", "origin", "revision_reason"}, f"Fixture {fixture_id} provenance")
    if provenance["kind"] != "synthetic":
        raise IntegrityError(f"Fixture {fixture_id} provenance kind must be synthetic")
    require_text(provenance["origin"], f"Fixture {fixture_id} provenance origin")
    require_text(provenance["revision_reason"], f"Fixture {fixture_id} provenance revision_reason")
    if metadata["difficulty"] not in DIFFICULTIES:
        raise IntegrityError(f"Fixture {fixture_id} has invalid difficulty")
    require_text_list(metadata["domains"], f"Fixture {fixture_id} domains")
    adjudication = require_exact_mapping(metadata["adjudication"], {"status", "method", "reviewer", "reviewed_on", "sources", "notes", "excluded_claims"}, f"Fixture {fixture_id} adjudication")
    if adjudication["status"] != "reviewed" or adjudication["reviewed_on"] != "2026-09-19":
        raise IntegrityError(f"Fixture {fixture_id} adjudication status or date is invalid")
    for field in ("method", "reviewer", "notes"):
        require_text(adjudication[field], f"Fixture {fixture_id} adjudication {field}")
    require_text_list(adjudication["excluded_claims"], f"Fixture {fixture_id} excluded_claims", allow_empty=True)
    if not isinstance(adjudication["sources"], list) or not adjudication["sources"]:
        raise IntegrityError(f"Fixture {fixture_id} adjudication sources must be nonempty")
    for index, source in enumerate(adjudication["sources"]):
        source = require_exact_mapping(source, {"url", "supports"}, f"Fixture {fixture_id} source {index}")
        url = require_text(source["url"], f"Fixture {fixture_id} source {index} url")
        if not url.startswith("https://"):
            raise IntegrityError(f"Fixture {fixture_id} source URLs must use HTTPS")
        require_text(source["supports"], f"Fixture {fixture_id} source {index} supports")
    return metadata


def validate_evidence_spans(value: object, code: str, label: str) -> list[dict]:
    if not isinstance(value, list) or not value:
        raise IntegrityError(f"{label} evidence_spans must be nonempty")
    spans, seen = [], set()
    max_line = len(code.splitlines())
    for index, raw in enumerate(value):
        span = require_exact_mapping(raw, {"lines", "rationale"}, f"{label} evidence span {index}")
        lines = span["lines"]
        if not isinstance(lines, list) or not lines or any(type(line) is not int or line < 1 or line > max_line for line in lines) or lines != sorted(set(lines)):
            raise IntegrityError(f"{label} evidence span {index} has invalid lines")
        key = tuple(lines)
        if key in seen:
            raise IntegrityError(f"{label} has duplicate evidence spans")
        seen.add(key)
        require_text(span["rationale"], f"{label} evidence span {index} rationale")
        spans.append({"lines": lines, "rationale": span["rationale"]})
    return spans


def migrate_fixture(fixture: dict, catalog: dict) -> dict:
    fixture = require_exact_mapping(fixture, {"schema_version", "id", "category", "description", "intentional_clean", "public", "metadata", "issues"}, "Fixture")
    if fixture["schema_version"] != 2:
        raise IntegrityError("Fixture schema_version must be 2")
    fixture_id = require_text(fixture["id"], "Fixture id")
    require_text(fixture["category"], f"Fixture {fixture_id} category")
    require_text(fixture["description"], f"Fixture {fixture_id} description")
    if type(fixture["intentional_clean"]) is not bool or not isinstance(fixture["issues"], list):
        raise IntegrityError(f"Fixture {fixture_id} clean flag or issues list is invalid")
    if fixture["intentional_clean"] != (fixture["issues"] == []):
        raise IntegrityError(f"Fixture {fixture_id} must explicitly agree on clean status and issues")
    public = validate_public_fixture(fixture["public"], fixture_id)
    metadata = validate_fixture_metadata(fixture["metadata"], fixture_id)
    code = public["code"]
    gold, issue_ids, accepted_keys = [], set(), set()
    issue_fields = {"id", "rule_id", "category", "severity", "description", "evidence_spans"}
    for index, raw in enumerate(fixture["issues"]):
        issue = require_exact_mapping(raw, issue_fields, f"Fixture {fixture_id} issue {index}")
        issue_id_value = require_text(issue["id"], f"Fixture {fixture_id} issue {index} id")
        if issue_id_value in issue_ids:
            raise IntegrityError(f"Fixture {fixture_id} has duplicate issue ids")
        issue_ids.add(issue_id_value)
        rule_id = require_text(issue["rule_id"], f"Fixture {fixture_id} issue {index} rule_id")
        category = require_text(issue["category"], f"Fixture {fixture_id} issue {index} category")
        if catalog["by_id"].get(rule_id) != category:
            raise IntegrityError(f"Fixture {fixture_id} issue {issue_id_value} has a rule/category mismatch")
        if issue["severity"] not in SEVERITY_WEIGHT:
            raise IntegrityError(f"Fixture {fixture_id} issue {issue_id_value} has invalid severity")
        require_text(issue["description"], f"Fixture {fixture_id} issue {issue_id_value} description")
        spans = validate_evidence_spans(issue["evidence_spans"], code, f"Fixture {fixture_id} issue {issue_id_value}")
        for span in spans:
            key = (rule_id, tuple(span["lines"]))
            if key in accepted_keys:
                raise IntegrityError(f"Fixture {fixture_id} has an ambiguous accepted evidence key")
            accepted_keys.add(key)
        gold.append({"issue_id": issue_id_value, "rule_id": rule_id, "severity": issue["severity"], "category": category, "accepted_evidence_lines": [span["lines"] for span in spans]})
    projection = public_fixture({"public": public})
    return {"id": fixture_id, "code": code, "public": public, "metadata": metadata, "intentional_clean": fixture["intentional_clean"], "gold": gold, "public_hash": canonical_hash(projection), "gold_hash": canonical_hash(gold), "full_hash": canonical_hash(fixture)}


def load_committed_fixtures(commit: str, critic: str, catalog: dict) -> list[dict]:
    paths = fixture_paths(commit, critic)
    fixtures = [migrate_fixture(strict_yaml_load(read_regular_blob(commit, path)[0], f"fixture {path}"), catalog) for path in paths]
    if len(fixtures) != 8:
        raise IntegrityError(f"Expected exactly 8 fixtures, found {len(fixtures)}")
    if len({fixture["id"] for fixture in fixtures}) != len(fixtures):
        raise IntegrityError("Fixture ids must be unique")
    return fixtures


def public_fixture(fixture: dict) -> dict:
    public = fixture["public"]
    return {
        "file_path": public["file_path"],
        "language": public["language"],
        "frameworks": public["frameworks"],
        "runtime": public["runtime"],
        "assumptions": public["assumptions"],
        "requirements": public["requirements"],
        "source_lines": [{"line": index, "code": line} for index, line in enumerate(public["code"].splitlines(), 1)],
    }


def public_rule_catalog(catalog: dict) -> dict:
    return {"rules": sorted(catalog["rules"], key=lambda rule: rule["id"])}


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
    fields = {"schema_version", "run_id", "critic", "treatment", "custody_classification", "provider", "model", "runtime", "parameters", "tools", "input_commit", "fixture_ids", "skill_sha256", "rule_catalog_sha256", "scorer_id", "scorer_version", "scorer_sha256", "template_hashes", "public_fixture_hashes", "gold_fixture_hashes"}
    if not isinstance(config, dict) or set(config) != fields or config.get("schema_version") != 2:
        raise IntegrityError("run.json schema is invalid")
    if config["run_id"] != run_id or config["critic"] != critic or config["treatment"] != TREATMENT or config["custody_classification"] != CUSTODY_CLASSIFICATION:
        raise IntegrityError("run.json does not bind the requested run")
    if not all(isinstance(config[field], str) and config[field] for field in ("provider", "model", "runtime")) or not isinstance(config["parameters"], dict) or config["tools"] != []:
        raise IntegrityError("run.json execution configuration is invalid")
    require_hash(config["skill_sha256"], "run.json skill_sha256")
    require_hash(config["rule_catalog_sha256"], "run.json rule_catalog_sha256")
    require_hash(config["scorer_sha256"], "run.json scorer_sha256")
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
    if config["skill_sha256"] != inputs["skill_sha"] or config["rule_catalog_sha256"] != inputs["rule_sha"] or config["scorer_id"] != SCORER_ID or config["scorer_version"] != SCORER_VERSION or config["scorer_sha256"] != inputs["scorer_sha"] or config["template_hashes"] != inputs["template_hashes"]:
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
    if not isinstance(record, dict) or set(record) != fields or record.get("schema_version") != 5:
        raise IntegrityError("Capture schema must be exactly version 5")
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
    accepted = {}
    for issue in fixture["gold"]:
        for lines in issue["accepted_evidence_lines"]:
            accepted[(issue["rule_id"], tuple(lines))] = issue["issue_id"]
    matched_issue_ids, matched_predictions = set(), set()
    for prediction in sorted(predicted):
        issue_id_value = accepted.get(prediction)
        if issue_id_value is not None and issue_id_value not in matched_issue_ids:
            matched_issue_ids.add(issue_id_value)
            matched_predictions.add(prediction)
    return {
        "fixture_id": fixture["id"],
        "role": role,
        "predicted": sorted(predicted),
        "matched_predictions": sorted(matched_predictions),
        "matched_issue_ids": sorted(matched_issue_ids),
        "gold": fixture["gold"],
        "capture_path": path,
        "capture_blob_oid": oid,
        "capture_raw_sha256": bytes_hash(raw),
        "rendered_prompt_sha256": record["prompt_sha256"],
        "response_sha256": record["response_sha256"],
    }


def metric_summary(artifacts: list[dict], fixtures: list[dict], role: str) -> dict:
    by_id = {fixture["id"]: fixture for fixture in fixtures}
    tp = fp = fn = 0
    severity = {name: [0, 0] for name in SEVERITY_WEIGHT}
    per_fixture, clean_correct = [], 0
    clean_total = sum(1 for fixture in fixtures if fixture["intentional_clean"])
    for artifact in [item for item in artifacts if item["role"] == role]:
        fixture = by_id[artifact["fixture_id"]]
        predicted = {tuple([item[0], tuple(item[1])]) for item in artifact["predicted"]}
        matched_predictions = {tuple([item[0], tuple(item[1])]) for item in artifact["matched_predictions"]}
        matched_issue_ids = set(artifact["matched_issue_ids"])
        local_tp = len(matched_issue_ids)
        local_fp = len(predicted - matched_predictions)
        local_fn = len(fixture["gold"]) - local_tp
        tp += local_tp; fp += local_fp; fn += local_fn
        exact = local_fp == 0 and local_fn == 0
        per_fixture.append({"fixture_id": artifact["fixture_id"], "exact_match": exact, "f1": 1.0 if exact and not fixture["gold"] else f1(local_tp, local_fp, local_fn)})
        if fixture["intentional_clean"] and exact:
            clean_correct += 1
        for issue in fixture["gold"]:
            bucket = severity[issue["severity"]]
            bucket[1] += 1
            if issue["issue_id"] in matched_issue_ids:
                bucket[0] += 1
    return {"fixture_count": len(fixtures), "gold_issue_count": sum(len(fixture["gold"]) for fixture in fixtures), "tp": tp, "fp": fp, "fn": fn, "precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn), "f1": f1(tp, fp, fn), "per_severity_recall": {name: ratio(hit, total) for name, (hit, total) in severity.items()}, "per_fixture": per_fixture, "clean_fixture_accuracy": {"correct": clean_correct, "total": clean_total, "accuracy": ratio(clean_correct, clean_total) if clean_total else None}}


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
                fixture_id = fixtures[index]["id"]
                refs.append({"cell_id": f"{run_id}:window-{window}:{fixture_id}:{role}", "window": window, "fixture_id": fixture_id, "role": role, "capture_blob_oid": artifact["capture_blob_oid"]})
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
    reservation = bundle.lstat()
    temp = None
    bundle_fd = None
    try:
        bundle_fd = os.open(bundle, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        opened = os.fstat(bundle_fd)
        if (opened.st_dev, opened.st_ino) != (reservation.st_dev, reservation.st_ino):
            raise IntegrityError("Reserved publication bundle was substituted before it was opened")
        temp = Path(tempfile.mkdtemp(prefix=".pending-model-benchmark-", dir=bundle.parent))
        (temp / "report.md").write_text(report + "\n")
        (temp / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
        (temp / "COMPLETE").write_text("complete\n")
        for name in ("report.md", "manifest.json", "COMPLETE"):
            os.replace(temp / name, name, dst_dir_fd=bundle_fd)
        temp.rmdir()
        current = bundle.lstat()
        if (current.st_dev, current.st_ino) != (reservation.st_dev, reservation.st_ino):
            raise IntegrityError("Reserved publication bundle was substituted during publication")
    except Exception:
        if temp is not None:
            shutil.rmtree(temp, ignore_errors=True)
        raise
    finally:
        if bundle_fd is not None:
            os.close(bundle_fd)
    return bundle / "report.md", bundle / "manifest.json"


def report_text(critic: str, run_id: str, candidate: dict, baseline: dict) -> str:
    delta = round(candidate["f1"] - baseline["f1"], 4)
    lines = [f"# {critic} Exact Structured Defect-Detection Benchmark", "", f"- Run ID: `{run_id}`", f"- Treatment: `{TREATMENT}`; this evaluates only the committed inline `SKILL.md` text.", f"- Custody: `{CUSTODY_CLASSIFICATION}`; provider labels are self-attested, not independently verified.", "- Primary sample: 8 unique captures per role. Jackknife windows are sensitivity references only.", "- Metrics are descriptive. This is not proof of full-skill behavior, prose quality, remediation quality, severity judgment, novel-finding ability, provider authenticity, or statistical superiority.", "", "## Micro exact-match metrics", "", "| Role | Fixtures | Gold issues | TP | FP | FN | Precision | Recall | F1 |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|", f"| Candidate | {candidate['fixture_count']} | {candidate['gold_issue_count']} | {candidate['tp']} | {candidate['fp']} | {candidate['fn']} | {candidate['precision']} | {candidate['recall']} | {candidate['f1']} |", f"| Baseline | {baseline['fixture_count']} | {baseline['gold_issue_count']} | {baseline['tp']} | {baseline['fp']} | {baseline['fn']} | {baseline['precision']} | {baseline['recall']} | {baseline['f1']} |", f"| Candidate minus baseline F1 |  |  |  |  |  |  |  | {delta} |", "", "## Per-severity recall", "", "| Severity | Candidate | Baseline |", "|---|---:|---:|"]
    lines += [f"| {severity} | {candidate['per_severity_recall'][severity]} | {baseline['per_severity_recall'][severity]} |" for severity in SEVERITY_WEIGHT]
    lines += ["", "## Per-fixture exact match and F1", "", "| Fixture | Candidate exact | Candidate F1 | Baseline exact | Baseline F1 |", "|---|---:|---:|---:|---:|"]
    baseline_by_id = {item["fixture_id"]: item for item in baseline["per_fixture"]}
    lines += [f"| {item['fixture_id']} | {item['exact_match']} | {item['f1']} | {baseline_by_id[item['fixture_id']]['exact_match']} | {baseline_by_id[item['fixture_id']]['f1']} |" for item in candidate["per_fixture"]]
    lines += ["", f"Candidate clean-fixture accuracy: {candidate['clean_fixture_accuracy']['correct']}/{candidate['clean_fixture_accuracy']['total']} ({candidate['clean_fixture_accuracy']['accuracy']})", f"Baseline clean-fixture accuracy: {baseline['clean_fixture_accuracy']['correct']}/{baseline['clean_fixture_accuracy']['total']} ({baseline['clean_fixture_accuracy']['accuracy']})"]
    return "\n".join(lines)


def run_model_benchmark(critic: str, capture_commit: str, run_id: str, capture_root: str, results_dir: Path) -> tuple[Path, Path]:
    capture_commit = verify_commit(capture_commit)
    if not RUN_ID_RE.fullmatch(run_id):
        raise IntegrityError("--run-id must be an RFC4122 UUID")
    input_commit = capture_input_commit(capture_commit, capture_root, critic, run_id)
    current = head_commit()
    require_ancestor(capture_commit, current, "current HEAD must equal or descend from capture commit")
    scorer_authority = assert_clean_inputs(critic, input_commit, current)
    catalog, rule_raw, rule_oid = load_rule_catalog(input_commit, critic)
    fixtures = load_committed_fixtures(input_commit, critic, catalog)
    skill_raw, skill_oid = read_regular_blob(input_commit, SKILL_PATHS[critic])
    templates, template_oids, template_hashes = load_role_templates(input_commit)
    inputs = {"commit": input_commit, "fixture_ids": [fixture["id"] for fixture in fixtures], "skill_sha": bytes_hash(skill_raw), "rule_sha": bytes_hash(rule_raw), "scorer_sha": scorer_authority["sha256"], "template_hashes": template_hashes, "public_hashes": {fixture["id"]: fixture["public_hash"] for fixture in fixtures}, "gold_hashes": {fixture["id"]: fixture["gold_hash"] for fixture in fixtures}}
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
    manifest = {"schema_version": 5, "benchmark": "exact-structured-defect-detection", "treatment": TREATMENT, "custody_classification": CUSTODY_CLASSIFICATION, "run_id": run_id, "critic": critic, "capture_commit": capture_commit, "input_commit": input_commit, "run_config": {"path": run_config_path(capture_root, critic, run_id), "blob_oid": config_oid, "sha256": config_sha}, "scoring_code": scorer_authority, "skill": {"path": SKILL_PATHS[critic], "blob_oid": skill_oid, "sha256": inputs['skill_sha']}, "rule_catalog": {"path": f"{RULE_DIR}/{critic}.yaml", "blob_oid": rule_oid, "sha256": inputs['rule_sha']}, "templates": {role: {"path": ROLE_TEMPLATE_PATHS[role], "blob_oid": template_oids[role], "sha256": template_hashes[role]} for role in templates}, "fixtures": [{"id": item["id"], "intentional_clean": item["intentional_clean"], "difficulty": item["metadata"]["difficulty"], "public_sha256": item["public_hash"], "gold_sha256": item["gold_hash"], "full_sha256": item["full_hash"]} for item in fixtures], "capture_artifacts": artifacts, "capture_artifact_count": 16, "window_references": refs, "jackknife_window_reference_count": 36, "metrics": {"candidate": candidate, "baseline": baseline, "candidate_minus_baseline_f1": round(candidate['f1'] - baseline['f1'], 4)}}
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
