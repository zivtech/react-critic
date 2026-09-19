#!/usr/bin/env python3
"""Shared manifest-v2 and external-skill integrity helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable


MAX_FILE_BYTES = 1024 * 1024
TEXT_SCAN_SUFFIXES = {
    ".md", ".txt", ".yaml", ".yml", ".json", ".py", ".js", ".mjs",
    ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".toml",
}
ASSET_DIRS = {"assets"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
INJECTION_PATTERNS = (
    (re.compile(r"ignore\s+(?:all\s+|any\s+|previous\s+|prior\s+|above\s+)?(?:instructions|rules|guidelines)", re.IGNORECASE), "instruction override"),
    (re.compile(r"you\s+are\s+now\b", re.IGNORECASE), "identity override"),
    (re.compile(r"from\s+now\s+on\b.*?\b(?:ignore|forget|disregard)", re.IGNORECASE), "behavioral override"),
    (re.compile(r"system\s+(?:prompt|message|instruction)", re.IGNORECASE), "system prompt reference"),
    (re.compile(r"disregard\s+(?:all\s+|any\s+|previous\s+|prior\s+)?(?:instructions|rules|guidelines|constraints)", re.IGNORECASE), "instruction disregard"),
    (re.compile(r"<script[\s>]", re.IGNORECASE), "script injection"),
    (re.compile(r"javascript[ \t]*:[ \t]*[A-Za-z_$({]", re.IGNORECASE), "javascript URI"),
    (re.compile(r"data:\s*\w+/\w+;base64,", re.IGNORECASE), "base64 data embed"),
    (re.compile(r"<\s*(?:invoke|tool_use|function_call)", re.IGNORECASE), "tool invocation injection"),
    (re.compile(r"\bIMPORTANT\s*:\s*(?:ignore|override|disregard|forget)", re.IGNORECASE), "priority override"),
)


class ExternalSkillError(RuntimeError):
    """A typed, fail-closed external skill error."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class FetchResult:
    data: bytes
    url: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def scan_content(content: str, skill_id: str) -> list[str]:
    """Return stable, line-addressed prompt-injection findings."""
    def mask(match: re.Match[str]) -> str:
        return "".join("\n" if character == "\n" else " " for character in match.group())

    # Literal examples are data, not instructions. Preserve their line offsets while
    # excluding fenced and inline Markdown code from the natural-language scanner.
    scanned = re.sub(
        r"(?ms)^[ \t]*(?:>[ \t]*)*(```|~~~).*?^[ \t]*(?:>[ \t]*)*\1[ \t]*$",
        mask,
        content,
    )
    scanned = re.sub(r"(?<!`)`[^`\n]+`(?!`)", mask, scanned)
    warnings: list[str] = []
    for pattern, description in INJECTION_PATTERNS:
        for match in pattern.finditer(scanned):
            line_number = scanned[:match.start()].count("\n") + 1
            warnings.append(
                f'  {skill_id} line {line_number}: {description} — matched "{match.group()}"'
            )
    return warnings


def warning_hash(skill_id: str, warning: str) -> str:
    return hashlib.sha256(f"{skill_id}\0{warning}".encode("utf-8")).hexdigest()[:16]


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def bundle_digest(files: Iterable[dict]) -> str:
    records: list[bytes] = []
    for record in sorted(files, key=lambda item: item["path"].encode("utf-8")):
        records.append(
            record["path"].encode("utf-8")
            + b"\0"
            + str(record["size"]).encode("ascii")
            + b"\0"
            + record["sha256"].encode("ascii")
            + b"\n"
        )
    return sha256_bytes(b"".join(records))


def validate_relative_path(path: str) -> PurePosixPath:
    if not path or "\x00" in path or "\\" in path:
        raise ExternalSkillError("INVALID_PATH", f"Invalid source path: {path!r}")
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or any(part in {"", ".", ".."} for part in parsed.parts):
        raise ExternalSkillError("INVALID_PATH", f"Unsafe source path: {path!r}")
    return parsed


def instruction_file(relative_path: PurePosixPath) -> bool:
    if any(part in ASSET_DIRS for part in relative_path.parts):
        return False
    return relative_path.suffix.lower() in TEXT_SCAN_SUFFIXES


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


