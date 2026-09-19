from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".claude/skills/shared-js-core/scripts"))

from artifact_receipt import (  # noqa: E402
    create_review_receipt,
    plan_digest,
    read_json,
    scope_fingerprint,
    verify_receipt,
)
from external_skill_lib import ExternalSkillError  # noqa: E402


class ArtifactReceiptTests(unittest.TestCase):
    def plan(self) -> dict:
        return {
            "schema_version": 1,
            "objective": "Add a component",
            "framework": "react",
            "scope": ["src"],
            "assumptions": [],
            "steps": ["Implement"],
            "validation": ["Test"],
            "rollback": "Revert the focused change",
            "out_of_scope": ["Deployment"],
            "critic": "react-critic",
        }

    def test_plan_digest_ignores_embedded_digest_and_is_stable(self) -> None:
        plan = self.plan()
        digest = plan_digest(plan)
        reordered = json.loads(json.dumps(plan, sort_keys=True))
        reordered["plan_sha256"] = "wrong"
        self.assertEqual(digest, plan_digest(reordered))

    def test_plan_rejects_wrong_framework_critic(self) -> None:
        plan = self.plan()
        plan["critic"] = "next-critic"
        with self.assertRaisesRegex(ExternalSkillError, "Expected react-critic"):
            plan_digest(plan)

    def test_plan_rejects_missing_and_unknown_framework(self) -> None:
        plan = self.plan()
        del plan["steps"]
        with self.assertRaisesRegex(ExternalSkillError, "Missing plan fields"):
            plan_digest(plan)
        plan = self.plan()
        plan["framework"] = "vue"
        with self.assertRaisesRegex(ExternalSkillError, "framework must"):
            plan_digest(plan)

    def test_read_json_reports_invalid_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("not json", encoding="utf-8")
            with self.assertRaisesRegex(ExternalSkillError, "Unable to read"):
                read_json(str(path))

    def test_scope_fingerprint_tracks_modified_and_untracked_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            (root / "src").mkdir()
            (root / "src/a.tsx").write_text("old\n", encoding="utf-8")
            subprocess.run(["git", "add", "src/a.tsx"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
            base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            (root / "src/a.tsx").write_text("new\n", encoding="utf-8")
            (root / "src/b.tsx").write_text("added\n", encoding="utf-8")
            result = scope_fingerprint(root, base, ["src"])
            self.assertEqual(["src/a.tsx", "src/b.tsx"], [item["path"] for item in result["files"]])
            self.assertEqual(64, len(result["scope_sha256"]))

    def test_receipt_is_fail_closed_for_scope_drift(self) -> None:
        receipt = {
            "schema_version": 1,
            "critic": "react-critic",
            "verdict": "ACCEPT",
            "artifact_sha256": "a" * 64,
            "scope_sha256": "b" * 64,
            "review_sha256": "d" * 64,
        }
        with self.assertRaisesRegex(ExternalSkillError, "working-tree scope"):
            verify_receipt(receipt, "a" * 64, "c" * 64, "d" * 64, "react-critic")

    def test_receipt_accepts_exact_binding_and_rejects_other_failures(self) -> None:
        receipt = {
            "schema_version": 1,
            "critic": "next-critic",
            "verdict": "ACCEPT-WITH-RESERVATIONS",
            "artifact_sha256": "a" * 64,
            "scope_sha256": "b" * 64,
            "review_sha256": "d" * 64,
        }
        verify_receipt(receipt, "a" * 64, "b" * 64, "d" * 64, "next-critic")
        cases = [
            ({**receipt, "critic": "react-critic"}, "Receipt critic"),
            ({**receipt, "verdict": "REVISE"}, "Receipt verdict"),
            ({**receipt, "artifact_sha256": "c" * 64}, "artifact digest"),
            ({key: value for key, value in receipt.items() if key != "verdict"}, "Missing receipt"),
        ]
        for candidate, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ExternalSkillError, message):
                verify_receipt(candidate, "a" * 64, "b" * 64, "d" * 64, "next-critic")

    def test_review_receipt_binds_exact_accepted_critic_output(self) -> None:
        review = "VERDICT: ACCEPT\n\nOverall Assessment\nGood.\n"
        receipt = create_review_receipt(review, "a" * 64, "b" * 64, "react-critic")
        verify_receipt(
            receipt,
            "a" * 64,
            "b" * 64,
            receipt["review_sha256"],
            "react-critic",
        )
        with self.assertRaisesRegex(ExternalSkillError, "Critic verdict is REVISE"):
            create_review_receipt("VERDICT: REVISE\n", "a" * 64, "b" * 64, "react-critic")
        with self.assertRaisesRegex(ExternalSkillError, "exactly one VERDICT"):
            create_review_receipt("No verdict\n", "a" * 64, "b" * 64, "react-critic")
        with self.assertRaisesRegex(ExternalSkillError, "critic output"):
            verify_receipt(receipt, "a" * 64, "b" * 64, "e" * 64, "react-critic")
        with self.assertRaisesRegex(ExternalSkillError, "lowercase SHA-256"):
            create_review_receipt(review, "not-a-digest", "b" * 64, "react-critic")

    def test_scope_fingerprint_tracks_deletion_and_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            (root / "src").mkdir()
            tracked = root / "src/deleted.ts"
            tracked.write_text("old\n", encoding="utf-8")
            subprocess.run(["git", "add", "src/deleted.ts"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
            base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            tracked.unlink()
            (root / "src/target.ts").write_text("target\n", encoding="utf-8")
            (root / "src/link.ts").symlink_to("target.ts")
            result = scope_fingerprint(root, base, ["src"])
            by_path = {item["path"]: item for item in result["files"]}
            self.assertIsNone(by_path["src/deleted.ts"]["current"])
            self.assertEqual("120000", by_path["src/link.ts"]["current"]["mode"])

    def test_scope_rejects_unsafe_path(self) -> None:
        with self.assertRaisesRegex(ExternalSkillError, "Unsafe scope"):
            scope_fingerprint(ROOT, "HEAD", ["../outside"])


if __name__ == "__main__":
    unittest.main()
