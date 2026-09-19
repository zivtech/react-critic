#!/usr/bin/env python3
"""Load and execute the benchmark scorer from an exact committed Git blob."""

import hashlib
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
SCORER_PATH = "scripts/benchmark_scorer.py"


def _git_bytes(*args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode().strip() or "Git command failed")
    return result.stdout


def _run_committed_scorer() -> None:
    commit = _git_bytes("rev-parse", "HEAD").decode().strip()
    blob = _git_bytes("show", f"{commit}:{SCORER_PATH}")
    working = (REPO_ROOT / SCORER_PATH).read_bytes()
    if working != blob:
        raise RuntimeError(f"Refusing to execute dirty scorer: {SCORER_PATH}")
    oid = _git_bytes("rev-parse", f"{commit}:{SCORER_PATH}").decode().strip()
    authority = {
        "commit": commit,
        "path": SCORER_PATH,
        "blob_oid": oid,
        "sha256": hashlib.sha256(blob).hexdigest(),
        "execution": "compiled-from-committed-blob",
    }
    namespace = {
        "__name__": "__committed_benchmark_scorer__",
        "__file__": str(REPO_ROOT / SCORER_PATH),
        "EXECUTED_SCORER_AUTHORITY": authority,
    }
    exec(compile(blob, namespace["__file__"], "exec"), namespace)
    namespace["main"]()


if __name__ == "__main__":
    _run_committed_scorer()
else:
    from benchmark_scorer import *  # noqa: F401,F403