@lru_cache(maxsize=1)
def _github_token() -> str | None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token.strip()
    if not shutil.which("gh"):
        return None
    process = subprocess.run(
        ["gh", "auth", "token"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return process.stdout.strip() if process.returncode == 0 else None


def fetch_bytes(url: str, *, attempts: int = 3, timeout: int = 20) -> FetchResult:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            headers = {"User-Agent": "zivtech-react-critic/2"}
            if urllib.parse.urlparse(url).hostname == "api.github.com":
                token = _github_token()
                if token:
                    headers["Authorization"] = f"Bearer {token}"
            request = urllib.request.Request(
                url,
                headers=headers,
            )
            with urllib.request.urlopen(request, timeout=timeout, context=_ssl_context()) as response:
                return FetchResult(response.read(), response.geturl())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ssl.SSLError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.5 * (2**attempt))
    raise ExternalSkillError("UNAVAILABLE", f"Unable to fetch {url}: {last_error}")


def repo_slug(repo_url: str) -> str:
    prefix = "https://github.com/"
    if not repo_url.startswith(prefix):
        raise ExternalSkillError("INVALID_REPOSITORY", f"Unsupported repository: {repo_url}")
    slug = repo_url.removeprefix(prefix).removesuffix(".git")
    if len(slug.split("/")) != 2:
        raise ExternalSkillError("INVALID_REPOSITORY", f"Invalid GitHub repository: {repo_url}")
    return slug


def raw_url(entry: dict, repository_path: str) -> str:
    path = validate_relative_path(repository_path)
    encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in path.parts)
    return (
        f"https://raw.githubusercontent.com/{repo_slug(entry['repo_url'])}/"
        f"{entry['pinned_commit']}/{encoded_path}"
    )


def github_tree(entry: dict) -> list[dict]:
    slug = repo_slug(entry["repo_url"])
    commit = entry["pinned_commit"]
    url = f"https://api.github.com/repos/{slug}/git/trees/{commit}?recursive=1"
    payload = json.loads(fetch_bytes(url).data)
    if payload.get("truncated"):
        raise ExternalSkillError("TRUNCATED_TREE", f"Git tree is truncated for {entry['id']}")
    return payload.get("tree", [])


def current_head(repo_url: str) -> str:
    process = subprocess.run(
        ["git", "ls-remote", repo_url, "HEAD"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if process.returncode or not process.stdout.strip():
        detail = process.stderr.strip() or "empty ls-remote response"
        raise ExternalSkillError("UNAVAILABLE", f"Unable to resolve HEAD for {repo_url}: {detail}")
    commit = process.stdout.split()[0]
    if not SHA_RE.fullmatch(commit):
        raise ExternalSkillError("INVALID_PIN", f"Invalid HEAD returned for {repo_url}")
    return commit


def collect_bundle(
    entry: dict,
    *,
    tree: list[dict] | None = None,
    fetcher: Callable[[str], FetchResult] = fetch_bytes,
) -> tuple[list[dict], dict[str, str]]:
    source_path = validate_relative_path(entry["source_path"])
    source_dir = source_path.parent
    tree = tree if tree is not None else github_tree(entry)
    prefix = "" if str(source_dir) == "." else f"{source_dir}/"
    candidates: list[tuple[str, str, int]] = []
    seen_casefold: set[str] = set()

    for item in tree:
        repository_path = item.get("path", "")
        if prefix and not repository_path.startswith(prefix):
            continue
        relative = repository_path[len(prefix):] if prefix else repository_path
        if not relative:
            continue
        relative_path = validate_relative_path(relative)
        if not instruction_file(relative_path):
            continue
        if item.get("type") == "tree":
            continue
        if item.get("type") != "blob" or item.get("mode") in {"120000", "160000"}:
            raise ExternalSkillError(
                "UNSUPPORTED_ENTRY",
                f"Unsupported bundle entry for {entry['id']}: {repository_path}",
            )
        size = int(item.get("size", 0))
        if size > MAX_FILE_BYTES:
            raise ExternalSkillError(
                "FILE_TOO_LARGE",
                f"Instruction file exceeds {MAX_FILE_BYTES} bytes: {repository_path}",
            )
        folded = relative.casefold()
        if folded in seen_casefold:
            raise ExternalSkillError("PATH_COLLISION", f"Case-fold path collision: {relative}")
        seen_casefold.add(folded)
        candidates.append((relative, repository_path, size))

    entry_relative = source_path.name
    if entry_relative not in {candidate[0] for candidate in candidates}:
        raise ExternalSkillError("ENTRYPOINT_MISSING", f"Missing entrypoint: {entry['source_path']}")

    records: list[dict] = []
    texts: dict[str, str] = {}

    def download(candidate: tuple[str, str, int]) -> tuple[str, int, bytes]:
        relative, repository_path, expected_size = candidate
        data = fetcher(raw_url(entry, repository_path)).data
        if len(data) != expected_size:
            raise ExternalSkillError(
                "SIZE_MISMATCH",
                f"Size mismatch for {entry['id']}:{relative}: expected {expected_size}, got {len(data)}",
            )
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ExternalSkillError(
                "NON_UTF8_INSTRUCTION",
                f"Non-UTF-8 instruction file for {entry['id']}:{relative}",
            ) from exc
        return relative, expected_size, data

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(candidates)))) as executor:
        futures = {executor.submit(download, candidate): candidate for candidate in candidates}
        for future in as_completed(futures):
            relative, size, data = future.result()
            records.append({"path": relative, "size": size, "sha256": sha256_bytes(data)})
            texts[relative] = data.decode("utf-8")

    records.sort(key=lambda item: item["path"].encode("utf-8"))
    return records, texts


def validate_file_records(entry: dict) -> None:
    files = entry.get("files")
    if not isinstance(files, list) or not files:
        raise ExternalSkillError("INVALID_LOCK", f"No locked files for {entry.get('id')}")
    paths: set[str] = set()
    for record in files:
        path = str(record.get("path", ""))
        validate_relative_path(path)
        if path in paths:
            raise ExternalSkillError("INVALID_LOCK", f"Duplicate locked path: {path}")
        paths.add(path)
        if not isinstance(record.get("size"), int) or record["size"] < 0:
            raise ExternalSkillError("INVALID_LOCK", f"Invalid size for {path}")
        if not SHA256_RE.fullmatch(str(record.get("sha256", ""))):
            raise ExternalSkillError("INVALID_LOCK", f"Invalid SHA-256 for {path}")
    if bundle_digest(files) != entry.get("bundle_sha256"):
        raise ExternalSkillError("BUNDLE_MISMATCH", f"Stored bundle digest mismatch for {entry.get('id')}")
    entry_relative = PurePosixPath(entry["source_path"]).name
    entry_record = next((record for record in files if record["path"] == entry_relative), None)
    if not entry_record or entry_record["sha256"] != entry.get("entry_sha256"):
        raise ExternalSkillError("ENTRY_MISMATCH", f"Entrypoint digest mismatch for {entry.get('id')}")


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExternalSkillError("INVALID_JSON", f"Unable to read {path}: {exc}") from exc


def write_json(path: Path, value: dict) -> None:
    write_text_atomic(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def resolve_locked_file(entry: dict, relative_path: str) -> str:
    validate_file_records(entry)
    relative = str(validate_relative_path(relative_path))
    record = next((item for item in entry["files"] if item["path"] == relative), None)
    if record is None:
        raise ExternalSkillError("RESOURCE_NOT_LOCKED", f"Resource is not locked: {relative}")
    source_dir = PurePosixPath(entry["source_path"]).parent
    repository_path = str(source_dir / relative) if str(source_dir) != "." else relative
    data = fetch_bytes(raw_url(entry, repository_path)).data
    if len(data) != record["size"] or sha256_bytes(data) != record["sha256"]:
        raise ExternalSkillError("CONTENT_MISMATCH", f"Content mismatch for {entry['id']}:{relative}")
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExternalSkillError("NON_UTF8_INSTRUCTION", f"Resource is not UTF-8: {relative}") from exc
    exceptions = {
        (item.get("finding_hash"), item.get("warning"))
        for item in entry.get("scan_exceptions", [])
    }
    for warning in scan_content(content, f"{entry['id']}:{relative}"):
        finding_hash = warning_hash(entry["id"], warning)
        if (finding_hash, warning) not in exceptions:
            raise ExternalSkillError(
                "SCAN_WARNING",
                f"{entry['id']} scan warning {finding_hash}: {warning}",
            )
    return content


def environment_config_dir() -> Path:
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(configured) if configured else Path.home() / ".claude"
