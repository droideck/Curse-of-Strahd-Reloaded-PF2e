#!/usr/bin/env python3
"""Stateful, deterministic workflow for in-place English -> Russian localization.

The script intentionally uses only the Python standard library.  It treats the
Git blob recorded in .translation/ru/config.json as the immutable English
source and the worktree file as the Russian target.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence


STATE_REL = Path(".translation/ru")
SKILL_REL = Path(".agents/skills/translate-cos-reloaded-ru")
LEGACY_REFERENCE_REL = Path("cos-translation-skill-stuff/references")
CONFIG_NAME = "config.json"
CONFIG_SEAL_NAME = "config-seal.json"
MANIFEST_NAME = "manifest.json"
HEADING_MAP_NAME = "heading-map.json"
STYLE_WATCH_NAME = "style-watch.tsv"
REPORTS_DIR = "reports"
REVIEWS_DIR = "reviews"
WORK_DIR = "work"
CONTENT_SUFFIXES = {".md", ".canvas"}
CONTENT_ROOTS = (
    "Introduction/",
    "Chapter 1 - Beginning the Campaign/",
    "Chapter 2 - The Land of Barovia/",
    "Chapter 3 - Running the Game/",
    "Act I - Into the Mists/",
    "Act II - The Shadowed Town/",
    "Act III - The Broken Land/",
    "Act IV - Secrets of the Ancient/",
    "Appendices/",
    "_other/templates/",
)
DEFAULT_PROTECTED_BRANCHES = {"main", "master", "pf2e-changes", "translate-rus-5e"}
AUTHORITY_FILES = ("glossary.tsv", STYLE_WATCH_NAME, "style-guide.md", "voice-cards.md")
GLOSSARY_HEADER = (
    "source", "approved_ru", "category", "sense_ruleset", "gender_animacy", "forms",
    "capitalization", "scope", "forbidden_variants", "status", "enforce", "evidence",
    "origin_unit", "reviewer", "decision_date", "notes",
)
TERM_CANDIDATES_HEADER = (
    "source", "proposed_ru", "category", "sense_ruleset", "forms_or_voice", "scope",
    "evidence", "origin_unit", "rationale", "proposed_by", "status", "reviewer",
    "decision_date", "notes",
)
SOURCE_ISSUES_HEADER = (
    "id", "path", "line_or_heading", "category", "description", "translation_policy",
    "status", "evidence_commit", "reviewer", "notes",
)
STYLE_WATCH_HEADER = (
    "id", "status", "literals", "category", "guidance", "applicability", "exceptions",
    "evidence", "origin_unit", "reviewer", "decision_date", "notes",
)
STYLE_DISPOSITION_DECISIONS = {"accepted-context", "false-positive"}
UNIT_STATUSES = {
    "pending", "in_progress", "auto_qa_pass", "independent_review", "needs_revision",
    "approved", "completed", "consistency_review", "stale_source", "skipped",
}
ACTIVE_TRANSLATION_STATUSES = {
    "in_progress", "auto_qa_pass", "independent_review", "needs_revision", "approved",
}
HTML_BLOCK_CONTAINERS = {"div", "table", "details", "section", "pre", "style", "script"}

HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", re.MULTILINE)
SCENE_CODE_RE = re.compile(r"^([A-U]\d+[a-z]?\.)\s+", re.IGNORECASE)
CALLOUT_RE = re.compile(r"^(\s*(?:>\s*)+)\[!([^\]]+)\]([+-]?)", re.MULTILINE)
WIKILINK_RE = re.compile(r"(!?)\[\[([^\]\n]+)\]\]")
ENTITY_RE = re.compile(r"&(?:#\d+|#x[0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]+);")
FOOTNOTE_REF_RE = re.compile(r"\[\^([^\]]+)\]")
FOOTNOTE_DEF_RE = re.compile(r"(?m)^\[\^([^\]]+)\]:")
BLOCK_ID_RE = re.compile(r"(?m)(?<!\S)\^([A-Za-z0-9-]+)[ \t]*$")
DICE_RE = re.compile(r"(?<![A-Za-z0-9_])(?:\d+)?[dD]\d+(?:\s*[+-]\s*\d+)?(?![A-Za-z0-9_])")
NUMBER_RE = re.compile(r"(?<![A-Za-zА-Яа-яЁё])\d+(?:[.,]\d+)?")
SIGNED_NUMBER_RE = re.compile(r"(?<![A-Za-zА-Яа-яЁё0-9])[+−-]\s*\d+(?:[.,]\d+)?(?![A-Za-zА-Яа-яЁё0-9])")
RANGE_RE = re.compile(r"(?<!\d)\d+(?:[.,]\d+)?\s*(?:-|–|—|/)\s*\d+(?:[.,]\d+)?(?!\d)")
PERCENT_RE = re.compile(r"(?<!\d)\d+(?:[.,]\d+)?%")
MACRO_RE = re.compile(r"@[A-Za-z][A-Za-z0-9_]*\[[^\]\n]*\]")
ROLL_RE = re.compile(r"\[\[(?:/(?:r|roll|damage)\b)[^\]\n]*\]\]", re.IGNORECASE)
TEMPLATE_RE = re.compile(r"\{\{[^{}\n]+\}\}|\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b")
CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
LATIN_RE = re.compile(r"[A-Za-z]")
ENGLISH_WORD_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
INLINE_CODE_RE = re.compile(r"(?<!`)(`+)(?!`)([^\n]*?)(?<!`)\1(?!`)")
FENCED_CODE_RE = re.compile(r"(?ms)^(?P<indent>[ \t]{0,3})(?P<fence>`{3,}|~{3,})[^\n]*\n.*?^(?P=indent)(?P=fence)[ \t]*(?:\n|$)")
BARE_URL_RE = re.compile(r"(?<![\w\"'=])(https?://[^\s<>\"']+)")
EMPHASIS_RE = re.compile(r"(?<!\\)(?:\*{1,3}|_{1,3})")

ENGLISH_STOPWORDS = {
    "a", "about", "after", "all", "also", "an", "and", "any", "are", "as", "at",
    "be", "because", "before", "but", "by", "can", "character", "characters", "do",
    "does", "each", "for", "from", "has", "have", "he", "her", "his", "if", "in",
    "into", "is", "it", "its", "may", "must", "not", "of", "on", "one", "or", "other",
    "player", "players", "read", "she", "should", "that", "the", "their", "them", "then",
    "they", "this", "through", "to", "until", "upon", "was", "when", "where", "which",
    "while", "who", "will", "with", "you", "your",
}


class WorkflowError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def compact_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def merge_spans(spans: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def html_comment_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    index = 0
    while True:
        start = text.find("<!--", index)
        if start < 0:
            break
        close = text.find("-->", start + 4)
        end = len(text) if close < 0 else close + 3
        spans.append((start, end))
        index = end
    return spans


def html_comment_tokens(text: str) -> list[str]:
    return [text[start:end] for start, end in html_comment_spans(text)]


def code_spans(text: str) -> list[tuple[int, int]]:
    """Return fenced and inline Markdown code spans without parsing prose inside fences."""
    lines = text.splitlines(keepends=True)
    offsets: list[int] = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line)
    fenced: list[tuple[int, int]] = []
    index = 0
    while index < len(lines):
        opener = re.match(
            r"^[ \t]{0,3}(?P<quotes>(?:>\s*)*)(?P<fence>`{3,}|~{3,})[^\r\n]*(?:\r?\n|$)",
            lines[index],
        )
        if not opener:
            index += 1
            continue
        fence = opener.group("fence")
        quote_depth = opener.group("quotes").count(">")
        quote_prefix = rf"(?:>\s*){{{quote_depth}}}" if quote_depth else ""
        closing = re.compile(
            rf"^[ \t]{{0,3}}{quote_prefix}{re.escape(fence[0])}{{{len(fence)},}}[ \t]*(?:\r?\n|$)"
        )
        end_index = index + 1
        while end_index < len(lines) and not closing.match(lines[end_index]):
            end_index += 1
        if end_index < len(lines):
            end_index += 1
        start_offset = offsets[index]
        end_offset = offsets[end_index] if end_index < len(offsets) else len(text)
        fenced.append((start_offset, end_offset))
        index = max(end_index, index + 1)
    indented: list[tuple[int, int]] = []
    excluded = merge_spans([*fenced, *html_comment_spans(text)])
    html_depths: list[int] = []
    html_depth = 0
    for raw_line in lines:
        html_depths.append(html_depth)
        for tag in scan_html_tags(raw_line):
            tag_match = re.match(r"<\s*(/?)\s*([A-Za-z0-9-]+)", tag)
            if not tag_match or tag.startswith("<!"):
                continue
            closing, name = tag_match.group(1), tag_match.group(2).casefold()
            if name not in HTML_BLOCK_CONTAINERS:
                continue
            if closing:
                html_depth = max(0, html_depth - 1)
            elif not tag.rstrip().endswith("/>"):
                html_depth += 1
    line_index = 0
    while line_index < len(lines):
        start_offset = offsets[line_index]
        if any(left <= start_offset < right for left, right in excluded):
            line_index += 1
            continue
        line = lines[line_index]
        if html_depths[line_index] or not re.match(r"^(?: {4}|\t)", line):
            line_index += 1
            continue
        previous_line_blank = line_index == 0 or not lines[line_index - 1].strip()
        previous_nonblank = next(
            (lines[item] for item in range(line_index - 1, -1, -1) if lines[item].strip()),
            "",
        )
        if not previous_line_blank or re.match(r"^\s*(?:[-+*]\s|\d+[.)]\s)", previous_nonblank):
            line_index += 1
            continue
        end_index = line_index + 1
        while end_index < len(lines):
            if re.match(r"^(?: {4}|\t)", lines[end_index]):
                end_index += 1
                continue
            if not lines[end_index].strip():
                next_nonblank = next(
                    (item for item in range(end_index + 1, len(lines)) if lines[item].strip()),
                    None,
                )
                if next_nonblank is not None and re.match(r"^(?: {4}|\t)", lines[next_nonblank]):
                    end_index += 1
                    continue
            break
        end_offset = offsets[end_index] if end_index < len(offsets) else len(text)
        indented.append((start_offset, end_offset))
        line_index = end_index
    inline: list[tuple[int, int]] = []
    index = 0
    while index < len(text):
        containing = next(((start, end) for start, end in fenced if start <= index < end), None)
        if containing:
            index = containing[1]
            continue
        if text[index] != "`":
            index += 1
            continue
        run_end = index + 1
        while run_end < len(text) and text[run_end] == "`":
            run_end += 1
        length = run_end - index
        search = run_end
        closing_end = -1
        while search < len(text):
            next_tick = text.find("`", search)
            if next_tick < 0:
                break
            candidate_end = next_tick + 1
            while candidate_end < len(text) and text[candidate_end] == "`":
                candidate_end += 1
            if candidate_end - next_tick == length:
                closing_end = candidate_end
                break
            search = candidate_end
        if closing_end >= 0:
            inline.append((index, closing_end))
            index = closing_end
        else:
            index = run_end
    return merge_spans([*fenced, *indented, *inline])


def protected_spans(text: str) -> list[tuple[int, int]]:
    comments = html_comment_spans(text)
    return merge_spans([*comments, *code_spans(text)])


def mask_spans(text: str, spans: Iterable[tuple[int, int]]) -> str:
    """Replace protected characters with spaces while preserving newlines and offsets."""
    chars = list(text)
    for start, end in spans:
        for index in range(start, min(end, len(chars))):
            if chars[index] not in "\r\n":
                chars[index] = " "
    return "".join(chars)


def code_tokens(text: str) -> list[str]:
    return [text[start:end] for start, end in code_spans(text)]


def bare_urls(text: str) -> list[str]:
    """Extract bare URL tokens while excluding ordinary sentence punctuation."""
    results: list[str] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    for match in BARE_URL_RE.finditer(text):
        value = match.group(1).rstrip(".,;:!?")
        while value and value[-1] in pairs and value.count(value[-1]) > value.count(pairs[value[-1]]):
            value = value[:-1]
        results.append(value)
    return results


def span_is_protected(start: int, spans: Sequence[tuple[int, int]]) -> bool:
    return any(left <= start < right for left, right in spans)


def run_git(root: Path, args: Sequence[str], *, binary: bool = False, check: bool = True) -> Any:
    proc = subprocess.run(
        ["git", *args],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=not binary,
    )
    if check and proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", "replace") if binary else proc.stderr
        raise WorkflowError(f"git {' '.join(args)} failed: {stderr.strip()}")
    return proc


def repo_root() -> Path:
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise WorkflowError("run this command inside the translation repository")
    return Path(proc.stdout.strip()).resolve()


def state_dir(root: Path) -> Path:
    return root / STATE_REL


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkflowError(f"missing {path}; run init first") from exc
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"invalid JSON in {path}: {exc}") from exc


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = (path.stat().st_mode & 0o7777) if path.exists() else 0o644
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def load_state(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    state = state_dir(root)
    return load_json(state / CONFIG_NAME), load_json(state / MANIFEST_NAME)


def save_manifest(root: Path, manifest: dict[str, Any]) -> None:
    manifest["updated_at"] = utc_now()
    atomic_write_json(state_dir(root) / MANIFEST_NAME, manifest)


def write_config_seal(root: Path, config_path: Path) -> None:
    atomic_write_json(
        state_dir(root) / CONFIG_SEAL_NAME,
        {
            "schema_version": 1,
            "config_sha256": sha256_bytes(config_path.read_bytes()),
            "sealed_at": utc_now(),
        },
    )


def config_seal_ok(root: Path) -> bool:
    config_path = state_dir(root) / CONFIG_NAME
    seal_path = state_dir(root) / CONFIG_SEAL_NAME
    if not regular_state_file_ok(config_path) or not regular_state_file_ok(seal_path):
        return False
    try:
        seal = load_json(seal_path)
    except WorkflowError:
        return False
    return seal.get("schema_version") == 1 and seal.get("config_sha256") == sha256_bytes(config_path.read_bytes())


def validate_config_contract(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if config.get("schema_version") != 1:
        errors.append("unsupported config schema")
    if config.get("workflow_version") != 2:
        errors.append("unsupported config workflow version")
    if config.get("project") != "Curse of Strahd: Reloaded":
        errors.append("config project identity is invalid")
    if config.get("source_language") != "en" or config.get("target_language") != "ru":
        errors.append("config language direction must remain en-to-ru")
    if not re.fullmatch(r"[0-9a-f]{40}", str(config.get("source_commit", ""))):
        errors.append("config source commit is invalid")
    if not str(config.get("source_ref_at_init", "")).strip():
        errors.append("config source-ref provenance is missing")
    edition = config.get("edition")
    if not isinstance(edition, dict) or (
        edition.get("system") != "D&D 5e"
        or edition.get("baseline") != "2014 rules"
        or edition.get("forbid_implicit_conversion") is not True
        or not str(edition.get("exceptions", "")).strip()
    ):
        errors.append("config edition contract is invalid or weakened")
    protected = config.get("protected_branches")
    if not isinstance(protected, list) or not DEFAULT_PROTECTED_BRANCHES.issubset(
        {str(value) for value in protected}
    ):
        errors.append("config protected-branch set is invalid or weakened")
    if config.get("required_review_roles") != ["fidelity", "russian-style"]:
        errors.append("config must require independent fidelity and Russian-style reviews")
    minimum_score = config.get("minimum_review_score")
    if (
        isinstance(minimum_score, bool)
        or not isinstance(minimum_score, (int, float))
        or not 90 <= minimum_score <= 100
    ):
        errors.append("config minimum review score must remain between 90 and 100")
    maximum_words = config.get("maximum_segment_words")
    if isinstance(maximum_words, bool) or not isinstance(maximum_words, int) or not 500 <= maximum_words <= 5000:
        errors.append("config maximum segment size is outside the reviewed safety range")
    minimum_cyrillic = config.get("minimum_cyrillic_letter_ratio")
    if (
        isinstance(minimum_cyrillic, bool)
        or not isinstance(minimum_cyrillic, (int, float))
        or not 0.35 <= minimum_cyrillic <= 1.0
    ):
        errors.append("config Cyrillic threshold is invalid or weakened")
    if config.get("yaml_translatable_keys") != ["description", "keywords", "title", "aliases"]:
        errors.append("config YAML translatable-key allowlist is invalid")
    if config.get("content_roots") != list(CONTENT_ROOTS):
        errors.append("config content-root inventory is invalid")
    if not isinstance(config.get("sealed_support_hashes"), dict):
        errors.append("config sealed-support identity is invalid")
    history = config.get("workflow_seal_history")
    if not isinstance(history, list) or not history:
        errors.append("config workflow-seal history is missing")
    return errors


def regular_state_file_ok(path: Path) -> bool:
    try:
        mode = path.lstat().st_mode
    except OSError:
        return False
    return stat.S_ISREG(mode) and (mode & 0o777) == 0o644


def core_state_file_errors(root: Path) -> list[str]:
    state = state_dir(root)
    errors: list[str] = []
    for name in (CONFIG_NAME, CONFIG_SEAL_NAME, MANIFEST_NAME, HEADING_MAP_NAME):
        path = state / name
        if not regular_state_file_ok(path):
            errors.append(f"core state is missing/non-regular/wrong-mode: {path}")
    return errors


def current_branch(root: Path) -> str:
    return run_git(root, ["branch", "--show-current"]).stdout.strip()


def ensure_mutation_branch(root: Path, config: dict[str, Any] | None = None) -> str:
    if config is not None and not config_seal_ok(root):
        raise WorkflowError("config differs from its reviewed seal; reseal it between units")
    if config is not None:
        state_errors = [*core_state_file_errors(root), *validate_authority_state(root)]
        if state_errors:
            raise WorkflowError("translation state integrity failure: " + "; ".join(state_errors[:8]))
    if config is not None and config.get("sealed_support_hashes", {}) != compute_static_support_hashes(root):
        raise WorkflowError("workflow-support files differ from their reviewed seal")
    branch = current_branch(root)
    protected = set((config or {}).get("protected_branches", DEFAULT_PROTECTED_BRANCHES))
    if not branch:
        raise WorkflowError("detached HEAD is not allowed for translation mutations")
    if branch in protected:
        raise WorkflowError(f"refusing to mutate protected branch {branch!r}")
    return branch


def ensure_source_ancestor(root: Path, config: dict[str, Any]) -> None:
    commit = config["source_commit"]
    proc = run_git(root, ["merge-base", "--is-ancestor", commit, "HEAD"], check=False)
    if proc.returncode != 0:
        raise WorkflowError(
            f"recorded source commit {commit[:12]} is not an ancestor of HEAD; "
            "stop and reconcile the source baseline"
        )


def git_dirty_paths(root: Path) -> set[str]:
    proc = run_git(
        root,
        ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
        binary=True,
    )
    records = proc.stdout.split(b"\0")
    paths: set[str] = set()
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if len(record) < 4:
            raise WorkflowError("could not parse git status output")
        status = record[:2].decode("ascii", "replace")
        paths.add(record[3:].decode("utf-8", "surrogateescape"))
        if "R" in status or "C" in status:
            if index >= len(records) or not records[index]:
                raise WorkflowError("could not parse renamed path from git status")
            paths.add(records[index].decode("utf-8", "surrogateescape"))
            index += 1
    return paths


MUTABLE_STATE_FILES = {
    CONFIG_NAME,
    CONFIG_SEAL_NAME,
    MANIFEST_NAME,
    HEADING_MAP_NAME,
    "glossary.tsv",
    "term-candidates.tsv",
    STYLE_WATCH_NAME,
    "style-guide.md",
    "voice-cards.md",
    "source-issues.tsv",
    "lessons.md",
}


def is_support_path(root: Path, path: str, config: dict[str, Any], unit: dict[str, Any]) -> bool:
    state_prefix = STATE_REL.as_posix() + "/"
    if path.startswith(state_prefix):
        relative = path[len(state_prefix):]
        if relative in MUTABLE_STATE_FILES:
            return True
        for directory in (REPORTS_DIR, REVIEWS_DIR, WORK_DIR):
            if directory == REPORTS_DIR and relative.startswith(f"{REPORTS_DIR}/regression/"):
                return True
            if directory == REPORTS_DIR and relative.startswith(f"{REPORTS_DIR}/history/"):
                return True
            if relative == directory or relative.startswith(f"{directory}/{unit['id']}/"):
                return True
            if directory == REPORTS_DIR and relative == f"{REPORTS_DIR}/{unit['id']}.json":
                return True
        expected = config.get("sealed_support_hashes", {}).get(path)
        candidate = root / path
        return bool(expected and candidate.exists() and static_support_identity(candidate) == expected)
    expected = config.get("sealed_support_hashes", {}).get(path)
    candidate = root / path
    return bool(expected and candidate.exists() and static_support_identity(candidate) == expected)


def ensure_start_scope(root: Path, config: dict[str, Any], manifest: dict[str, Any], unit: dict[str, Any]) -> None:
    dirty = git_dirty_paths(root)
    content = {item["path"] for item in manifest["units"]}
    unexpected = sorted(path for path in dirty if path not in content and not is_support_path(root, path, config, unit))
    if unexpected:
        raise WorkflowError("unrelated worktree changes must be resolved before start: " + ", ".join(unexpected[:12]))
    dirty_content = sorted(path for path in dirty if path in content)
    other_content = [path for path in dirty_content if path != unit["path"]]
    if other_content:
        raise WorkflowError("other content units are dirty: " + ", ".join(other_content[:12]))
    if unit["status"] == "pending" and unit["path"] in dirty_content:
        raise WorkflowError("the pending unit already has unrecorded edits; inspect or commit them before start")


def unit_heading_mapping(root: Path, config: dict[str, Any], unit: dict[str, Any]) -> dict[str, str]:
    source_value = source_text(root, config["source_commit"], unit["path"])
    target_value = (root / unit["path"]).read_text(encoding="utf-8")
    src_rows = heading_rows(source_value)
    dst_rows = heading_rows(target_value)
    return validated_heading_mapping(src_rows, dst_rows)


def heading_rewrite_mapping(
    root: Path, config: dict[str, Any], unit: dict[str, Any], current: dict[str, str]
) -> dict[str, str]:
    """Add prior translated anchors as one-generation aliases for revision-safe resynchronization."""
    result = dict(current)
    state_path = state_dir(root) / HEADING_MAP_NAME
    if not state_path.exists():
        return result
    state = load_json(state_path)
    previous_record = state.get("files", {}).get(unit["path"], {})
    if previous_record.get("source_commit") != config["source_commit"]:
        return result
    for source_heading, old_target in previous_record.get("headings", {}).items():
        new_target = current.get(source_heading)
        if not old_target or not new_target or old_target == new_target:
            continue
        if old_target in result and result[old_target] != new_target:
            raise WorkflowError(f"prior heading alias is ambiguous: {old_target!r}")
        result[old_target] = new_target
    return result


def validate_heading_map_entry(
    root: Path, config: dict[str, Any], unit: dict[str, Any]
) -> list[str]:
    if not unit["path"].endswith(".md"):
        return []
    state_path = state_dir(root) / HEADING_MAP_NAME
    if not regular_state_file_ok(state_path):
        return [f"heading-map state is missing/non-regular/wrong-mode: {state_path}"]
    try:
        state = load_json(state_path)
        source_value = source_text(root, config["source_commit"], unit["path"])
        target_value = (root / unit["path"]).read_bytes().decode("utf-8")
        src_rows = heading_rows(source_value)
        dst_rows = heading_rows(target_value)
        mapping = validated_heading_mapping(src_rows, dst_rows)
    except (WorkflowError, UnicodeDecodeError) as exc:
        return [f"cannot validate heading map for {unit['path']}: {exc}"]
    record = state.get("files", {}).get(unit["path"], {})
    expected = {
        "unit_id": unit["id"],
        "source_commit": config["source_commit"],
        "source_heading_sha256": sha256_text("\n".join(row["plain"] for row in src_rows)),
        "target_heading_sha256": sha256_text("\n".join(row["plain"] for row in dst_rows)),
        "headings": mapping,
    }
    if any(record.get(key) != value for key, value in expected.items()):
        return [f"heading-map entry is missing or stale: {unit['path']}"]
    return []


def ensure_finish_scope(root: Path, config: dict[str, Any], manifest: dict[str, Any], unit: dict[str, Any]) -> None:
    current_head = run_git(root, ["rev-parse", "HEAD"]).stdout.strip()
    if not unit.get("started_head") or unit["started_head"] != current_head:
        raise WorkflowError("HEAD changed during the active unit; reconcile or undo premature commits before finish")
    dirty = git_dirty_paths(root)
    content = {item["path"] for item in manifest["units"]}
    unexpected = sorted(path for path in dirty if path not in content and not is_support_path(root, path, config, unit))
    if unexpected:
        raise WorkflowError("unrelated worktree changes must be resolved before finish: " + ", ".join(unexpected[:12]))
    other_content = sorted(path for path in dirty if path in content and path != unit["path"])
    if not other_content:
        return
    if not unit["path"].endswith(".md"):
        raise WorkflowError("a Canvas unit cannot produce inbound Markdown content changes")
    mapping = heading_rewrite_mapping(root, config, unit, unit_heading_mapping(root, config, unit))
    paths = [item["path"] for item in manifest["units"]]
    index = wiki_file_index(paths)
    status_by_path = {item["path"]: item["status"] for item in manifest["units"]}
    invalid: list[str] = []
    for path in other_content:
        if not path.endswith((".md", ".canvas")):
            invalid.append(path)
            continue
        head_proc = run_git(root, ["show", f"HEAD:{path}"], binary=True, check=False)
        if head_proc.returncode != 0 or not (root / path).exists():
            invalid.append(path)
            continue
        head_text = head_proc.stdout.decode("utf-8")
        rewrite = rewrite_links_for_unit if path.endswith(".md") else rewrite_canvas_links_for_unit
        expected, problems = rewrite(
            head_text,
            current_path=path,
            target_path=unit["path"],
            index=index,
            mapping=mapping,
            preserve_english_display=status_by_path.get(path) in {"pending", "skipped"},
        )
        current = (root / path).read_bytes().decode("utf-8")
        if problems or current != expected:
            invalid.append(path)
    if invalid:
        raise WorkflowError(
            "non-unit content changes are not pure generated inbound-link updates: " + ", ".join(invalid[:12])
        )


def source_bytes(root: Path, commit: str, rel_path: str) -> bytes:
    proc = run_git(root, ["show", f"{commit}:{rel_path}"], binary=True)
    return proc.stdout


def source_text(root: Path, commit: str, rel_path: str) -> str:
    data = source_bytes(root, commit, rel_path)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WorkflowError(f"source file is not UTF-8: {rel_path}") from exc


def git_mode(root: Path, commit: str, rel_path: str) -> str:
    out = run_git(root, ["ls-tree", commit, "--", rel_path]).stdout.strip()
    return out.split(maxsplit=1)[0] if out else ""


def worktree_git_mode(path: Path) -> str:
    mode = path.lstat().st_mode
    if stat.S_ISLNK(mode):
        return "120000"
    if not stat.S_ISREG(mode):
        return f"non-regular:{stat.S_IFMT(mode):o}"
    return "100755" if mode & 0o111 else "100644"


def head_bytes(root: Path, rel_path: str) -> bytes | None:
    proc = run_git(root, ["show", f"HEAD:{rel_path}"], binary=True, check=False)
    return proc.stdout if proc.returncode == 0 else None


def expected_head_sha256(unit: dict[str, Any]) -> str:
    return unit.get("expected_head_sha256") or unit["source_sha256"]


def authority_hashes(root: Path) -> dict[str, str]:
    state = state_dir(root)
    return {
        name: sha256_bytes((state / name).read_bytes()) if (state / name).exists() else "missing"
        for name in AUTHORITY_FILES
    }


def validate_completed_evidence(
    root: Path, config: dict[str, Any], unit: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    errors.extend(validate_heading_map_entry(root, config, unit))
    required = (
        "translator", "started_at", "started_head", "started_config_sha256", "prestart_sha256",
        "initial_ledger_sha256",
        "completed_at", "target_sha256", "qa_report", "completed_project_hashes",
        "completed_workflow_hashes", "semantic_target_sha256", "completion_minimum_review_score",
        "completed_work_hashes",
    )
    if not all(unit.get(key) for key in required) or not unit.get("learning_recorded"):
        return [f"completed unit lacks lifecycle evidence: {unit.get('path', '<missing>')}"]
    if unit.get("target_sha256") == unit.get("source_sha256"):
        errors.append(f"completed unit target is identical to its English source: {unit['path']}")
    work_directory = unit_work_dir(root, unit)
    if any(not regular_state_file_ok(work_directory / name) for name in ("segments.json", "progress.json", "ledger.md")):
        errors.append(f"completed unit work evidence is missing/non-regular/wrong-mode: {unit['path']}")
    elif unit_work_hashes(root, unit) != unit.get("completed_work_hashes"):
        errors.append(f"completed unit work evidence hash drifted: {unit['path']}")
    expected_report_rel = (STATE_REL / REPORTS_DIR / f"{unit['id']}.json").as_posix()
    if unit.get("qa_report") != expected_report_rel:
        errors.append(f"completed unit has a noncanonical QA report path: {unit['path']}")
    if not regular_state_file_ok(root / expected_report_rel):
        errors.append(f"completed unit QA report is missing/non-regular/wrong-mode: {unit['path']}")
        return errors
    try:
        report = load_json(root / expected_report_rel)
    except WorkflowError as exc:
        errors.append(str(exc))
        return errors
    if (
        report.get("schema_version") != 1
        or not report.get("pass")
        or report.get("unit_id") != unit["id"]
        or report.get("path") != unit["path"]
        or report.get("source_commit") != config["source_commit"]
        or report.get("source_sha256") != unit["source_sha256"]
        or report.get("target_sha256") != unit["target_sha256"]
        or report.get("workflow_hashes") != unit.get("completed_workflow_hashes")
        or report.get("project_hashes") != unit.get("completed_project_hashes")
    ):
        errors.append(f"completed unit QA identity is missing, failing, or stale: {unit['path']}")
        return errors
    try:
        validate_style_flags_report(report)
    except WorkflowError as exc:
        errors.append(str(exc))
        return errors
    semantic_is_current = unit["target_sha256"] == unit["semantic_target_sha256"]
    review_dir = state_dir(root) / REVIEWS_DIR / unit["id"]
    reviews: list[dict[str, Any]] = []
    russian_style_review: dict[str, Any] | None = None
    for role in config.get("required_review_roles", []):
        review_path = review_dir / f"{role}.json"
        if not regular_state_file_ok(review_path):
            errors.append(f"completed unit {role} review is missing/non-regular/wrong-mode: {unit['path']}")
            continue
        try:
            review = load_json(review_path)
            validate_review_identity(review, unit, role)
            validate_style_review_record(review, report if semantic_is_current else None)
        except WorkflowError as exc:
            errors.append(str(exc))
            continue
        if review.get("verdict") != "pass":
            errors.append(f"completed unit has a non-passing {role} review: {unit['path']}")
        issue_counts = review.get("issue_counts", {})
        category_scores = review.get("category_scores", {})
        if (
            review.get("score", 0) < unit.get("completion_minimum_review_score", 90)
            or review.get("unresolved_issues") != 0
            or set(issue_counts) != {"blocker", "major", "minor"}
            or issue_counts.get("blocker") != 0
            or issue_counts.get("major") != 0
            or set(category_scores) != {"fidelity", "mechanics", "terminology", "language", "navigation", "typography"}
            or min(category_scores.values(), default=0) < 4
        ):
            errors.append(f"completed unit {role} review does not meet the quality gate: {unit['path']}")
        reviews.append(review)
        if role == "russian-style":
            russian_style_review = review
    if len({review.get("reviewer") for review in reviews}) != len(reviews):
        errors.append(f"completed unit review roles are not independent: {unit['path']}")
    learning_path = review_dir / "learning.json"
    if not regular_state_file_ok(learning_path):
        errors.append(f"completed unit learning is missing/non-regular/wrong-mode: {unit['path']}")
        return errors
    try:
        learning = load_json(learning_path)
    except WorkflowError as exc:
        errors.append(str(exc))
        return errors
    if (
        learning.get("schema_version") != 1
        or learning.get("unit_id") != unit["id"]
        or learning.get("path") != unit["path"]
        or not learning.get("terms_reviewed")
        or not learning.get("style_watch_reviewed")
        or not str(learning.get("curator", "")).strip()
    ):
        errors.append(f"completed unit learning identity is invalid: {unit['path']}")
    semantic_hash = unit["semantic_target_sha256"]
    if unit["target_sha256"] == semantic_hash:
        for review in reviews:
            if qa_identity(review) != qa_identity(report):
                errors.append(f"completed unit review identity is stale: {unit['path']}")
        if qa_identity(learning) != qa_identity(report):
            errors.append(f"completed unit learning identity is stale: {unit['path']}")
    else:
        semantic_identity: dict[str, Any] | None = None
        for review in reviews:
            identity = qa_identity(review)
            if identity.get("target_sha256") != semantic_hash:
                errors.append(f"semantic review target is not the recorded semantic completion: {unit['path']}")
            if semantic_identity is None:
                semantic_identity = identity
            elif identity != semantic_identity:
                errors.append(f"semantic review identities disagree after link revalidation: {unit['path']}")
        if semantic_identity is None or qa_identity(learning) != semantic_identity:
            errors.append(f"semantic learning evidence is stale after link revalidation: {unit['path']}")
        try:
            link_path = review_dir / "link-consistency.json"
            if not regular_state_file_ok(link_path):
                raise WorkflowError(f"link-consistency record is missing/non-regular/wrong-mode: {link_path}")
            link_review = load_json(link_path)
        except WorkflowError as exc:
            errors.append(str(exc))
        else:
            link_reviewer = str(link_review.get("reviewer", "")).strip()
            trigger_translator = str(
                (link_review.get("trigger") or {}).get("trigger_translator", "")
            ).strip() or None
            if (
                link_review.get("schema_version") != 1
                or link_review.get("unit_id") != unit["id"]
                or link_review.get("path") != unit["path"]
                or link_review.get("role") != "link-consistency"
                or link_review.get("verdict") != "pass"
                or qa_identity(link_review) != qa_identity(report)
                or not link_reviewer
                or not trigger_translator
                or link_reviewer in {unit.get("translator"), trigger_translator}
            ):
                errors.append(f"link-consistency evidence is stale or invalid: {unit['path']}")
            if russian_style_review is None:
                errors.append(f"link-revalidated completion lacks its semantic Russian-style review: {unit['path']}")
            else:
                try:
                    validate_link_style_transition(
                        link_review.get("style_transition"),
                        str(russian_style_review.get("style_flags_sha256", "")),
                        report,
                        unit,
                        link_reviewer,
                        trigger_translator,
                    )
                except WorkflowError as exc:
                    errors.append(str(exc))
        if not unit.get("link_consistency_reviewed_at") or not unit.get("link_consistency_reviewer"):
            errors.append(f"link-revalidated completion lacks reviewer provenance: {unit['path']}")
    return errors


def validate_source_metadata(root: Path, config: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = [
        *core_state_file_errors(root),
        *validate_config_contract(config),
        *validate_authority_state(root),
    ]
    if manifest.get("source_commit") != config.get("source_commit"):
        errors.append("manifest source commit differs from config")
    if manifest.get("workflow_version") != config.get("workflow_version"):
        errors.append("manifest workflow version differs from config")
    if manifest.get("schema_version") != 1:
        errors.append("unsupported manifest schema")
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    expected_paths = set(source_paths(root, config["source_commit"]))
    manifest_paths = {unit.get("path", "") for unit in manifest.get("units", [])}
    manifest_ids = {unit.get("id", "") for unit in manifest.get("units", [])}
    missing = sorted(expected_paths - manifest_paths)
    extra = sorted(manifest_paths - expected_paths)
    if missing:
        errors.append("manifest omits pinned content units: " + ", ".join(missing[:8]))
    if extra:
        errors.append("manifest contains non-pinned content units: " + ", ".join(extra[:8]))
    expected_units: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for path in sorted(expected_paths):
        unit_id, kind, order = classify_unit(path)
        base = unit_id
        suffix = 2
        while unit_id in used_ids:
            unit_id = f"{base}-{suffix}"
            suffix += 1
        used_ids.add(unit_id)
        expected_units.append({"id": unit_id, "path": path, "kind": kind, "order": order})
    expected_units.sort(key=lambda item: (item["order"], item["path"]))
    for sequence, item in enumerate(expected_units, start=1):
        item["sequence"] = sequence
    canonical_by_path = {item["path"]: item for item in expected_units}
    actual_order = [(unit.get("id"), unit.get("path")) for unit in manifest.get("units", [])]
    canonical_order = [(unit["id"], unit["path"]) for unit in expected_units]
    if actual_order != canonical_order:
        errors.append("manifest unit list is not in canonical arc/supplement order")
    for unit in manifest.get("units", []):
        unit_id = unit.get("id", "<missing>")
        path = unit.get("path", "")
        if unit_id in seen_ids:
            errors.append(f"duplicate unit id: {unit_id}")
        if path in seen_paths:
            errors.append(f"duplicate unit path: {path}")
        seen_ids.add(unit_id)
        seen_paths.add(path)
        canonical = canonical_by_path.get(path)
        if canonical and any(unit.get(key) != canonical[key] for key in ("id", "kind", "order", "sequence")):
            errors.append(f"noncanonical unit identity/order metadata: {path}")
        status = unit.get("status")
        if status not in UNIT_STATUSES:
            errors.append(f"invalid unit status {status!r}: {path}")
        try:
            data = source_bytes(root, config["source_commit"], path)
        except WorkflowError:
            errors.append(f"pinned source is missing: {path}")
            continue
        if sha256_bytes(data) != unit.get("source_sha256"):
            errors.append(f"pinned source hash does not match manifest: {path}")
        if source_format(data) != unit.get("source_format"):
            errors.append(f"pinned source byte format does not match manifest: {path}")
        if git_mode(root, config["source_commit"], path) != unit.get("source_mode"):
            errors.append(f"pinned source mode does not match manifest: {path}")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"pinned source is not UTF-8: {path}")
            continue
        words = content_word_count(path, text)
        canonical_empty = not text.strip() or words == 0
        if canonical_empty and status != "skipped":
            errors.append(f"empty pinned unit must remain skipped: {path}")
        if canonical_empty and unit.get("skip_reason") != "empty source placeholder":
            errors.append(f"skipped empty unit lacks its canonical reason: {path}")
        if not canonical_empty and status == "skipped":
            errors.append(f"nonempty pinned unit cannot be skipped: {path}")
        expected_counts = {
            "source_words": words,
            "source_lines": text.count("\n") + (0 if text.endswith("\n") else 1),
            "source_headings": len(heading_rows(text)) if path.endswith(".md") else 0,
        }
        if any(unit.get(key) != value for key, value in expected_counts.items()):
            errors.append(f"source count metadata is noncanonical: {path}")
        recorded_head_hash = unit.get("expected_head_sha256") or unit.get("source_sha256", "")
        if not re.fullmatch(r"[0-9a-f]{64}", str(recorded_head_hash)):
            errors.append(f"invalid expected HEAD hash: {path}")
        generated = unit.get("generated_link_update")
        chain_valid = False
        if generated:
            cursor = unit.get("source_sha256")
            chain = generated.get("chain", [])
            chain_valid = (
                generated.get("origin_source_sha256") == unit.get("source_sha256")
                and isinstance(chain, list)
                and bool(chain)
            )
            if chain_valid:
                for event in chain:
                    if (
                        not isinstance(event, dict)
                        or event.get("previous_sha256") != cursor
                        or not re.fullmatch(r"[0-9a-f]{64}", str(event.get("target_sha256", "")))
                        or event.get("trigger_unit") not in manifest_ids
                        or not event.get("updated_at")
                    ):
                        chain_valid = False
                        break
                    cursor = event["target_sha256"]
            if chain_valid:
                latest = chain[-1]
                chain_valid = (
                    cursor == recorded_head_hash
                    and generated.get("target_sha256") == cursor
                    and generated.get("previous_sha256") == latest.get("previous_sha256")
                    and generated.get("trigger_unit") == latest.get("trigger_unit")
                )
            if not chain_valid:
                errors.append(f"invalid generated-link HEAD hash chain: {path}")
        if recorded_head_hash != unit.get("source_sha256") and not chain_valid:
            errors.append(f"non-source expected HEAD hash lacks generated-link provenance: {path}")
        if status in ACTIVE_TRANSLATION_STATUSES and not all(
            unit.get(key) for key in (
                "translator", "started_at", "started_head", "started_config_sha256",
                "prestart_sha256", "initial_ledger_sha256",
            )
        ):
            errors.append(f"active unit lacks start provenance: {path}")
        if status == "completed" and not re.fullmatch(r"[0-9a-f]{64}", str(unit.get("target_sha256", ""))):
            errors.append(f"completed unit lacks a valid target hash: {path}")
        if status == "completed":
            errors.extend(validate_completed_evidence(root, config, unit))
            target_path = root / path
            if (
                not target_path.exists()
                or sha256_bytes(target_path.read_bytes()) != unit.get("target_sha256")
                or worktree_git_mode(target_path) != unit.get("source_mode")
            ):
                errors.append(f"completed target bytes/mode drifted: {path}")
        if status == "consistency_review":
            errors.extend(validate_completed_evidence(root, config, unit))
            record = unit.get("consistency_review", {})
            if not all(record.get(key) for key in ("trigger_unit", "previous_target_sha256", "target_sha256", "reason")):
                errors.append(f"consistency-review unit lacks provenance: {path}")
            elif record.get("trigger_unit") not in manifest_ids:
                errors.append(f"consistency-review trigger unit is missing: {path}")
            target_path = root / path
            if (
                not target_path.exists()
                or sha256_bytes(target_path.read_bytes()) != record.get("target_sha256")
                or worktree_git_mode(target_path) != unit.get("source_mode")
            ):
                errors.append(f"consistency-review target bytes/mode drifted: {path}")
        if status == "stale_source" and not all(
            unit.get(key) for key in ("stale_detected_at", "expected_head_sha256", "actual_head_sha256")
        ):
            errors.append(f"stale-source unit lacks drift provenance: {path}")
    return errors


def edition_evidence_ok(root: Path, config: dict[str, Any]) -> bool:
    edition = config.get("edition", {})
    if edition.get("system") != "D&D 5e" or edition.get("baseline") != "2014 rules":
        return False
    try:
        evidence = source_text(root, config["source_commit"], "Introduction/Using This Guide.md")
    except WorkflowError:
        return False
    return bool(re.search(r"\b2014 Rules\b", evidence, re.IGNORECASE))


def source_paths(root: Path, commit: str) -> list[str]:
    proc = run_git(root, ["ls-tree", "-r", "-z", "--name-only", commit], binary=True)
    paths = proc.stdout.decode("utf-8").split("\0")
    return sorted(
        path for path in paths
        if path
        and Path(path).suffix.lower() in CONTENT_SUFFIXES
        and path.startswith(CONTENT_ROOTS)
    )


def content_word_count(path: str, text: str) -> int:
    if path.endswith(".canvas"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return 0
        fragments: list[str] = []
        for node in payload.get("nodes", []):
            if isinstance(node, dict) and isinstance(node.get("text"), str):
                fragments.append(node["text"])
        for edge in payload.get("edges", []):
            if isinstance(edge, dict) and isinstance(edge.get("label"), str):
                fragments.append(edge["label"])
        text = "\n".join(fragments)
    return len(re.findall(r"\b[\w’'-]+\b", text, re.UNICODE))


def slugify(value: str) -> str:
    value = value.lower().replace("'", "").replace("’", "")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "unit"


def classify_unit(path: str) -> tuple[str, str, int]:
    name = Path(path).stem
    arc_match = re.match(r"Arc ([A-U])\s+-\s+", name)
    if arc_match:
        letter = arc_match.group(1)
        return f"arc-{letter.lower()}", "arc", (ord(letter) - ord("A") + 1) * 10
    act_match = re.match(r"Act (I|II|III|IV) Summary", name)
    if act_match:
        after_arc = {"I": 35, "II": 95, "III": 175, "IV": 215}
        return f"act-{act_match.group(1).lower()}-summary", "act-summary", after_arc[act_match.group(1)]
    if name == "Epilogue":
        return "epilogue", "epilogue", 220
    if path.startswith("Appendices/"):
        order = {"Amber Shards": 300, "Bestiary": 310, "Non-Player Characters": 320, "Glossary": 330}
        return f"appendix-{slugify(name)}", "appendix", order.get(name, 340)
    chapter_match = re.match(r"Chapter (\d+) - ", path)
    if chapter_match:
        chapter = int(chapter_match.group(1))
        preferred = {
            "Session Zero": 0,
            "Character Creation": 1,
            "Lore of Barovia": 0,
            "History of Barovia": 1,
            "Strahd von Zarovich": 2,
            "Adventure Summary": 0,
            "Running the Adventure": 1,
        }
        return f"chapter-{chapter}-{slugify(name)}", "chapter", 400 + chapter * 20 + preferred.get(name, 9)
    if path.startswith("Introduction/"):
        preferred = {"A DM's Guide to Curse of Strahd": 0, "Using This Guide": 1, "Changelog": 9}
        return f"introduction-{slugify(name)}", "introduction", 500 + preferred.get(name, 5)
    if path.endswith(".canvas"):
        return f"canvas-{slugify(name)}", "canvas", 600
    if path.startswith("_other/templates/"):
        return f"template-{slugify(name)}", "template", 700
    return slugify(name), "supplement", 650


def source_format(data: bytes) -> dict[str, Any]:
    payload = data[3:] if data.startswith(b"\xef\xbb\xbf") else data
    endings = re.findall(b"\r\n|\r|\n", payload)
    crlf = payload.count(b"\r\n")
    lf = payload.count(b"\n") - crlf
    bare_cr = payload.count(b"\r") - crlf
    styles = sum(bool(value) for value in (crlf, lf, bare_cr))
    if styles > 1:
        eol = "mixed"
    elif crlf:
        eol = "crlf"
    elif lf:
        eol = "lf"
    elif bare_cr:
        eol = "cr"
    else:
        eol = "none"
    return {
        "bom": data.startswith(b"\xef\xbb\xbf"),
        "eol": eol,
        "eol_sequence_sha256": sha256_bytes(b"\x00".join(endings)),
        "final_newline": data.endswith(b"\n"),
    }


def heading_rows(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for match in HEADING_RE.finditer(text):
        label = match.group(2).strip()
        plain = plain_heading(label)
        code_match = SCENE_CODE_RE.match(plain)
        rows.append(
            {
                "level": len(match.group(1)),
                "label": label,
                "plain": plain,
                "code": code_match.group(1) if code_match else "",
                "line": text.count("\n", 0, match.start()) + 1,
            }
        )
    return rows


def plain_heading(value: str) -> str:
    value = re.sub(r"<[^>\n]+>", "", value)
    value = re.sub(r"!?(?:\[\[)([^\]]+)(?:\]\])", lambda m: split_wikilink(m.group(1))[1] or split_wikilink(m.group(1))[0], value)
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = value.replace("`", "").replace("*", "").replace("_", "")
    return re.sub(r"\s+", " ", value).strip()


def validated_heading_mapping(
    src_rows: list[dict[str, Any]], dst_rows: list[dict[str, Any]]
) -> dict[str, str]:
    if len(src_rows) != len(dst_rows):
        raise WorkflowError(f"heading count changed ({len(src_rows)} -> {len(dst_rows)})")
    mapping: dict[str, str] = {}
    reverse: dict[str, set[str]] = {}
    for src, dst in zip(src_rows, dst_rows):
        if src["level"] != dst["level"] or src["code"] != dst["code"]:
            raise WorkflowError(f"heading structure/code drift near source line {src['line']}")
        src_key = normalize_apostrophes(src["plain"])
        dst_key = normalize_apostrophes(dst["plain"])
        if src["plain"] in mapping and mapping[src["plain"]] != dst["plain"]:
            raise WorkflowError(f"ambiguous duplicate source heading: {src['plain']!r}")
        mapping[src["plain"]] = dst["plain"]
        reverse.setdefault(dst_key, set()).add(src_key)
    collisions = [sources for sources in reverse.values() if len(sources) > 1]
    if collisions:
        raise WorkflowError("distinct source headings collapse to the same target anchor")
    return mapping


def build_manifest(root: Path, commit: str, source_ref: str) -> dict[str, Any]:
    units: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for rel_path in source_paths(root, commit):
        data = source_bytes(root, commit, rel_path)
        text = data.decode("utf-8")
        unit_id, kind, order = classify_unit(rel_path)
        original_id = unit_id
        suffix = 2
        while unit_id in used_ids:
            unit_id = f"{original_id}-{suffix}"
            suffix += 1
        used_ids.add(unit_id)
        words = content_word_count(rel_path, text)
        empty = not text.strip() or words == 0
        units.append(
            {
                "id": unit_id,
                "path": rel_path,
                "kind": kind,
                "order": order,
                "status": "skipped" if empty else "pending",
                "skip_reason": "empty source placeholder" if empty else "",
                "source_sha256": sha256_bytes(data),
                "expected_head_sha256": sha256_bytes(data),
                "source_mode": git_mode(root, commit, rel_path),
                "source_format": source_format(data),
                "source_words": words,
                "source_lines": text.count("\n") + (0 if text.endswith("\n") else 1),
                "source_headings": len(heading_rows(text)) if rel_path.endswith(".md") else 0,
            }
        )
    units.sort(key=lambda item: (item["order"], item["path"]))
    for sequence, unit in enumerate(units, start=1):
        unit["sequence"] = sequence
    return {
        "schema_version": 1,
        "workflow_version": 2,
        "source_commit": commit,
        "source_ref_at_init": source_ref,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "units": units,
    }


def cmd_init(args: argparse.Namespace) -> int:
    root = repo_root()
    ensure_mutation_branch(root)
    state = state_dir(root)
    config_path = state / CONFIG_NAME
    manifest_path = state / MANIFEST_NAME
    if (config_path.exists() or manifest_path.exists()) and not args.force:
        raise WorkflowError("translation state already exists; use --force only to rebuild it intentionally")
    commit = run_git(root, ["rev-parse", args.source_ref]).stdout.strip()
    ancestor = run_git(root, ["merge-base", "--is-ancestor", commit, "HEAD"], check=False)
    if ancestor.returncode != 0:
        raise WorkflowError(f"source ref {args.source_ref!r} is not an ancestor of HEAD")
    state.mkdir(parents=True, exist_ok=True)
    support_identities = compute_static_support_hashes(root)
    ensure_static_support_regular(support_identities)
    config = {
        "schema_version": 1,
        "workflow_version": 2,
        "project": "Curse of Strahd: Reloaded",
        "source_language": "en",
        "target_language": "ru",
        "source_ref_at_init": args.source_ref,
        "source_commit": commit,
        "edition": {
            "system": "D&D 5e",
            "baseline": "2014 rules",
            "exceptions": "explicitly cited 2024 elements and Reloaded homebrew only",
            "forbid_implicit_conversion": True,
        },
        "protected_branches": sorted(DEFAULT_PROTECTED_BRANCHES),
        "sealed_support_hashes": support_identities,
        "workflow_seal_history": [
            {"sealed_at": utc_now(), "reason": "initial workflow initialization", "branch": current_branch(root)}
        ],
        "required_review_roles": ["fidelity", "russian-style"],
        "minimum_review_score": 90,
        "maximum_segment_words": 2200,
        "minimum_cyrillic_letter_ratio": 0.35,
        "yaml_translatable_keys": ["description", "keywords", "title", "aliases"],
        "content_roots": list(CONTENT_ROOTS),
        "created_at": utc_now(),
    }
    manifest = build_manifest(root, commit, args.source_ref)
    if args.force:
        shutil.rmtree(state / REPORTS_DIR, ignore_errors=True)
        shutil.rmtree(state / REVIEWS_DIR, ignore_errors=True)
        shutil.rmtree(state / WORK_DIR, ignore_errors=True)
    state.mkdir(parents=True, exist_ok=True)
    (state / REPORTS_DIR).mkdir(exist_ok=True)
    (state / REVIEWS_DIR).mkdir(exist_ok=True)
    atomic_write_json(config_path, config)
    write_config_seal(root, config_path)
    atomic_write_json(manifest_path, manifest)
    atomic_write_json(state / HEADING_MAP_NAME, {"schema_version": 1, "files": {}})
    print(f"Initialized {len(manifest['units'])} units from {commit[:12]} on {current_branch(root)}")
    return 0


def unit_by_arg(manifest: dict[str, Any], value: str | None, *, default_next: bool = False) -> dict[str, Any]:
    units = manifest["units"]
    if value is None and default_next:
        active = active_units(manifest)
        if len(active) == 1:
            return active[0]
        if len(active) > 1:
            raise WorkflowError("manifest contains more than one active unit")
        for unit in units:
            if unit["status"] == "pending":
                return unit
        raise WorkflowError("no pending translation unit remains")
    if value is None:
        raise WorkflowError("a unit id or path is required")
    exact = [u for u in units if value in {u["id"], u["path"]}]
    if len(exact) == 1:
        return exact[0]
    basename = [u for u in units if value == Path(u["path"]).name or value == Path(u["path"]).stem]
    if len(basename) == 1:
        return basename[0]
    if len(basename) > 1:
        raise WorkflowError(f"ambiguous unit {value!r}; use its id or full path")
    raise WorkflowError(f"unknown unit {value!r}")


def active_units(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        unit for unit in manifest["units"]
        if unit["status"] in ACTIVE_TRANSLATION_STATUSES | {"consistency_review"}
    ]


def outstanding_consistency_units(manifest: dict[str, Any], trigger_unit_id: str) -> list[str]:
    return [
        unit["id"] for unit in manifest["units"]
        if unit.get("status") == "consistency_review"
        and unit.get("consistency_review", {}).get("trigger_unit") == trigger_unit_id
    ]


def require_no_outstanding_consistency(manifest: dict[str, Any], trigger_unit_id: str) -> None:
    pending = outstanding_consistency_units(manifest, trigger_unit_id)
    if pending:
        raise WorkflowError(
            "resolve generated inbound consistency reviews before final review/learning/finish for "
            f"{trigger_unit_id}: " + ", ".join(pending)
        )


def visual_asset_summary(root: Path) -> str:
    path = state_dir(root) / "visual-assets.json"
    if not path.exists():
        return "not initialized"
    payload = load_json(path)
    counts = Counter(item.get("status", "unknown") for item in payload.get("assets", []))
    return ", ".join(f"{key}={counts[key]}" for key in sorted(counts)) or "none"


def cmd_status(args: argparse.Namespace) -> int:
    root = repo_root()
    config, manifest = load_state(root)
    branch = current_branch(root)
    protected = set(config.get("protected_branches", DEFAULT_PROTECTED_BRANCHES))
    source_ok = run_git(root, ["merge-base", "--is-ancestor", config["source_commit"], "HEAD"], check=False).returncode == 0
    metadata_errors = validate_source_metadata(root, config, manifest)
    edition_ok = edition_evidence_ok(root, config)
    config_ok = config_seal_ok(root)
    seal_ok = config.get("sealed_support_hashes", {}) == compute_static_support_hashes(root)
    head_drift: list[str] = []
    head_mode_drift: list[str] = []
    generated_updates_awaiting_commit: list[str] = []
    completed_drift: list[str] = []
    for unit in manifest.get("units", []):
        if unit.get("status") not in {"pending", "skipped"}:
            continue
        data = head_bytes(root, unit["path"])
        if git_mode(root, "HEAD", unit["path"]) != unit.get("source_mode"):
            head_mode_drift.append(unit["id"])
        if data is None or sha256_bytes(data) != expected_head_sha256(unit):
            target = root / unit["path"]
            if (
                unit.get("generated_link_update")
                and target.exists()
                and sha256_bytes(target.read_bytes()) == expected_head_sha256(unit)
            ):
                generated_updates_awaiting_commit.append(unit["id"])
            else:
                head_drift.append(unit["id"])
    for unit in manifest.get("units", []):
        if unit.get("status") != "completed" or not unit.get("target_sha256"):
            continue
        target = root / unit["path"]
        if (
            not target.exists()
            or sha256_bytes(target.read_bytes()) != unit["target_sha256"]
            or worktree_git_mode(target) != unit.get("source_mode")
        ):
            completed_drift.append(unit["id"])
    counts = Counter(unit["status"] for unit in manifest["units"])
    active = active_units(manifest)
    next_unit = next((u for u in manifest["units"] if u["status"] == "pending"), None)
    stale_units = [unit["id"] for unit in manifest.get("units", []) if unit.get("status") == "stale_source"]
    consistency_units = [
        unit["id"] for unit in manifest.get("units", []) if unit.get("status") == "consistency_review"
    ]
    dirty = git_dirty_paths(root)
    content_by_path = {unit["path"]: unit for unit in manifest.get("units", [])}
    allowed_dirty_content: set[str] = {unit["path"] for unit in active}
    for unit in manifest.get("units", []):
        target = root / unit["path"]
        if unit.get("status") in {"pending", "skipped"} and unit.get("generated_link_update") and target.exists():
            if (
                sha256_bytes(target.read_bytes()) == expected_head_sha256(unit)
                and worktree_git_mode(target) == unit.get("source_mode")
            ):
                allowed_dirty_content.add(unit["path"])
        if unit.get("status") == "completed" and target.exists() and unit.get("target_sha256"):
            if (
                sha256_bytes(target.read_bytes()) == unit["target_sha256"]
                and worktree_git_mode(target) == unit.get("source_mode")
            ):
                allowed_dirty_content.add(unit["path"])
    unscoped_dirty_content = sorted(
        path for path in dirty if path in content_by_path and path not in allowed_dirty_content
    )
    scope_units = active or [
        content_by_path[path] for path in sorted(allowed_dirty_content & dirty) if path in content_by_path
    ]
    if not scope_units and next_unit is not None:
        scope_units = [next_unit]
    if not scope_units and manifest.get("units"):
        scope_units = [manifest["units"][0]]
    unexpected_dirty_paths = sorted(
        path for path in dirty
        if path not in content_by_path
        and not any(is_support_path(root, path, config, candidate) for candidate in scope_units)
    )
    healthy = (
        bool(branch) and branch not in protected and source_ok and edition_ok and config_ok and not metadata_errors
        and seal_ok and not head_drift and not head_mode_drift and not completed_drift and not stale_units
        and not consistency_units and not unscoped_dirty_content and not unexpected_dirty_paths
        and len(active) <= 1
    )
    payload = {
        "healthy": healthy,
        "branch": branch,
        "branch_is_mutation_safe": bool(branch) and branch not in protected,
        "source_commit": config["source_commit"],
        "source_is_ancestor": source_ok,
        "source_metadata_errors": metadata_errors,
        "pending_head_drift": head_drift,
        "pending_head_mode_drift": head_mode_drift,
        "generated_updates_awaiting_commit": generated_updates_awaiting_commit,
        "completed_target_drift": completed_drift,
        "stale_source_units": stale_units,
        "consistency_review_units": consistency_units,
        "unscoped_dirty_content": unscoped_dirty_content,
        "unexpected_dirty_paths": unexpected_dirty_paths,
        "workflow_seal_ok": seal_ok,
        "edition": config["edition"],
        "edition_evidence_ok": edition_ok,
        "config_seal_ok": config_ok,
        "counts": dict(sorted(counts.items())),
        "active": [{"id": u["id"], "path": u["path"], "status": u["status"]} for u in active],
        "next": None if next_unit is None else {"id": next_unit["id"], "path": next_unit["path"]},
        "visual_assets": visual_asset_summary(root),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Branch: {payload['branch']}")
        print(f"Source: {config['source_commit'][:12]} (ancestor: {'yes' if source_ok else 'NO'})")
        edition = config["edition"]
        print(f"Edition: {edition.get('system')}, {edition.get('baseline')}; {edition.get('exceptions')}")
        print(f"Integrity: {'healthy' if healthy else 'BLOCKED'}")
        for issue in metadata_errors[:12]:
            print(f"ERROR: {issue}")
        if head_drift:
            print("ERROR: pending HEAD drift: " + ", ".join(head_drift[:12]))
        if head_mode_drift:
            print("ERROR: pending HEAD mode drift: " + ", ".join(head_mode_drift[:12]))
        if generated_updates_awaiting_commit:
            print("Pending generated link updates awaiting commit: " + ", ".join(generated_updates_awaiting_commit[:12]))
        if completed_drift:
            print("ERROR: completed target drift: " + ", ".join(completed_drift[:12]))
        if stale_units:
            print("ERROR: stale source units: " + ", ".join(stale_units[:12]))
        if consistency_units:
            print("ERROR: unresolved link consistency review: " + ", ".join(consistency_units[:12]))
        if unscoped_dirty_content:
            print("ERROR: dirty content outside the active/generated scope: " + ", ".join(unscoped_dirty_content[:12]))
        if unexpected_dirty_paths:
            print("ERROR: unrelated or unsealed dirty paths: " + ", ".join(unexpected_dirty_paths[:12]))
        if not edition_ok:
            print("ERROR: pinned source does not support the configured edition claim")
        if not config_ok:
            print("ERROR: config differs from its reviewed seal")
        if not seal_ok:
            print("ERROR: workflow-support files differ from their reviewed seal")
        print("Units: " + ", ".join(f"{k}={v}" for k, v in payload["counts"].items()))
        print("Active: " + (", ".join(u["id"] for u in active) if active else "none"))
        print("Next: " + (f"{next_unit['id']} — {next_unit['path']}" if next_unit else "none"))
        print(f"Visual assets: {payload['visual_assets']}")
    return 0 if healthy else 2


def cmd_next(args: argparse.Namespace) -> int:
    root = repo_root()
    config, manifest = load_state(root)
    ensure_source_ancestor(root, config)
    metadata_errors = validate_source_metadata(root, config, manifest)
    if metadata_errors:
        raise WorkflowError("source/manifest integrity failure: " + "; ".join(metadata_errors[:8]))
    unit = next((item for item in manifest["units"] if item["status"] == "pending"), None)
    if unit is None:
        raise WorkflowError("no pending translation unit remains")
    if args.json:
        print(json.dumps(unit, ensure_ascii=False, indent=2))
    else:
        print(f"{unit['id']}\t{unit['path']}\t{unit['source_words']} words")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    root = repo_root()
    config, manifest = load_state(root)
    ensure_mutation_branch(root, config)
    ensure_source_ancestor(root, config)
    metadata_errors = validate_source_metadata(root, config, manifest)
    if metadata_errors:
        raise WorkflowError("source/manifest integrity failure: " + "; ".join(metadata_errors[:8]))
    if not edition_evidence_ok(root, config):
        raise WorkflowError("configured edition is not supported by the pinned source evidence")
    translator = args.translator.strip()
    if not translator:
        raise WorkflowError("translator identity must be nonempty")
    stale_units = [item["id"] for item in manifest["units"] if item.get("status") == "stale_source"]
    if stale_units:
        raise WorkflowError("stale source must be reconciled before starting work: " + ", ".join(stale_units[:12]))
    active = active_units(manifest)
    if active:
        raise WorkflowError(f"{active[0]['id']} is already active; finish it before starting another unit")
    drifted: list[str] = []
    awaiting_commit: list[str] = []
    changed_state = False
    for candidate in manifest["units"]:
        if candidate.get("status") not in {"pending", "skipped"}:
            continue
        data = head_bytes(root, candidate["path"])
        actual_hash = sha256_bytes(data) if data is not None else "missing"
        actual_mode = git_mode(root, "HEAD", candidate["path"])
        if actual_hash == expected_head_sha256(candidate) and actual_mode == candidate.get("source_mode"):
            continue
        target = root / candidate["path"]
        if (
            candidate.get("generated_link_update")
            and target.exists()
            and sha256_bytes(target.read_bytes()) == expected_head_sha256(candidate)
            and worktree_git_mode(target) == candidate.get("source_mode")
            and actual_mode == candidate.get("source_mode")
        ):
            awaiting_commit.append(candidate["id"])
            continue
        drifted.append(candidate["id"])
        if candidate["status"] == "pending":
            candidate.update(
                {
                    "status": "stale_source",
                    "stale_detected_at": utc_now(),
                    "expected_head_sha256": expected_head_sha256(candidate),
                    "actual_head_sha256": actual_hash,
                    "expected_head_mode": candidate.get("source_mode"),
                    "actual_head_mode": actual_mode,
                }
            )
            changed_state = True
    if drifted:
        if changed_state:
            save_manifest(root, manifest)
        raise WorkflowError(
            "source/HEAD content or mode drift must be reconciled before translation: " + ", ".join(drifted[:12])
        )
    if awaiting_commit:
        raise WorkflowError(
            "commit the generated inbound-link updates before starting another unit: "
            + ", ".join(awaiting_commit[:12])
        )
    expected_next = next((candidate for candidate in manifest["units"] if candidate["status"] == "pending"), None)
    unit = unit_by_arg(manifest, args.unit, default_next=True)
    if unit["status"] == "stale_source":
        raise WorkflowError("unit has stale HEAD source; reconcile the baseline before translation")
    if unit["status"] != "pending":
        raise WorkflowError(f"cannot start {unit['id']} from status {unit['status']}")
    if (
        unit["status"] == "pending"
        and expected_next is not None
        and expected_next["id"] != unit["id"]
        and not args.reason
    ):
        raise WorkflowError(
            f"{expected_next['id']} is next; use --reason to record why {unit['id']} is selected out of order"
        )
    ensure_start_scope(root, config, manifest, unit)
    target = root / unit["path"]
    if not target.exists():
        raise WorkflowError(f"worktree file is missing: {unit['path']}")
    unit.update(
        {
            "status": "in_progress",
            "translator": translator,
            "started_at": utc_now(),
            "started_head": run_git(root, ["rev-parse", "HEAD"]).stdout.strip(),
            "started_config_sha256": sha256_bytes((state_dir(root) / CONFIG_NAME).read_bytes()),
            "prestart_sha256": sha256_bytes(target.read_bytes()),
            "selection_reason": args.reason or "manifest order",
            "started_project_hashes": project_hashes(root),
            "started_workflow_hashes": workflow_hashes(root),
            "started_authority_hashes": authority_hashes(root),
        }
    )
    review_dir = state_dir(root) / REVIEWS_DIR / unit["id"]
    review_dir.mkdir(parents=True, exist_ok=True)
    for stale in review_dir.glob("*.json"):
        archive_record(stale)
    report = state_dir(root) / REPORTS_DIR / f"{unit['id']}.json"
    if report.exists():
        archive_record(report)
    unit["initial_ledger_sha256"] = initialize_unit_work(root, config, unit)
    save_manifest(root, manifest)
    print(f"Started {unit['id']}: {unit['path']} (translator {translator})")
    return 0


def cmd_reopen(args: argparse.Namespace) -> int:
    root = repo_root()
    config, manifest = load_state(root)
    ensure_mutation_branch(root, config)
    ensure_source_ancestor(root, config)
    metadata_errors = validate_source_metadata(root, config, manifest)
    if metadata_errors:
        raise WorkflowError("source/manifest integrity failure: " + "; ".join(metadata_errors[:8]))
    if active_units(manifest):
        raise WorkflowError("finish the active translation/link review before reopening a completed unit")
    unit = unit_by_arg(manifest, args.unit, default_next=False)
    if unit.get("status") != "completed":
        raise WorkflowError("semantic revision can reopen only a fully evidenced completed unit")
    translator = args.translator.strip()
    reason = args.reason.strip()
    if not translator or not reason:
        raise WorkflowError("reopen requires nonempty translator identity and reviewed reason")
    ensure_start_scope(root, config, manifest, unit)
    if unit["path"] in git_dirty_paths(root):
        raise WorkflowError("commit or resolve the completed target before reopening it")
    target = root / unit["path"]
    target_hash = sha256_bytes(target.read_bytes())
    head_data = head_bytes(root, unit["path"])
    if (
        head_data is None
        or sha256_bytes(head_data) != unit["target_sha256"]
        or target_hash != unit["target_sha256"]
        or git_mode(root, "HEAD", unit["path"]) != unit["source_mode"]
        or worktree_git_mode(target) != unit["source_mode"]
    ):
        raise WorkflowError("completed target must be committed and byte/mode-current before semantic revision")
    prior = {
        key: unit.get(key)
        for key in (
            "completed_at", "target_sha256", "semantic_target_sha256", "qa_report",
            "completed_project_hashes", "completed_workflow_hashes",
            "completion_minimum_review_score", "completed_work_hashes", "translator",
        )
    }
    unit.setdefault("revision_history", []).append(
        {
            "reopened_at": utc_now(),
            "reason": reason,
            "translator": translator,
            "prior_completion": prior,
        }
    )
    report_path = state_dir(root) / REPORTS_DIR / f"{unit['id']}.json"
    archive_record(report_path)
    review_dir = state_dir(root) / REVIEWS_DIR / unit["id"]
    for record in review_dir.glob("*.json"):
        archive_record(record)
    prior_work = archive_unit_work(root, unit)
    for key in (
        "completed_at", "target_sha256", "semantic_target_sha256", "qa_report",
        "completed_project_hashes", "completed_workflow_hashes", "completion_minimum_review_score",
        "completed_work_hashes",
        "consistency_review_resolved_at", "consistency_review_reviewer",
        "link_consistency_reviewed_at", "link_consistency_reviewer",
    ):
        unit.pop(key, None)
    unit.update(
        {
            "status": "in_progress",
            "translator": translator,
            "started_at": utc_now(),
            "started_head": run_git(root, ["rev-parse", "HEAD"]).stdout.strip(),
            "started_config_sha256": sha256_bytes((state_dir(root) / CONFIG_NAME).read_bytes()),
            "prestart_sha256": target_hash,
            "selection_reason": f"semantic revision: {reason}",
            "started_project_hashes": project_hashes(root),
            "started_workflow_hashes": workflow_hashes(root),
            "started_authority_hashes": authority_hashes(root),
            "learning_recorded": False,
            "revision_number": len(unit["revision_history"]),
        }
    )
    initialize_unit_work(root, config, unit)
    ledger = unit_work_dir(root, unit) / "ledger.md"
    if prior_work is not None:
        prior_ledger = prior_work / "ledger.md"
        if prior_ledger.exists():
            relative = prior_ledger.relative_to(root).as_posix()
            atomic_write_text(
                ledger,
                ledger.read_text(encoding="utf-8").rstrip()
                + f"\n\n## Prior revision memory\n\nReview the archived ledger at `{relative}` before drafting.\n",
            )
    unit["initial_ledger_sha256"] = sha256_bytes(ledger.read_bytes())
    save_manifest(root, manifest)
    print(f"Reopened {unit['id']} for semantic revision: {reason}")
    return 0


def archive_unit_work(root: Path, unit: dict[str, Any]) -> Path | None:
    directory = unit_work_dir(root, unit)
    if not directory.exists():
        return None
    history_root = directory / "history"
    history_root.mkdir(parents=True, exist_ok=True)
    destination = history_root / compact_timestamp()
    counter = 2
    while destination.exists():
        destination = history_root / f"{compact_timestamp()}-{counter}"
        counter += 1
    destination.mkdir()
    moved = False
    for child in list(directory.iterdir()):
        if child == history_root:
            continue
        shutil.move(str(child), destination / child.name)
        moved = True
    return destination if moved else None


def split_wikilink(inner: str) -> tuple[str, str]:
    if "|" in inner:
        target, alias = inner.rsplit("|", 1)
        return target, alias
    return inner, ""


def split_wiki_target(target: str) -> tuple[str, list[str]]:
    if "#" not in target:
        return target, []
    file_part, section = target.split("#", 1)
    return file_part, section.split("#")


def unprotected_wikilinks(text: str) -> list[re.Match[str]]:
    spans = protected_spans(text)
    return [match for match in WIKILINK_RE.finditer(text) if not span_is_protected(match.start(), spans)]


def segment_plan(text: str, max_words: int) -> list[dict[str, Any]]:
    if max_words <= 0:
        raise WorkflowError("maximum segment words must be positive")
    lines = text.splitlines()
    starts: list[tuple[int, str]] = [(0, "Preamble")]
    for index, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            if index == 0:
                starts[0] = (0, plain_heading(match.group(2)))
            else:
                starts.append((index, plain_heading(match.group(2))))
    sections: list[dict[str, Any]] = []
    for index, (start, heading) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(lines)
        body = "\n".join(lines[start:end])
        section = {"start": start, "end": end, "heading": heading, "words": content_word_count("x.md", body)}
        sections.extend(split_oversize_section(lines, section, max_words))
    groups: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    current_words = 0
    for section in sections:
        if current and current_words + section["words"] > max_words:
            groups.append(_segment_group(current, current_words, max_words))
            current = []
            current_words = 0
        current.append(section)
        current_words += section["words"]
        if section.get("atomic_oversize"):
            groups.append(_segment_group(current, current_words, max_words))
            current = []
            current_words = 0
    if current:
        groups.append(_segment_group(current, current_words, max_words))
    for number, group in enumerate(groups, start=1):
        group["segment"] = number
    return groups


def _segment_group(sections: list[dict[str, Any]], words: int, max_words: int) -> dict[str, Any]:
    return {
        "start_line": sections[0]["start"] + 1,
        "end_line": sections[-1]["end"],
        "words": words,
        "headings": [section["heading"] for section in sections],
        "oversize": any(section.get("atomic_oversize", False) for section in sections),
        "split_reason": "atomic block exceeds limit" if any(section.get("atomic_oversize", False) for section in sections) else "safe structural boundary",
        "continuation_context": sections[0].get("continuation_context", ""),
    }


HTML_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def safe_paragraph_boundaries(lines: list[str], start: int, end: int, max_words: int) -> list[int]:
    """Return safe exclusive line offsets at blank lines outside code, HTML, lists, tables, and callouts."""
    section_text = "\n".join(lines[start:end])
    protected_lines: set[int] = set()
    for left, right in protected_spans(section_text):
        first = section_text.count("\n", 0, left)
        last = section_text.count("\n", 0, right)
        protected_lines.update(range(first, last + 1))
    depth = 0
    boundaries: list[int] = []
    callouts: list[tuple[int, int, int]] = []
    callout_index = start
    while callout_index < end:
        if not re.match(r"^\s*(?:>\s*)+\[![^\]]+\]", lines[callout_index]):
            callout_index += 1
            continue
        callout_end = callout_index + 1
        while callout_end < end and re.match(r"^\s*(?:>.*)?$", lines[callout_end]):
            if lines[callout_end].strip() and not re.match(r"^\s*>", lines[callout_end]):
                break
            callout_end += 1
        words = content_word_count("x.md", "\n".join(lines[callout_index:callout_end]))
        callouts.append((callout_index, callout_end, words))
        if callout_end < end:
            boundaries.append(callout_end)
        callout_index = callout_end
    for relative, line in enumerate(lines[start:end]):
        protected = relative in protected_lines
        quote_blank = bool(re.fullmatch(r"\s*(?:>\s*)+", line))
        list_item = bool(re.match(r"^\s*(?:>\s*)*(?:[-+*]|\d+[.)])\s+", line))
        if not protected and depth == 0 and relative > 0 and list_item:
            boundaries.append(start + relative)
        for tag in scan_html_tags(line):
            tag_match = re.match(r"<\s*(/?)\s*([A-Za-z0-9-]+)", tag)
            if not tag_match or tag.startswith("<!--") or tag.startswith("<!"):
                continue
            closing, name = tag_match.group(1), tag_match.group(2).casefold()
            if name not in HTML_BLOCK_CONTAINERS:
                continue
            if closing:
                depth = max(0, depth - 1)
            elif not tag.rstrip().endswith("/>") and not re.search(
                rf"</\s*{re.escape(name)}\s*>", tag, re.IGNORECASE
            ):
                depth += 1
        if quote_blank and not protected and depth == 0:
            boundaries.append(start + relative + 1)
            continue
        if line.strip() or protected or depth:
            continue
        previous = lines[start + relative - 1] if relative else ""
        following = lines[start + relative + 1] if start + relative + 1 < end else ""
        structural = (previous, following)
        if any(re.match(r"^\s*(?:>|\||[-+*]\s|\d+[.)]\s| {4}|\t)", value) for value in structural if value):
            continue
        boundaries.append(start + relative + 1)
    def allowed(boundary: int) -> bool:
        containing = next(
            ((left, right, words) for left, right, words in callouts if left < boundary < right),
            None,
        )
        return containing is None or containing[2] > max_words

    return sorted(set(boundary for boundary in boundaries if start < boundary < end and allowed(boundary)))


def split_oversize_section(
    lines: list[str], section: dict[str, Any], max_words: int
) -> list[dict[str, Any]]:
    if section["words"] <= max_words:
        return [section]
    boundaries = safe_paragraph_boundaries(lines, section["start"], section["end"], max_words)
    cuts = [section["start"], *boundaries, section["end"]]
    blocks: list[dict[str, Any]] = []
    for left, right in zip(cuts, cuts[1:]):
        if right <= left:
            continue
        words = content_word_count("x.md", "\n".join(lines[left:right]))
        blocks.append(
            {
                "start": left,
                "end": right,
                "heading": section["heading"],
                "words": words,
                "atomic_oversize": words > max_words,
                "continuation_context": re.match(
                    r"^(\s*(?:>\s*)*(?:(?:[-+*]|\d+[.)])\s+)?)",
                    lines[left] if left < len(lines) else "",
                ).group(1),
            }
        )
    if len(blocks) <= 1:
        section["atomic_oversize"] = True
        return [section]
    chunks: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    words = 0
    for block in blocks:
        if current and words + block["words"] > max_words:
            chunks.append(
                {
                    "start": current[0]["start"],
                    "end": current[-1]["end"],
                    "heading": section["heading"],
                    "words": words,
                    "atomic_oversize": any(item["atomic_oversize"] for item in current),
                    "continuation_context": current[0].get("continuation_context", ""),
                }
            )
            current = []
            words = 0
        current.append(block)
        words += block["words"]
    if current:
        chunks.append(
            {
                "start": current[0]["start"],
                "end": current[-1]["end"],
                "heading": section["heading"],
                "words": words,
                "atomic_oversize": any(item["atomic_oversize"] for item in current),
                "continuation_context": current[0].get("continuation_context", ""),
            }
        )
    return chunks


def cmd_segments(args: argparse.Namespace) -> int:
    root = repo_root()
    config, manifest = load_state(root)
    unit = unit_by_arg(manifest, args.unit, default_next=True)
    maximum = args.max_words or config["maximum_segment_words"]
    result = plan_unit_segments(root, config, unit, maximum)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def plan_unit_segments(
    root: Path, config: dict[str, Any], unit: dict[str, Any], maximum: int | None = None
) -> list[dict[str, Any]]:
    text = source_text(root, config["source_commit"], unit["path"])
    maximum = maximum or config["maximum_segment_words"]
    if not unit["path"].endswith(".canvas"):
        return segment_plan(text, maximum)
    payload = json.loads(text)
    result: list[dict[str, Any]] = []
    for path, value in iter_canvas_text(payload):
        if canvas_translatable(path):
            result.append(
                {
                    "segment": len(result) + 1,
                    "json_path": format_json_path(path),
                    "words": content_word_count("x.md", value),
                    "oversize": content_word_count("x.md", value) > maximum,
                    "split_reason": "Canvas text field is atomic",
                }
            )
    return result


def unit_work_dir(root: Path, unit: dict[str, Any]) -> Path:
    return state_dir(root) / WORK_DIR / unit["id"]


def unit_work_hashes(root: Path, unit: dict[str, Any]) -> dict[str, str]:
    directory = unit_work_dir(root, unit)
    return {
        name: sha256_bytes((directory / name).read_bytes()) if (directory / name).is_file() else "missing"
        for name in ("segments.json", "progress.json", "ledger.md")
    }


def initialize_unit_work(root: Path, config: dict[str, Any], unit: dict[str, Any]) -> str:
    directory = unit_work_dir(root, unit)
    directory.mkdir(parents=True, exist_ok=True)
    segments = plan_unit_segments(root, config, unit)
    atomic_write_json(
        directory / "segments.json",
        {
            "schema_version": 1,
            "unit_id": unit["id"],
            "path": unit["path"],
            "source_commit": config["source_commit"],
            "source_sha256": unit["source_sha256"],
            "maximum_words": config["maximum_segment_words"],
            "segments": segments,
        },
    )
    atomic_write_json(
        directory / "progress.json",
        {
            "schema_version": 1,
            "unit_id": unit["id"],
            "path": unit["path"],
            "source_sha256": unit["source_sha256"],
            "updated_at": utc_now(),
            "segments": [
                {
                    "segment": item["segment"],
                    "status": "pending",
                    "completed_by": "",
                    "completed_at": "",
                    "notes": "",
                }
                for item in segments
            ],
        },
    )
    ledger = directory / "ledger.md"
    atomic_write_text(
        ledger,
        f"# Translation Ledger — {unit['id']}\n\n"
        "Record only evidence-backed decisions. Promote reusable choices through the reviewed `learn` gate.\n\n"
        "## Entities and relationships\n\n- None recorded.\n\n"
        "## Terminology decisions and candidates\n\n- None recorded.\n\n"
        "## Voice and register observations\n\n- None recorded.\n\n"
        "## Continuity, foreshadowing, and open questions\n\n- None recorded.\n",
    )
    return sha256_bytes(ledger.read_bytes())


def load_progress(root: Path, config: dict[str, Any], unit: dict[str, Any]) -> dict[str, Any]:
    segment_record = load_json(unit_work_dir(root, unit) / "segments.json")
    expected_segments = plan_unit_segments(root, config, unit)
    if (
        segment_record.get("unit_id") != unit["id"]
        or segment_record.get("source_sha256") != unit["source_sha256"]
        or segment_record.get("maximum_words") != config["maximum_segment_words"]
        or segment_record.get("segments") != expected_segments
    ):
        raise WorkflowError("persisted segment plan is stale or tampered")
    progress = load_json(unit_work_dir(root, unit) / "progress.json")
    if progress.get("unit_id") != unit["id"] or progress.get("source_sha256") != unit["source_sha256"]:
        raise WorkflowError("segment progress belongs to a different source/unit")
    expected_ids = [item["segment"] for item in expected_segments]
    actual_ids = [item.get("segment") for item in progress.get("segments", [])]
    if actual_ids != expected_ids or len(actual_ids) != len(set(actual_ids)):
        raise WorkflowError("segment progress does not exactly cover the pinned plan")
    for item in progress["segments"]:
        if item.get("status") not in {"pending", "completed"}:
            raise WorkflowError(f"invalid segment status for segment {item.get('segment')}")
        if item["status"] == "completed" and not all(
            str(item.get(key, "")).strip() for key in ("completed_by", "completed_at", "notes")
        ):
            raise WorkflowError(f"completed segment {item['segment']} lacks provenance/notes")
    return progress


def cmd_progress(args: argparse.Namespace) -> int:
    root = repo_root()
    config, manifest = load_state(root)
    unit = unit_by_arg(manifest, args.unit, default_next=True)
    progress = load_progress(root, config, unit)
    print(json.dumps(progress, ensure_ascii=False, indent=2))
    return 0


def cmd_segment_done(args: argparse.Namespace) -> int:
    root = repo_root()
    config, manifest = load_state(root)
    ensure_mutation_branch(root, config)
    unit = unit_by_arg(manifest, args.unit, default_next=False)
    if unit["status"] not in {"in_progress", "auto_qa_pass", "independent_review", "needs_revision", "approved"}:
        raise WorkflowError("segment completion is only valid for the active translation unit")
    agent = args.agent.strip()
    if not agent:
        raise WorkflowError("segment agent identity must be nonempty")
    notes = Path(args.notes_file).read_text(encoding="utf-8").strip()
    if not notes:
        raise WorkflowError("segment notes must summarize translation and continuity decisions")
    progress = load_progress(root, config, unit)
    record = next((item for item in progress["segments"] if item["segment"] == args.segment), None)
    if record is None:
        raise WorkflowError(f"unknown segment {args.segment} for {unit['id']}")
    incomplete_prior = [
        item["segment"] for item in progress["segments"]
        if item["segment"] < args.segment and item.get("status") != "completed"
    ]
    if incomplete_prior:
        raise WorkflowError(
            "segments must be completed in source order; first complete "
            + ", ".join(map(str, incomplete_prior[:20]))
        )
    record.update(
        {
            "status": "completed",
            "completed_by": agent,
            "completed_at": utc_now(),
            "notes": notes,
        }
    )
    progress["updated_at"] = utc_now()
    atomic_write_json(unit_work_dir(root, unit) / "progress.json", progress)
    print(f"Completed segment {args.segment} for {unit['id']}")
    return 0


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle, delimiter="\t")]


def validated_tsv_rows(path: Path, expected_header: Sequence[str]) -> tuple[list[dict[str, str]], list[str]]:
    errors: list[str] = []
    if not regular_state_file_ok(path):
        return [], [f"authority state is missing/non-regular/wrong-mode: {path}"]
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle, delimiter="\t", strict=True)
            header = next(reader, None)
            if header != list(expected_header):
                return [], [f"authority TSV header is noncanonical: {path}"]
            rows: list[dict[str, str]] = []
            for line_number, values in enumerate(reader, start=2):
                if len(values) != len(expected_header):
                    errors.append(
                        f"authority TSV row {line_number} has {len(values)} fields, "
                        f"expected {len(expected_header)}: {path}"
                    )
                    continue
                if not any(value.strip() for value in values):
                    errors.append(f"authority TSV contains a blank row at line {line_number}: {path}")
                    continue
                rows.append(dict(zip(expected_header, values)))
    except (OSError, UnicodeError, csv.Error) as exc:
        return [], [f"cannot parse authority TSV {path}: {exc}"]
    return rows, errors


def missing_fields(row: dict[str, str], names: Sequence[str]) -> list[str]:
    return [name for name in names if not str(row.get(name, "")).strip()]


def validate_authority_state(root: Path) -> list[str]:
    state = state_dir(root)
    errors: list[str] = []

    glossary, found = validated_tsv_rows(state / "glossary.tsv", GLOSSARY_HEADER)
    errors.extend(found)
    seen_glossary: set[str] = set()
    for line_number, row in enumerate(glossary, start=2):
        required = (
            "source", "approved_ru", "category", "sense_ruleset", "capitalization", "scope",
            "status", "enforce", "evidence", "origin_unit", "reviewer",
        )
        missing = missing_fields(row, required)
        if missing:
            errors.append(f"glossary row {line_number} lacks required fields: {', '.join(missing)}")
        status_value = row.get("status", "").strip()
        if status_value not in {"approved", "provisional", "rejected"}:
            errors.append(f"glossary row {line_number} has invalid status: {status_value!r}")
        enforce = row.get("enforce", "").strip()
        if enforce not in {"yes", "no"}:
            errors.append(f"glossary row {line_number} has invalid enforce value: {enforce!r}")
        if status_value == "approved" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row.get("decision_date", "").strip()):
            errors.append(f"approved glossary row {line_number} lacks a canonical decision date")
        key = row.get("source", "").strip().casefold()
        if key and key in seen_glossary:
            errors.append(f"duplicate glossary source key at row {line_number}: {row.get('source', '')!r}")
        seen_glossary.add(key)

    candidates, found = validated_tsv_rows(state / "term-candidates.tsv", TERM_CANDIDATES_HEADER)
    errors.extend(found)
    seen_candidates: set[str] = set()
    for line_number, row in enumerate(candidates, start=2):
        required = (
            "source", "proposed_ru", "category", "sense_ruleset", "scope", "evidence",
            "origin_unit", "rationale", "proposed_by", "status",
        )
        missing = missing_fields(row, required)
        if missing:
            errors.append(f"term-candidate row {line_number} lacks required fields: {', '.join(missing)}")
        status_value = row.get("status", "").strip()
        if status_value not in {"candidate", "approved", "rejected", "deferred"}:
            errors.append(f"term-candidate row {line_number} has invalid status: {status_value!r}")
        if status_value in {"approved", "rejected", "deferred"}:
            if not row.get("reviewer", "").strip() or not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}", row.get("decision_date", "").strip()
            ):
                errors.append(f"resolved term-candidate row {line_number} lacks reviewer/date evidence")
        key = row.get("source", "").strip().casefold()
        if key and key in seen_candidates:
            errors.append(f"duplicate term-candidate source key at row {line_number}: {row.get('source', '')!r}")
        seen_candidates.add(key)

    style_watch, found = validated_tsv_rows(state / STYLE_WATCH_NAME, STYLE_WATCH_HEADER)
    errors.extend(found)
    seen_watch_ids: set[str] = set()
    seen_watch_literals: dict[str, str] = {}
    for line_number, row in enumerate(style_watch, start=2):
        required = (
            "id", "status", "literals", "category", "guidance", "applicability",
            "exceptions", "evidence", "origin_unit",
        )
        missing = missing_fields(row, required)
        if missing:
            errors.append(f"style-watch row {line_number} lacks required fields: {', '.join(missing)}")
        rule_id = row.get("id", "").strip()
        if not re.fullmatch(r"RUQ-[0-9]{3,}", rule_id):
            errors.append(f"style-watch row {line_number} has an invalid id: {rule_id!r}")
        if rule_id and rule_id in seen_watch_ids:
            errors.append(f"duplicate style-watch id at row {line_number}: {rule_id!r}")
        seen_watch_ids.add(rule_id)
        status_value = row.get("status", "").strip()
        if status_value not in {"candidate", "approved", "rejected", "deferred"}:
            errors.append(f"style-watch row {line_number} has invalid status: {status_value!r}")
        if status_value in {"approved", "rejected", "deferred"}:
            if not row.get("reviewer", "").strip() or not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}", row.get("decision_date", "").strip()
            ):
                errors.append(f"resolved style-watch row {line_number} lacks reviewer/date evidence")
        literals = [item.strip() for item in row.get("literals", "").split(";")]
        if not literals or any(not item for item in literals):
            errors.append(f"style-watch row {line_number} has an empty literal")
        for literal in literals:
            key = literal.casefold()
            previous = seen_watch_literals.get(key)
            if key and previous:
                errors.append(
                    f"duplicate style-watch literal at row {line_number}: {literal!r} "
                    f"(already in {previous})"
                )
            elif key:
                seen_watch_literals[key] = rule_id

    source_issues, found = validated_tsv_rows(state / "source-issues.tsv", SOURCE_ISSUES_HEADER)
    errors.extend(found)
    seen_issue_ids: set[str] = set()
    for line_number, row in enumerate(source_issues, start=2):
        required = (
            "id", "path", "line_or_heading", "category", "description", "translation_policy",
            "status", "evidence_commit", "reviewer",
        )
        missing = missing_fields(row, required)
        if missing:
            errors.append(f"source-issue row {line_number} lacks required fields: {', '.join(missing)}")
        status_value = row.get("status", "").strip()
        if status_value not in {"open", "resolved", "wont-fix"}:
            errors.append(f"source-issue row {line_number} has invalid status: {status_value!r}")
        if not re.fullmatch(r"[0-9a-f]{40}", row.get("evidence_commit", "").strip()):
            errors.append(f"source-issue row {line_number} has an invalid evidence commit")
        issue_id = row.get("id", "").strip()
        if issue_id and issue_id in seen_issue_ids:
            errors.append(f"duplicate source-issue id at row {line_number}: {issue_id!r}")
        seen_issue_ids.add(issue_id)

    for name in ("style-guide.md", "voice-cards.md", "lessons.md"):
        path = state / name
        if not regular_state_file_ok(path):
            errors.append(f"authority state is missing/non-regular/wrong-mode: {path}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"cannot read authority document {path}: {exc}")
            continue
        if not text.startswith("# "):
            errors.append(f"authority document lacks a top-level Markdown heading: {path}")
    return errors


def project_hashes(root: Path) -> dict[str, str]:
    state = state_dir(root)
    names = [
        "glossary.tsv",
        "term-candidates.tsv",
        STYLE_WATCH_NAME,
        "style-guide.md",
        "voice-cards.md",
        "source-issues.tsv",
        "lessons.md",
    ]
    return {name: sha256_bytes((state / name).read_bytes()) if (state / name).exists() else "missing" for name in names}


def workflow_hashes(root: Path) -> dict[str, str]:
    skill = root / SKILL_REL
    names = [
        "SKILL.md",
        "references/agent-workflow.md",
        "references/review-rubric.md",
        "references/russian-prose-quality.md",
        "references/style-and-translation-standard.md",
        "references/technical-contract.md",
        "scripts/translation_workflow.py",
        "scripts/test_translation_workflow.py",
        "agents/openai.yaml",
    ]
    return {name: sha256_bytes((skill / name).read_bytes()) if (skill / name).exists() else "missing" for name in names}


def static_support_identity(path: Path) -> dict[str, Any]:
    mode = path.lstat().st_mode
    if stat.S_ISREG(mode):
        return {
            "type": "regular",
            "mode": f"{mode & 0o7777:04o}",
            "sha256": sha256_bytes(path.read_bytes()),
        }
    if stat.S_ISLNK(mode):
        return {
            "type": "symlink",
            "mode": f"{mode & 0o7777:04o}",
            "sha256": sha256_text(os.readlink(path)),
        }
    if stat.S_ISDIR(mode):
        return {"type": "directory", "mode": f"{mode & 0o7777:04o}", "sha256": ""}
    return {"type": "non-regular", "mode": f"{mode & 0o7777:04o}", "sha256": ""}


def compute_static_support_hashes(root: Path) -> dict[str, dict[str, Any]]:
    candidates: list[Path] = []
    skill = root / SKILL_REL
    if skill.exists():
        candidates.extend(
            path for path in (
                root / ".agents",
                root / ".agents/skills",
                skill,
                root / ".translation",
                state_dir(root),
            )
            if path.exists() or path.is_symlink()
        )
        candidates.extend(
            path for path in skill.rglob("*")
            if (path.is_file() or path.is_dir() or path.is_symlink())
            and "__pycache__" not in path.parts and path.suffix != ".pyc"
        )
    for relative in (Path(".gitignore"), STATE_REL / "visual-assets.json"):
        path = root / relative
        if path.is_file() or path.is_symlink():
            candidates.append(path)
    legacy = root / LEGACY_REFERENCE_REL
    if legacy.exists() or legacy.is_symlink():
        candidates.extend(
            path for path in (root / LEGACY_REFERENCE_REL.parts[0], legacy)
            if path.exists() or path.is_symlink()
        )
        if legacy.is_dir() and not legacy.is_symlink():
            candidates.extend(
                path for path in legacy.rglob("*")
                if path.is_file() or path.is_dir() or path.is_symlink()
            )
    return {
        path.relative_to(root).as_posix(): static_support_identity(path)
        for path in sorted(set(candidates))
    }


def ensure_static_support_regular(identities: dict[str, dict[str, Any]]) -> None:
    invalid = sorted(
        path for path, identity in identities.items()
        if identity.get("type") not in {"regular", "directory"}
    )
    if invalid:
        raise WorkflowError("workflow support must use regular files: " + ", ".join(invalid[:12]))


def cmd_seal_workflow(args: argparse.Namespace) -> int:
    root = repo_root()
    config, manifest = load_state(root)
    if not config_seal_ok(root):
        raise WorkflowError(
            "config differs from its reviewed seal; seal-workflow may approve support drift only, not config edits"
        )
    config_errors = validate_config_contract(config)
    if config_errors:
        raise WorkflowError("cannot reseal a weakened/invalid config: " + "; ".join(config_errors[:8]))
    ensure_mutation_branch(root)
    branch = current_branch(root)
    if not branch or branch in set(config.get("protected_branches", DEFAULT_PROTECTED_BRANCHES)):
        raise WorkflowError(f"refusing to reseal workflow support on protected/detached branch {branch!r}")
    ensure_source_ancestor(root, config)
    if active_units(manifest):
        raise WorkflowError("workflow support can only be resealed between units")
    metadata_errors = validate_source_metadata(root, config, manifest)
    if metadata_errors:
        raise WorkflowError("cannot seal invalid source/manifest state: " + "; ".join(metadata_errors[:8]))
    if not edition_evidence_ok(root, config):
        raise WorkflowError("cannot seal a config whose edition claim lacks pinned-source evidence")
    reason = args.reason.strip()
    if not reason:
        raise WorkflowError("a review reason is required when resealing workflow support")
    identities = compute_static_support_hashes(root)
    ensure_static_support_regular(identities)
    config["sealed_support_hashes"] = identities
    config.setdefault("workflow_seal_history", []).append(
        {"sealed_at": utc_now(), "reason": reason, "branch": current_branch(root)}
    )
    config_path = state_dir(root) / CONFIG_NAME
    atomic_write_json(config_path, config)
    write_config_seal(root, config_path)
    print(f"Sealed {len(config['sealed_support_hashes'])} workflow-support files")
    return 0


def cmd_context(args: argparse.Namespace) -> int:
    root = repo_root()
    config, manifest = load_state(root)
    metadata_errors = validate_source_metadata(root, config, manifest)
    if metadata_errors:
        raise WorkflowError("source/manifest integrity failure: " + "; ".join(metadata_errors[:8]))
    unit = unit_by_arg(manifest, args.unit, default_next=True)
    text = source_text(root, config["source_commit"], unit["path"])
    glossary = read_tsv(state_dir(root) / "glossary.tsv")
    candidates = read_tsv(state_dir(root) / "term-candidates.tsv")
    style_watch = read_tsv(state_dir(root) / STYLE_WATCH_NAME)
    matches = []
    candidate_matches = []
    lowered = text.casefold()
    for row in glossary:
        source = row.get("source", "").strip()
        if source and source.casefold() in lowered:
            matches.append({"source": source, "approved_ru": row.get("approved_ru", ""), "status": row.get("status", "")})
    for row in candidates:
        source = row.get("source", "").strip()
        if source and source.casefold() in lowered:
            candidate_matches.append(
                {
                    "source": source,
                    "proposed_ru": row.get("proposed_ru", ""),
                    "category": row.get("category", ""),
                    "status": row.get("status", ""),
                }
            )
    related = []
    for match in WIKILINK_RE.finditer(text):
        target, _ = split_wikilink(match.group(2))
        file_part, _ = split_wiki_target(target)
        if file_part and file_part not in related:
            related.append(file_part)
    payload = {
        "unit": {key: unit.get(key) for key in ("id", "path", "kind", "status", "source_words", "source_lines", "source_sha256")},
        "edition": config["edition"],
        "project_hashes": project_hashes(root),
        "workflow_hashes": workflow_hashes(root),
        "glossary_matches": matches,
        "term_candidate_matches": candidate_matches,
        "approved_style_watch": [
            {
                key: row.get(key, "")
                for key in ("id", "literals", "category", "guidance", "applicability", "exceptions")
            }
            for row in style_watch if row.get("status", "").strip() == "approved"
        ],
        "related_wikilink_targets": related,
        "segments": segment_plan(text, config["maximum_segment_words"]) if unit["path"].endswith(".md") else "use segments command for Canvas",
        "required_references": [
            ".agents/skills/translate-cos-reloaded-ru/references/style-and-translation-standard.md",
            ".agents/skills/translate-cos-reloaded-ru/references/technical-contract.md",
            ".agents/skills/translate-cos-reloaded-ru/references/agent-workflow.md",
            ".agents/skills/translate-cos-reloaded-ru/references/review-rubric.md",
            ".agents/skills/translate-cos-reloaded-ru/references/russian-prose-quality.md",
            ".translation/ru/style-guide.md",
            ".translation/ru/glossary.tsv",
            ".translation/ru/term-candidates.tsv",
            ".translation/ru/style-watch.tsv",
            ".translation/ru/voice-cards.md",
            ".translation/ru/source-issues.tsv",
            ".translation/ru/lessons.md",
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def scan_html_tags(text: str) -> list[str]:
    tags: list[str] = []
    index = 0
    while index < len(text):
        start = text.find("<", index)
        if start < 0:
            break
        if text.startswith("<!--", start):
            end_comment = text.find("-->", start + 4)
            index = len(text) if end_comment < 0 else end_comment + 3
            continue
        if start + 1 >= len(text) or text[start + 1] not in "/!ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz":
            index = start + 1
            continue
        quote = ""
        pos = start + 1
        while pos < len(text):
            char = text[pos]
            if quote:
                if char == quote:
                    quote = ""
            elif char in {'"', "'"}:
                quote = char
            elif char == ">":
                tags.append(text[start:pos + 1])
                pos += 1
                break
            elif char == "\n":
                break
            pos += 1
        index = max(pos, start + 1)
    return tags


def markdown_destinations(text: str) -> list[tuple[bool, str]]:
    results: list[tuple[bool, str]] = []
    index = 0
    while index < len(text):
        open_bracket = text.find("[", index)
        if open_bracket < 0:
            break
        if open_bracket + 1 < len(text) and text[open_bracket + 1] == "[":
            index = open_bracket + 2
            continue
        escaped = open_bracket > 0 and text[open_bracket - 1] == "\\"
        if escaped:
            index = open_bracket + 1
            continue
        close = open_bracket + 1
        while close < len(text):
            if text[close] == "]" and text[close - 1] != "\\":
                break
            close += 1
        if close >= len(text) or close + 1 >= len(text) or text[close + 1] != "(":
            index = open_bracket + 1
            continue
        pos = close + 2
        depth = 1
        quote = ""
        while pos < len(text) and depth:
            char = text[pos]
            if quote:
                if char == quote:
                    quote = ""
            elif char in {'"', "'"}:
                quote = char
            elif char == "(" and (pos == 0 or text[pos - 1] != "\\"):
                depth += 1
            elif char == ")" and (pos == 0 or text[pos - 1] != "\\"):
                depth -= 1
                if depth == 0:
                    results.append((open_bracket > 0 and text[open_bracket - 1] == "!", text[close + 2:pos]))
                    pos += 1
                    break
            pos += 1
        index = max(pos, open_bracket + 1)
    return results


def extract_frontmatter(text: str) -> list[tuple[str, str]] | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    result: list[tuple[str, str]] = []
    for line in lines[1:]:
        if line.strip() == "---":
            return result
        match = re.match(r"^([A-Za-z0-9_-]+)(\s*:\s*)(.*)$", line)
        if not match:
            result.append(("__raw__", line))
        else:
            result.append((match.group(1), match.group(2) + match.group(3)))
    return result


def quote_prefix(line: str) -> str:
    match = re.match(r"^(\s*(?:>\s*)*)", line)
    return match.group(1) if match else ""


def list_marker(line: str) -> str:
    rest = line[len(quote_prefix(line)):]
    match = re.match(r"^(\s*)([-+*]|\d+[.)])(\s+)", rest)
    return "" if not match else match.group(1) + match.group(2) + match.group(3)


def emphasis_signature(line: str) -> list[str]:
    rest = line[len(quote_prefix(line)):]
    marker = list_marker(line)
    if marker:
        rest = rest[len(marker):]
    rest = mask_spans(rest, code_spans(rest))
    return EMPHASIS_RE.findall(rest)


def table_pipe_count(line: str) -> int | None:
    rest = line[len(quote_prefix(line)):].lstrip()
    if not rest.startswith("|"):
        return None
    return len(re.findall(r"(?<!\\)\|", rest))


def compare_sequences(name: str, source: Sequence[Any], target: Sequence[Any], errors: list[str]) -> None:
    if list(source) != list(target):
        first = next((i for i, pair in enumerate(zip(source, target)) if pair[0] != pair[1]), min(len(source), len(target)))
        errors.append(f"{name} changed (source={len(source)}, target={len(target)}, first difference index={first})")


def visible_text(text: str) -> str:
    text = mask_spans(text, protected_spans(text))
    text = MACRO_RE.sub(" ", text)
    text = ROLL_RE.sub(" ", text)
    text = TEMPLATE_RE.sub(" ", text)
    text = DICE_RE.sub(" ", text)
    text = re.sub(r"<[^>\n]+>", " ", text)
    text = WIKILINK_RE.sub(_visible_wikilink, text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = ENTITY_RE.sub(" ", text)
    text = FOOTNOTE_REF_RE.sub(" ", text)
    text = re.sub(r"(?m)^\[\^[^\]]+\]:\s*", "", text)
    text = BLOCK_ID_RE.sub(" ", text)
    text = re.sub(r"^\s*(?:>\s*)+\[![^\]]+\][+-]?", " ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*(?:>\s*)+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_~`]", "", text)
    return text


def _visible_wikilink(match: re.Match[str]) -> str:
    if match.group(1) == "!":
        return " "
    target, alias = split_wikilink(match.group(2))
    if alias:
        return alias
    file_part, sections = split_wiki_target(target)
    if sections:
        return sections[-1]
    return Path(file_part).name if file_part else ""


def line_structure_errors(source: str, target: str) -> list[str]:
    errors: list[str] = []
    source_lines = source.splitlines()
    target_lines = target.splitlines()
    if len(source_lines) != len(target_lines):
        errors.append(f"line count changed ({len(source_lines)} -> {len(target_lines)})")
    for number, (src, dst) in enumerate(zip(source_lines, target_lines), start=1):
        if (not src.strip()) != (not dst.strip()):
            errors.append(f"line {number}: blank/nonblank structure changed")
        if quote_prefix(src) != quote_prefix(dst):
            errors.append(f"line {number}: blockquote prefix changed")
        src_heading = re.match(r"^(#{1,6})(\s+)", src)
        dst_heading = re.match(r"^(#{1,6})(\s+)", dst)
        if (src_heading.group(1, 2) if src_heading else None) != (dst_heading.group(1, 2) if dst_heading else None):
            errors.append(f"line {number}: heading marker changed")
        if list_marker(src) != list_marker(dst):
            errors.append(f"line {number}: list marker or indentation changed")
        if table_pipe_count(src) != table_pipe_count(dst):
            errors.append(f"line {number}: Markdown table pipe shape changed")
        src_trailing = re.search(r"[ \t]+$", src)
        dst_trailing = re.search(r"[ \t]+$", dst)
        if (src_trailing.group(0) if src_trailing else "") != (dst_trailing.group(0) if dst_trailing else ""):
            errors.append(f"line {number}: trailing whitespace changed")
        if emphasis_signature(src) != emphasis_signature(dst):
            errors.append(f"line {number}: emphasis delimiter sequence changed")
        if len(errors) >= 80:
            errors.append("additional line-structure errors suppressed")
            break
    return errors


def wiki_file_index(paths: Iterable[str]) -> dict[str, str | None]:
    index: dict[str, str | None] = {}
    for path in paths:
        if not path.endswith((".md", ".canvas")):
            continue
        stem = str(Path(path).with_suffix(""))
        keys = {stem, Path(stem).name, path, Path(path).name}
        for key in keys:
            if key in index and index[key] != path:
                index[key] = None
            else:
                index[key] = path
    return index


def resolve_wiki_file(file_part: str, current_path: str, index: dict[str, str | None]) -> str | None:
    if not file_part:
        return current_path
    clean = file_part.strip().lstrip("/")
    candidates = [clean]
    if clean.endswith(".md") or clean.endswith(".canvas"):
        candidates.append(str(Path(clean).with_suffix("")))
    relative = str((Path(current_path).parent / clean).as_posix())
    candidates.extend([relative, str(Path(relative).with_suffix("")), Path(clean).name, Path(clean).stem])
    for candidate in candidates:
        if candidate in index and index[candidate] is not None:
            return index[candidate]
    return None


def build_heading_maps(root: Path, config: dict[str, Any], manifest: dict[str, Any]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for unit in manifest["units"]:
        path = unit["path"]
        if not path.endswith(".md") or not (root / path).exists():
            continue
        source = source_text(root, config["source_commit"], path)
        target = (root / path).read_text(encoding="utf-8")
        src_rows = heading_rows(source)
        dst_rows = heading_rows(target)
        try:
            result[path] = validated_heading_mapping(src_rows, dst_rows)
        except WorkflowError:
            continue
    return result


def normalize_apostrophes(value: str) -> str:
    return value.replace("’", "'").casefold()


def mapped_heading(component: str, mapping: dict[str, str]) -> str | None:
    if component in mapping:
        return mapping[component]
    normalized = normalize_apostrophes(plain_heading(component))
    for source, target in mapping.items():
        if normalize_apostrophes(source) == normalized:
            return target
    if any(normalize_apostrophes(target) == normalized for target in mapping.values()):
        return component
    return None


def link_issue_set(
    texts: dict[str, str],
    paths: list[str],
    *,
    source_mode: bool = False,
) -> set[str]:
    # Index only files that are actually present in the source/worktree text set.
    # Manifest membership alone must not make a missing target appear resolvable.
    index = wiki_file_index(texts.keys())
    heading_sets = {path: {row["plain"] for row in heading_rows(text)} for path, text in texts.items() if path.endswith(".md")}
    block_sets = {path: set(BLOCK_ID_RE.findall(text)) for path, text in texts.items() if path.endswith(".md")}
    issues: set[str] = set()
    for path, text in texts.items():
        for location, fragment in link_fragments(path, text):
            for match in unprotected_wikilinks(fragment):
                inner = match.group(2)
                target, _ = split_wikilink(inner)
                file_part, components = split_wiki_target(target)
                extension = Path(file_part).suffix.lower()
                if match.group(1) == "!" or extension in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}:
                    continue
                resolved = resolve_wiki_file(file_part, path, index)
                marker = (
                    str(fragment.count("\n", 0, match.start()) + 1)
                    if location == "$markdown"
                    else location
                )
                if resolved is None:
                    issues.add(f"{path}:{marker}:unresolved-file:{file_part}")
                    continue
                for component in components:
                    if not component:
                        continue
                    if component.startswith("^"):
                        if component[1:] not in block_sets.get(resolved, set()):
                            issues.add(f"{path}:{marker}:unresolved-block:{resolved}#{component}")
                    elif plain_heading(component) not in heading_sets.get(resolved, set()):
                        issues.add(f"{path}:{marker}:unresolved-heading:{resolved}#{component}")
    return issues


def link_fragments(path: str, text: str) -> Iterator[tuple[str, str]]:
    if path.endswith(".md"):
        yield "$markdown", text
        return
    if not path.endswith(".canvas"):
        return
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return
    for json_path, value in iter_canvas_text(payload):
        if canvas_translatable(json_path):
            yield format_json_path(json_path), value


def compare_wikilinks(
    source: str,
    target: str,
    current_path: str,
    paths: list[str],
    heading_maps: dict[str, dict[str, str]],
    errors: list[str],
) -> None:
    src_links = [(m.group(1), m.group(2)) for m in unprotected_wikilinks(source)]
    dst_links = [(m.group(1), m.group(2)) for m in unprotected_wikilinks(target)]
    if len(src_links) != len(dst_links):
        errors.append(f"wikilink count changed ({len(src_links)} -> {len(dst_links)})")
        return
    index = wiki_file_index(paths)
    for number, ((src_embed, src_inner), (dst_embed, dst_inner)) in enumerate(zip(src_links, dst_links), start=1):
        if src_embed != dst_embed:
            errors.append(f"wikilink {number}: embed marker changed")
            continue
        src_target, _ = split_wikilink(src_inner)
        dst_target, _ = split_wikilink(dst_inner)
        src_file, src_components = split_wiki_target(src_target)
        dst_file, dst_components = split_wiki_target(dst_target)
        if src_file != dst_file:
            errors.append(f"wikilink {number}: file target changed: {src_file!r} -> {dst_file!r}")
            continue
        if len(src_components) != len(dst_components):
            errors.append(f"wikilink {number}: heading component count changed")
            continue
        resolved = resolve_wiki_file(src_file, current_path, index)
        mapping = heading_maps.get(resolved or "", {})
        for src_component, dst_component in zip(src_components, dst_components):
            if src_component.startswith("^"):
                if src_component != dst_component:
                    errors.append(f"wikilink {number}: block id changed")
            else:
                expected = mapped_heading(src_component, mapping) if mapping else src_component
                if expected is None or plain_heading(dst_component) != plain_heading(expected):
                    errors.append(
                        f"wikilink {number}: heading target is not mapped: {src_component!r} -> {dst_component!r}"
                    )


def compare_frontmatter(source: str, target: str, allow_keys: set[str], errors: list[str]) -> None:
    src = extract_frontmatter(source)
    dst = extract_frontmatter(target)
    if (src is None) != (dst is None):
        errors.append("YAML frontmatter presence changed")
        return
    if src is None or dst is None:
        return
    if len(src) != len(dst):
        errors.append("YAML frontmatter line count changed")
        return
    for index, ((src_key, src_value), (dst_key, dst_value)) in enumerate(zip(src, dst), start=2):
        if src_key != dst_key:
            errors.append(f"YAML line {index}: key/order changed")
        elif src_key not in allow_keys and src_value != dst_value:
            errors.append(f"YAML line {index}: protected value changed for {src_key}")
        elif src_key in allow_keys:
            if yaml_value_style(src_value) != yaml_value_style(dst_value):
                errors.append(f"YAML line {index}: separator or value quoting style changed for {src_key}")


def yaml_value_style(raw: str) -> tuple[str, str, str]:
    match = re.match(r"^(\s*:\s*)(.*)$", raw)
    if not match:
        return ("", "", "")
    value = match.group(2).strip()
    quote = value[0] if value[:1] in {'"', "'"} and value[-1:] == value[:1] else ""
    container = ""
    if not quote and value[:1] in {"[", "{", "|", ">"}:
        container = value[:1]
    return match.group(1), quote, container


def glossary_issues(root: Path, source_text_value: str, target_text_value: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    source_lines = visible_text(source_text_value).splitlines()
    target_lines = visible_text(target_text_value).splitlines()
    target_visible = "\n".join(target_lines)
    for row in read_tsv(state_dir(root) / "glossary.tsv"):
        if row.get("status", "").strip() != "approved":
            continue
        source = row.get("source", "").strip()
        enforce = row.get("enforce", "").strip().lower() in {"1", "true", "yes"}
        if source and enforce:
            capitalization = row.get("capitalization", "").casefold()
            source_flags = 0 if "capitalized" in capitalization else re.IGNORECASE
            source_pattern = re.compile(
                rf"(?<![A-Za-z]){re.escape(source)}(?![A-Za-z])",
                source_flags,
            )
            if source_pattern.search(target_visible):
                errors.append(f"approved glossary source term remains visible: {source!r}")
            approved = [row.get("approved_ru", "").strip()]
            approved.extend(item.strip() for item in row.get("forms", "").split(";") if item.strip())
            approved = [item for item in approved if item]
            if approved:
                allowed_pattern = re.compile(
                    r"(?<!\w)(?:" + "|".join(re.escape(item) for item in sorted(approved, key=len, reverse=True)) + r")(?!\w)",
                    re.IGNORECASE,
                )
                for line_number, (src_line, dst_line) in enumerate(zip(source_lines, target_lines), start=1):
                    if source_pattern.search(src_line) and not allowed_pattern.search(dst_line):
                        errors.append(
                            f"line {line_number}: approved Russian form missing for glossary term {source!r}"
                        )
        forbidden = [item.strip() for item in row.get("forbidden_variants", "").split(";") if item.strip()]
        for variant in forbidden:
            if re.search(rf"(?<!\w){re.escape(variant)}(?!\w)", target_visible, re.IGNORECASE):
                errors.append(f"forbidden glossary variant remains visible: {variant!r}")
    return errors, warnings


def literal_watch_pattern(literal: str) -> re.Pattern[str]:
    left = r"(?<!\w)" if literal[:1].isalnum() or literal[:1] == "_" else ""
    right = r"(?!\w)" if literal[-1:].isalnum() or literal[-1:] == "_" else ""
    return re.compile(left + re.escape(literal) + right, re.IGNORECASE)


def style_watch_findings(root: Path, fragments: Sequence[tuple[str, str]]) -> list[dict[str, Any]]:
    rules = [
        row for row in read_tsv(state_dir(root) / STYLE_WATCH_NAME)
        if row.get("status", "").strip() == "approved"
    ]
    findings: list[dict[str, Any]] = []
    seen_occurrences: set[tuple[str, str, int, int]] = set()
    for location_prefix, text in fragments:
        for line_number, line in enumerate(visible_text(text).splitlines(), start=1):
            if not line.strip():
                continue
            location = f"{location_prefix}:line {line_number}" if location_prefix else f"line {line_number}"
            for row in rules:
                rule_id = row.get("id", "").strip()
                for literal in (item.strip() for item in row.get("literals", "").split(";")):
                    if not literal:
                        continue
                    for match in literal_watch_pattern(literal).finditer(line):
                        occurrence = (rule_id, location, match.start(), match.end())
                        if occurrence in seen_occurrences:
                            continue
                        seen_occurrences.add(occurrence)
                        key_payload = json.dumps(
                            [rule_id, location, match.start(), match.end(), match.group(0), line],
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        findings.append(
                            {
                                "key": f"{rule_id}:{sha256_text(key_payload)[:20]}",
                                "rule_id": rule_id,
                                "location": location,
                                "literal": match.group(0),
                                "category": row.get("category", "").strip(),
                                "guidance": row.get("guidance", "").strip(),
                                "applicability": row.get("applicability", "").strip(),
                                "exceptions": row.get("exceptions", "").strip(),
                                "excerpt": line.strip()[:240],
                            }
                        )
    return findings


def style_fragments_for_target(path: str, text: str) -> list[tuple[str, str]]:
    if not path.endswith(".canvas"):
        return [("", text)]
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return [(path, text)]
    return [
        (format_json_path(json_path), value)
        for json_path, value in iter_canvas_text(payload)
        if canvas_translatable(json_path)
    ]


def style_flags_fingerprint(flags: Sequence[dict[str, Any]]) -> str:
    return sha256_text(json.dumps(list(flags), ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def validate_style_flags_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    flags = report.get("style_flags")
    if not isinstance(flags, list):
        raise WorkflowError("QA report lacks structured Russian style-watch flags")
    required = {
        "key", "rule_id", "location", "literal", "category", "guidance",
        "applicability", "exceptions", "excerpt",
    }
    keys: list[str] = []
    for index, flag in enumerate(flags, start=1):
        if not isinstance(flag, dict) or set(flag) != required:
            raise WorkflowError(f"QA style-watch flag {index} has a malformed schema")
        if any(not str(flag.get(name, "")).strip() for name in required):
            raise WorkflowError(f"QA style-watch flag {index} has empty evidence")
        keys.append(str(flag["key"]))
    if len(keys) != len(set(keys)):
        raise WorkflowError("QA style-watch flags contain duplicate occurrence keys")
    if report.get("style_flags_sha256") != style_flags_fingerprint(flags):
        raise WorkflowError("QA style-watch flag fingerprint is missing or stale")
    return flags


def load_style_dispositions(path_value: str | None, report: dict[str, Any], unit: dict[str, Any]) -> list[dict[str, str]]:
    flags = validate_style_flags_report(report)
    expected_keys = {str(flag["key"]) for flag in flags}
    if not path_value:
        if expected_keys:
            raise WorkflowError(
                "a Russian-style review must disposition every current style-watch flag "
                "with --style-dispositions-file"
            )
        return []
    payload = load_json(Path(path_value))
    if (
        payload.get("schema_version") != 1
        or payload.get("unit_id") != unit["id"]
        or payload.get("target_sha256") != report.get("target_sha256")
        or payload.get("style_flags_sha256") != report.get("style_flags_sha256")
    ):
        raise WorkflowError("style-watch dispositions belong to a stale or different QA/unit identity")
    values = payload.get("dispositions")
    if not isinstance(values, list):
        raise WorkflowError("style-watch dispositions must be a JSON list")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, value in enumerate(values, start=1):
        if not isinstance(value, dict) or set(value) != {"key", "decision", "reason"}:
            raise WorkflowError(f"style-watch disposition {index} has a malformed schema")
        key = str(value.get("key", "")).strip()
        decision = str(value.get("decision", "")).strip()
        reason = str(value.get("reason", "")).strip()
        if not key or key in seen:
            raise WorkflowError(f"style-watch disposition {index} has an empty or duplicate key")
        if decision not in STYLE_DISPOSITION_DECISIONS or not reason:
            raise WorkflowError(f"style-watch disposition {index} has an invalid decision or blank reason")
        seen.add(key)
        normalized.append({"key": key, "decision": decision, "reason": reason})
    if seen != expected_keys:
        missing = sorted(expected_keys - seen)
        extra = sorted(seen - expected_keys)
        raise WorkflowError(
            "style-watch disposition coverage does not match current QA "
            f"(missing={missing[:8]}, extra={extra[:8]})"
        )
    return sorted(normalized, key=lambda item: item["key"])


def validate_style_review_record(
    review: dict[str, Any], report: dict[str, Any] | None = None
) -> None:
    if review.get("role") != "russian-style":
        return
    if review.get("verdict") != "pass":
        return
    keys = review.get("reviewed_style_flag_keys")
    dispositions = review.get("style_dispositions")
    fingerprint = review.get("style_flags_sha256")
    if not isinstance(keys, list) or not isinstance(dispositions, list) or not str(fingerprint or "").strip():
        raise WorkflowError("Russian-style review lacks style-watch disposition evidence")
    if keys != sorted(set(keys)):
        raise WorkflowError("Russian-style review has duplicate or noncanonical style-watch keys")
    seen: set[str] = set()
    for index, value in enumerate(dispositions, start=1):
        if not isinstance(value, dict) or set(value) != {"key", "decision", "reason"}:
            raise WorkflowError(f"Russian-style disposition {index} has a malformed schema")
        key = str(value.get("key", "")).strip()
        decision = str(value.get("decision", "")).strip()
        reason = str(value.get("reason", "")).strip()
        if not key or key in seen or decision not in STYLE_DISPOSITION_DECISIONS or not reason:
            raise WorkflowError(f"Russian-style disposition {index} is duplicate, invalid, or unexplained")
        seen.add(key)
    if seen != set(keys):
        raise WorkflowError("Russian-style review dispositions do not cover their recorded style-watch keys")
    if report is not None:
        flags = validate_style_flags_report(report)
        expected_keys = sorted(str(flag["key"]) for flag in flags)
        if fingerprint != report.get("style_flags_sha256") or keys != expected_keys:
            raise WorkflowError("Russian-style review style-watch dispositions are stale for the current QA flags")


def validate_link_style_transition(
    transition: Any,
    semantic_fingerprint: str,
    report: dict[str, Any],
    unit: dict[str, Any],
    link_reviewer: str,
    trigger_translator: str | None,
) -> None:
    required = {
        "semantic_style_flags_sha256", "current_style_flags_sha256", "changed", "review",
    }
    if not isinstance(transition, dict) or set(transition) != required:
        raise WorkflowError("link-consistency evidence lacks a canonical style-watch transition")
    current_fingerprint = report.get("style_flags_sha256")
    if (
        transition.get("semantic_style_flags_sha256") != semantic_fingerprint
        or transition.get("current_style_flags_sha256") != current_fingerprint
        or not isinstance(transition.get("changed"), bool)
    ):
        raise WorkflowError("link-consistency style-watch transition is stale")
    changed = current_fingerprint != semantic_fingerprint
    if transition["changed"] != changed:
        raise WorkflowError("link-consistency style-watch change marker is invalid")
    delta = transition.get("review")
    if not changed:
        if delta is not None:
            raise WorkflowError("unchanged link style-watch evidence has an unexpected delta review")
        return
    delta_required = {
        "schema_version", "role", "reviewer", "reviewed_at", "notes", "target_sha256",
        "style_flags_sha256", "reviewed_style_flag_keys", "style_dispositions",
    }
    if not isinstance(delta, dict) or set(delta) != delta_required:
        raise WorkflowError("changed link style-watch evidence lacks a canonical Russian-style delta review")
    reviewer = str(delta.get("reviewer", "")).strip()
    if (
        delta.get("schema_version") != 1
        or delta.get("role") != "russian-style-link-delta"
        or not reviewer
        or reviewer == link_reviewer
        or reviewer in {unit.get("translator"), trigger_translator}
        or not str(delta.get("reviewed_at", "")).strip()
        or not str(delta.get("notes", "")).strip()
        or delta.get("target_sha256") != report.get("target_sha256")
    ):
        raise WorkflowError("Russian-style link-delta review identity is invalid or not independent")
    validate_style_review_record(
        {
            "role": "russian-style",
            "verdict": "pass",
            "style_flags_sha256": delta.get("style_flags_sha256"),
            "reviewed_style_flag_keys": delta.get("reviewed_style_flag_keys"),
            "style_dispositions": delta.get("style_dispositions"),
        },
        report,
    )


def language_issues(source: str, target: str, minimum_ratio: float) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    visible = visible_text(target)
    cyrillic = len(CYRILLIC_RE.findall(visible))
    latin = len(LATIN_RE.findall(visible))
    ratio = cyrillic / max(1, cyrillic + latin)
    if cyrillic == 0:
        errors.append("target contains no Cyrillic visible text")
    elif ratio < minimum_ratio:
        errors.append(f"Cyrillic letter ratio is too low ({ratio:.1%} < {minimum_ratio:.1%})")
    src_lines = source.splitlines()
    dst_lines = target.splitlines()
    src_visible_lines = visible_text(source).splitlines()
    dst_visible_lines = visible_text(target).splitlines()
    for number, (src, dst, src_visible_raw, dst_visible_raw) in enumerate(
        zip(src_lines, dst_lines, src_visible_lines, dst_visible_lines), start=1
    ):
        src_visible = src_visible_raw.strip()
        dst_visible = dst_visible_raw.strip()
        src_words = ENGLISH_WORD_RE.findall(src_visible)
        unchanged = bool(src_words) and src_visible == dst_visible
        is_heading = bool(re.match(r"^\s*#{1,6}\s+", src))
        is_html_heading = bool(re.search(r"<h[1-6](?:\s[^>]*)?>", src, re.IGNORECASE))
        is_callout_header = bool(CALLOUT_RE.match(src))
        structural_rest = src[len(quote_prefix(src)):]
        is_table_row = structural_rest.lstrip().startswith("|")
        is_list_item = bool(list_marker(src))
        if unchanged and (
            is_heading or is_html_heading or is_callout_header or is_table_row or is_list_item or len(src_words) >= 5
        ):
            errors.append(f"line {number}: eligible source text appears unchanged")
        elif unchanged and len(src_words) >= 2:
            warnings.append(f"line {number}: short visible source phrase appears unchanged")
        if len(src_words) >= 5 and not dst_visible:
            errors.append(f"line {number}: visible source text became empty")
        dst_words = [word.casefold() for word in ENGLISH_WORD_RE.findall(dst_visible)]
        stop_count = sum(word in ENGLISH_STOPWORDS for word in dst_words)
        dst_cyr = len(CYRILLIC_RE.findall(dst_visible))
        if stop_count >= 8 and dst_cyr < 3:
            errors.append(f"line {number}: likely untranslated English prose ({stop_count} function words)")
        elif stop_count >= 5 and dst_cyr < 3:
            warnings.append(f"line {number}: possible untranslated English run ({stop_count} function words)")
        if len(errors) >= 120:
            errors.append("additional language errors suppressed")
            break
    return errors, warnings, {"cyrillic_letters": cyrillic, "latin_letters": latin, "cyrillic_ratio": ratio}


def compare_markdown(
    source: str,
    target: str,
    *,
    current_path: str = "unit.md",
    content_paths: list[str] | None = None,
    heading_maps: dict[str, dict[str, str]] | None = None,
    yaml_allow_keys: set[str] | None = None,
    minimum_cyrillic_ratio: float = 0.35,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if "\ufffd" in target:
        errors.append("target contains Unicode replacement characters")
    if target.startswith("```") or "```markdown" in target.casefold():
        errors.append("target appears to contain model-added Markdown fences")
    compare_sequences("raw HTML tags", scan_html_tags(source), scan_html_tags(target), errors)
    compare_sequences("HTML comments", html_comment_tokens(source), html_comment_tokens(target), errors)
    compare_sequences("Markdown code spans/blocks", code_tokens(source), code_tokens(target), errors)
    compare_sequences("bare URLs", bare_urls(source), bare_urls(target), errors)
    compare_sequences("HTML entities", ENTITY_RE.findall(source), ENTITY_RE.findall(target), errors)
    compare_sequences("Markdown link/image destinations", markdown_destinations(source), markdown_destinations(target), errors)
    compare_sequences(
        "Obsidian image embeds",
        [m.group(0) for m in unprotected_wikilinks(source) if m.group(1)],
        [m.group(0) for m in unprotected_wikilinks(target) if m.group(1)],
        errors,
    )
    compare_sequences("footnote refs", FOOTNOTE_REF_RE.findall(source), FOOTNOTE_REF_RE.findall(target), errors)
    compare_sequences("footnote defs", FOOTNOTE_DEF_RE.findall(source), FOOTNOTE_DEF_RE.findall(target), errors)
    compare_sequences("block ids", BLOCK_ID_RE.findall(source), BLOCK_ID_RE.findall(target), errors)
    compare_sequences("dice formulas", DICE_RE.findall(source), DICE_RE.findall(target), errors)
    compare_sequences("numeric tokens", NUMBER_RE.findall(source), NUMBER_RE.findall(target), errors)
    compare_sequences("signed modifiers", SIGNED_NUMBER_RE.findall(source), SIGNED_NUMBER_RE.findall(target), errors)
    compare_sequences("numeric ranges", RANGE_RE.findall(source), RANGE_RE.findall(target), errors)
    compare_sequences("percentages", PERCENT_RE.findall(source), PERCENT_RE.findall(target), errors)
    compare_sequences("macros", MACRO_RE.findall(source), MACRO_RE.findall(target), errors)
    compare_sequences("inline rolls", ROLL_RE.findall(source), ROLL_RE.findall(target), errors)
    compare_sequences("template tokens", TEMPLATE_RE.findall(source), TEMPLATE_RE.findall(target), errors)
    compare_sequences("action glyphs", re.findall(r"▶|▷|↻|\[reaction\]", source), re.findall(r"▶|▷|↻|\[reaction\]", target), errors)

    src_headings = heading_rows(source)
    dst_headings = heading_rows(target)
    compare_sequences(
        "heading level/code sequence",
        [(h["level"], h["code"]) for h in src_headings],
        [(h["level"], h["code"]) for h in dst_headings],
        errors,
    )
    try:
        validated_heading_mapping(src_headings, dst_headings)
    except WorkflowError as exc:
        errors.append(str(exc))
    compare_sequences(
        "callout type/fold sequence",
        [(m.group(1), m.group(2), m.group(3)) for m in CALLOUT_RE.finditer(source)],
        [(m.group(1), m.group(2), m.group(3)) for m in CALLOUT_RE.finditer(target)],
        errors,
    )
    errors.extend(line_structure_errors(source, target))
    compare_frontmatter(source, target, yaml_allow_keys or set(), errors)
    paths = content_paths or [current_path]
    compare_wikilinks(source, target, current_path, paths, heading_maps or {current_path: {}}, errors)
    language_errors, language_warnings, metrics = language_issues(source, target, minimum_cyrillic_ratio)
    errors.extend(language_errors)
    warnings.extend(language_warnings)
    return {
        "pass": not errors,
        "errors": errors,
        "warnings": warnings,
        "metrics": metrics,
    }


def canvas_translatable(path: tuple[Any, ...]) -> bool:
    return (
        len(path) == 3
        and path[0] in {"nodes", "edges"}
        and isinstance(path[1], int)
        and ((path[0] == "nodes" and path[2] == "text") or (path[0] == "edges" and path[2] == "label"))
    )


def compare_canvas(
    source: str,
    target: str,
    minimum_cyrillic_ratio: float = 0.35,
    *,
    current_path: str = "unit.canvas",
    content_paths: list[str] | None = None,
    heading_maps: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        src_payload = json.loads(source)
    except json.JSONDecodeError as exc:
        return {"pass": False, "errors": [f"source Canvas JSON is invalid: {exc}"], "warnings": [], "metrics": {}}
    try:
        dst_payload = json.loads(target)
    except json.JSONDecodeError as exc:
        return {"pass": False, "errors": [f"target Canvas JSON is invalid: {exc}"], "warnings": [], "metrics": {}}
    try:
        source_skeleton = canvas_raw_skeleton(source)
        target_skeleton = canvas_raw_skeleton(target)
    except WorkflowError as exc:
        errors.append(str(exc))
    else:
        if source_skeleton != target_skeleton:
            errors.append("Canvas raw JSON bytes changed outside allowlisted text/label strings")
    translated_fragments: list[str] = []

    def walk(src: Any, dst: Any, path: tuple[Any, ...]) -> None:
        if type(src) is not type(dst):
            errors.append(f"Canvas type changed at {format_json_path(path)}")
            return
        if isinstance(src, dict):
            if list(src.keys()) != list(dst.keys()):
                errors.append(f"Canvas object keys/order changed at {format_json_path(path)}")
                return
            for key in src:
                walk(src[key], dst[key], path + (key,))
        elif isinstance(src, list):
            if len(src) != len(dst):
                errors.append(f"Canvas array length changed at {format_json_path(path)}")
                return
            for index, (src_item, dst_item) in enumerate(zip(src, dst)):
                walk(src_item, dst_item, path + (index,))
        elif canvas_translatable(path):
            if not isinstance(src, str):
                errors.append(f"Canvas allowlisted field is not text at {format_json_path(path)}")
            else:
                compare_canvas_text(
                    src,
                    dst,
                    format_json_path(path),
                    errors,
                    current_path=current_path,
                    content_paths=content_paths or [current_path],
                    heading_maps=heading_maps or {},
                )
                translated_fragments.append(dst)
        elif src != dst:
            errors.append(f"protected Canvas value changed at {format_json_path(path)}")

    walk(src_payload, dst_payload, ())
    source_visible = "\n".join(
        value for path, value in iter_canvas_text(src_payload) if canvas_translatable(path)
    )
    target_visible = "\n".join(translated_fragments)
    lang_errors, lang_warnings, metrics = language_issues(source_visible, target_visible, minimum_cyrillic_ratio)
    errors.extend(lang_errors)
    warnings.extend(lang_warnings)
    return {"pass": not errors, "errors": errors, "warnings": warnings, "metrics": metrics}


def canvas_raw_skeleton(text: str) -> str:
    pieces: list[str] = []
    cursor = 0
    for number, (start, end, _) in enumerate(canvas_translatable_string_spans(text), start=1):
        pieces.append(text[cursor:start])
        pieces.append(f"\x00CANVAS_TRANSLATABLE_{number}\x00")
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def compare_canvas_text(
    source: str,
    target: str,
    label: str,
    errors: list[str],
    *,
    current_path: str = "unit.canvas",
    content_paths: list[str] | None = None,
    heading_maps: dict[str, dict[str, str]] | None = None,
) -> None:
    prefix = f"Canvas {label}"
    compare_sequences(f"{prefix} raw HTML tags", scan_html_tags(source), scan_html_tags(target), errors)
    compare_sequences(f"{prefix} HTML comments", html_comment_tokens(source), html_comment_tokens(target), errors)
    compare_sequences(f"{prefix} Markdown code spans/blocks", code_tokens(source), code_tokens(target), errors)
    compare_sequences(f"{prefix} bare URLs", bare_urls(source), bare_urls(target), errors)
    compare_sequences(f"{prefix} HTML entities", ENTITY_RE.findall(source), ENTITY_RE.findall(target), errors)
    compare_sequences(f"{prefix} Markdown destinations", markdown_destinations(source), markdown_destinations(target), errors)
    compare_sequences(
        f"{prefix} Obsidian image embeds",
        [m.group(0) for m in unprotected_wikilinks(source) if m.group(1)],
        [m.group(0) for m in unprotected_wikilinks(target) if m.group(1)],
        errors,
    )
    compare_wikilinks(
        source,
        target,
        current_path,
        content_paths or [current_path],
        heading_maps or {},
        errors,
    )
    compare_sequences(f"{prefix} footnote refs", FOOTNOTE_REF_RE.findall(source), FOOTNOTE_REF_RE.findall(target), errors)
    compare_sequences(f"{prefix} footnote defs", FOOTNOTE_DEF_RE.findall(source), FOOTNOTE_DEF_RE.findall(target), errors)
    compare_sequences(f"{prefix} block ids", BLOCK_ID_RE.findall(source), BLOCK_ID_RE.findall(target), errors)
    compare_sequences(f"{prefix} dice formulas", DICE_RE.findall(source), DICE_RE.findall(target), errors)
    compare_sequences(f"{prefix} numeric tokens", NUMBER_RE.findall(source), NUMBER_RE.findall(target), errors)
    compare_sequences(f"{prefix} signed modifiers", SIGNED_NUMBER_RE.findall(source), SIGNED_NUMBER_RE.findall(target), errors)
    compare_sequences(f"{prefix} numeric ranges", RANGE_RE.findall(source), RANGE_RE.findall(target), errors)
    compare_sequences(f"{prefix} percentages", PERCENT_RE.findall(source), PERCENT_RE.findall(target), errors)
    compare_sequences(f"{prefix} macros", MACRO_RE.findall(source), MACRO_RE.findall(target), errors)
    compare_sequences(f"{prefix} inline rolls", ROLL_RE.findall(source), ROLL_RE.findall(target), errors)
    compare_sequences(f"{prefix} template tokens", TEMPLATE_RE.findall(source), TEMPLATE_RE.findall(target), errors)
    compare_sequences(
        f"{prefix} action glyphs",
        re.findall(r"▶|▷|↻|\[reaction\]", source),
        re.findall(r"▶|▷|↻|\[reaction\]", target),
        errors,
    )
    for issue in line_structure_errors(source, target):
        errors.append(f"{prefix}: {issue}")


def iter_canvas_text(value: Any, path: tuple[Any, ...] = ()) -> Iterator[tuple[tuple[Any, ...], str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from iter_canvas_text(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_canvas_text(child, path + (index,))
    elif isinstance(value, str):
        yield path, value


def format_json_path(path: tuple[Any, ...]) -> str:
    if not path:
        return "$"
    result = "$"
    for part in path:
        result += f"[{part}]" if isinstance(part, int) else f".{part}"
    return result


def all_content_texts(root: Path, config: dict[str, Any], manifest: dict[str, Any], *, source: bool) -> dict[str, str]:
    texts: dict[str, str] = {}
    for unit in manifest["units"]:
        path = unit["path"]
        if not path.endswith((".md", ".canvas")):
            continue
        if source:
            texts[path] = source_text(root, config["source_commit"], path)
        elif (root / path).exists():
            texts[path] = (root / path).read_text(encoding="utf-8")
    return texts


def qa_unit(root: Path, config: dict[str, Any], manifest: dict[str, Any], unit: dict[str, Any]) -> dict[str, Any]:
    path = unit["path"]
    source_data = source_bytes(root, config["source_commit"], path)
    integrity_errors = validate_source_metadata(root, config, manifest)
    target_path = root / path
    if not target_path.exists():
        return {
            "schema_version": 1,
            "unit_id": unit["id"],
            "path": path,
            "checked_at": utc_now(),
            "pass": False,
            "errors": ["target file is missing"],
            "warnings": [],
        }
    target_data = target_path.read_bytes()
    try:
        source_value = source_data.decode("utf-8")
        target_value = target_data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return {
            "schema_version": 1,
            "unit_id": unit["id"],
            "path": path,
            "checked_at": utc_now(),
            "pass": False,
            "errors": [f"UTF-8 decode failure: {exc}"],
            "warnings": [],
        }
    paths = [item["path"] for item in manifest["units"]]
    heading_maps = build_heading_maps(root, config, manifest)
    if path.endswith(".canvas"):
        result = compare_canvas(
            source_value,
            target_value,
            config["minimum_cyrillic_letter_ratio"],
            current_path=path,
            content_paths=paths,
            heading_maps=heading_maps,
        )
        try:
            source_payload = json.loads(source_value)
            target_payload = json.loads(target_value)
            source_glossary_text = "\n".join(
                value for json_path, value in iter_canvas_text(source_payload) if canvas_translatable(json_path)
            )
            target_glossary_text = "\n".join(
                value for json_path, value in iter_canvas_text(target_payload) if canvas_translatable(json_path)
            )
            style_fragments = [
                (format_json_path(json_path), value)
                for json_path, value in iter_canvas_text(target_payload)
                if canvas_translatable(json_path)
            ]
        except json.JSONDecodeError:
            source_glossary_text = source_value
            target_glossary_text = target_value
            style_fragments = [(path, target_value)]
    else:
        result = compare_markdown(
            source_value,
            target_value,
            current_path=path,
            content_paths=paths,
            heading_maps=heading_maps,
            yaml_allow_keys=set(config["yaml_translatable_keys"]),
            minimum_cyrillic_ratio=config["minimum_cyrillic_letter_ratio"],
        )
        source_glossary_text = source_value
        target_glossary_text = target_value
        style_fragments = [("", target_value)]
    result["errors"].extend(integrity_errors)
    if source_format(target_data) != unit.get("source_format"):
        result["errors"].append(
            f"byte format changed: expected {unit.get('source_format')}, got {source_format(target_data)}"
        )
    try:
        target_mode = worktree_git_mode(target_path)
    except OSError as exc:
        result["errors"].append(f"cannot inspect target mode: {exc}")
    else:
        if target_mode != unit.get("source_mode"):
            result["errors"].append(f"file mode changed ({unit.get('source_mode')} -> {target_mode})")
    glossary_errors, glossary_warnings = glossary_issues(root, source_glossary_text, target_glossary_text)
    result["errors"].extend(glossary_errors)
    result["warnings"].extend(glossary_warnings)
    style_flags = style_watch_findings(root, style_fragments)
    result["style_flags"] = style_flags
    result["style_flags_sha256"] = style_flags_fingerprint(style_flags)
    result.setdefault("metrics", {})["style_watch_flags"] = len(style_flags)
    result["warnings"].extend(
        f"{flag['location']}: style-watch {flag['rule_id']} matched {flag['literal']!r}; "
        f"{flag['guidance']} Exceptions: {flag['exceptions']}"
        for flag in style_flags
    )
    source_texts = all_content_texts(root, config, manifest, source=True)
    current_texts = all_content_texts(root, config, manifest, source=False)
    baseline_issues = link_issue_set(source_texts, paths, source_mode=True)
    current_issues = link_issue_set(current_texts, paths)
    new_link_issues = sorted(current_issues - baseline_issues)
    result["errors"].extend(f"new broken link: {issue}" for issue in new_link_issues)
    result.setdefault("metrics", {})["baseline_broken_links"] = len(baseline_issues)
    result["metrics"]["current_broken_links"] = len(current_issues)
    result["metrics"]["new_broken_links"] = len(new_link_issues)
    result.update(
        {
            "schema_version": 1,
            "unit_id": unit["id"],
            "path": path,
            "checked_at": utc_now(),
            "source_commit": config["source_commit"],
            "source_sha256": sha256_bytes(source_data),
            "target_sha256": sha256_bytes(target_data),
            "project_hashes": project_hashes(root),
            "authority_hashes": authority_hashes(root),
            "workflow_hashes": workflow_hashes(root),
        }
    )
    result["pass"] = not result["errors"]
    return result


def print_qa_report(report: dict[str, Any]) -> None:
    print(f"QA {'PASS' if report['pass'] else 'FAIL'}: {report['unit_id']} — {report['path']}")
    print(f"Errors: {len(report.get('errors', []))}; warnings: {len(report.get('warnings', []))}")
    for issue in report.get("errors", [])[:50]:
        print(f"ERROR: {issue}")
    if len(report.get("errors", [])) > 50:
        print(f"ERROR: {len(report['errors']) - 50} more errors omitted from console; inspect JSON report")
    for issue in report.get("warnings", [])[:30]:
        print(f"WARN: {issue}")
    if len(report.get("warnings", [])) > 30:
        print(f"WARN: {len(report['warnings']) - 30} more warnings omitted from console; inspect JSON report")


def cmd_qa(args: argparse.Namespace) -> int:
    root = repo_root()
    config, manifest = load_state(root)
    ensure_source_ancestor(root, config)
    if args.write_report:
        ensure_mutation_branch(root, config)
    if args.all_completed:
        units = [
            unit for unit in manifest["units"]
            if unit["status"] in {"completed", "consistency_review"}
        ]
        if not units:
            print("No completed units to regression-check")
            return 0
    else:
        units = [unit_by_arg(manifest, args.unit, default_next=False)]
    failed = 0
    for unit in units:
        report = qa_unit(root, config, manifest, unit)
        if args.write_report:
            if args.all_completed:
                regression = state_dir(root) / REPORTS_DIR / "regression"
                atomic_write_json(regression / f"{compact_timestamp()}-{unit['id']}.json", report)
            else:
                atomic_write_json(state_dir(root) / REPORTS_DIR / f"{unit['id']}.json", report)
        print_qa_report(report)
        if not report["pass"]:
            failed += 1
            if args.write_report and not args.all_completed and unit["status"] in {
                "auto_qa_pass", "independent_review", "needs_revision", "approved"
            }:
                unit["status"] = "needs_revision"
        elif args.write_report and unit["status"] in {"in_progress", "needs_revision"} and not args.all_completed:
            unit["status"] = "auto_qa_pass"
    if args.write_report and not args.all_completed:
        save_manifest(root, manifest)
    return 1 if failed else 0


def rewrite_links_for_unit(
    text: str,
    *,
    current_path: str,
    target_path: str,
    index: dict[str, str | None],
    mapping: dict[str, str],
    preserve_english_display: bool,
) -> tuple[str, list[str]]:
    problems: list[str] = []
    protected = protected_spans(text)

    def replace(match: re.Match[str]) -> str:
        if span_is_protected(match.start(), protected):
            return match.group(0)
        if match.group(1) == "!":
            return match.group(0)
        target, alias = split_wikilink(match.group(2))
        file_part, components = split_wiki_target(target)
        resolved = resolve_wiki_file(file_part, current_path, index)
        if resolved != target_path or not components:
            return match.group(0)
        changed = False
        new_components: list[str] = []
        for component in components:
            if component.startswith("^"):
                new_components.append(component)
                continue
            mapped = mapped_heading(component, mapping)
            if mapped is None:
                problems.append(f"{current_path}: no heading map entry for {component!r}")
                new_components.append(component)
            else:
                new_components.append(mapped)
                changed = changed or mapped != component
        if not changed:
            return match.group(0)
        new_target = file_part + "#" + "#".join(new_components)
        new_alias = alias
        if not alias and preserve_english_display:
            new_alias = components[-1]
        inner = new_target + (f"|{new_alias}" if new_alias else "")
        return f"[[{inner}]]"

    return WIKILINK_RE.sub(replace, text), problems


def canvas_translatable_string_spans(text: str) -> list[tuple[int, int, str]]:
    """Locate only schema-allowlisted Canvas JSON strings while retaining raw byte offsets."""
    decoder = json.JSONDecoder()
    spans: list[tuple[int, int, str]] = []

    def whitespace(index: int) -> int:
        while index < len(text) and text[index] in " \t\r\n":
            index += 1
        return index

    def parse(index: int, path: tuple[Any, ...]) -> int:
        index = whitespace(index)
        if index >= len(text):
            raise WorkflowError("truncated Canvas JSON")
        if text[index] == "{":
            index = whitespace(index + 1)
            if index < len(text) and text[index] == "}":
                return index + 1
            while True:
                try:
                    key, key_end = decoder.raw_decode(text, index)
                except json.JSONDecodeError as exc:
                    raise WorkflowError(f"invalid Canvas object key: {exc}") from exc
                if not isinstance(key, str):
                    raise WorkflowError("Canvas object key is not a string")
                index = whitespace(key_end)
                if index >= len(text) or text[index] != ":":
                    raise WorkflowError("invalid Canvas object separator")
                index = parse(index + 1, path + (key,))
                index = whitespace(index)
                if index < len(text) and text[index] == "}":
                    return index + 1
                if index >= len(text) or text[index] != ",":
                    raise WorkflowError("invalid Canvas object delimiter")
                index = whitespace(index + 1)
        if text[index] == "[":
            index = whitespace(index + 1)
            if index < len(text) and text[index] == "]":
                return index + 1
            item = 0
            while True:
                index = parse(index, path + (item,))
                item += 1
                index = whitespace(index)
                if index < len(text) and text[index] == "]":
                    return index + 1
                if index >= len(text) or text[index] != ",":
                    raise WorkflowError("invalid Canvas array delimiter")
                index = whitespace(index + 1)
        start = index
        try:
            value, end = decoder.raw_decode(text, index)
        except json.JSONDecodeError as exc:
            raise WorkflowError(f"invalid Canvas value: {exc}") from exc
        if isinstance(value, str) and canvas_translatable(path):
            spans.append((start, end, value))
        return end

    end = whitespace(parse(0, ()))
    if end != len(text):
        raise WorkflowError("unexpected trailing data in Canvas JSON")
    return spans


def rewrite_canvas_links_for_unit(
    text: str,
    *,
    current_path: str,
    target_path: str,
    index: dict[str, str | None],
    mapping: dict[str, str],
    preserve_english_display: bool,
) -> tuple[str, list[str]]:
    problems: list[str] = []
    replacements: list[tuple[int, int, str]] = []
    for start, end, value in canvas_translatable_string_spans(text):
        rewritten, found = rewrite_links_for_unit(
            value,
            current_path=current_path,
            target_path=target_path,
            index=index,
            mapping=mapping,
            preserve_english_display=preserve_english_display,
        )
        problems.extend(found)
        if rewritten != value:
            replacements.append((start, end, json.dumps(rewritten, ensure_ascii=False)))
    for start, end, replacement in reversed(replacements):
        text = text[:start] + replacement + text[end:]
    return text, problems


def cmd_sync_links(args: argparse.Namespace) -> int:
    root = repo_root()
    config, manifest = load_state(root)
    if args.check and (args.allow_style_delta or args.style_delta_reason):
        raise WorkflowError("style-delta acknowledgement options cannot be used with read-only --check")
    if args.style_delta_reason and not args.allow_style_delta:
        raise WorkflowError("--style-delta-reason requires --allow-style-delta")
    if not args.check:
        ensure_mutation_branch(root, config)
    ensure_source_ancestor(root, config)
    metadata_errors = validate_source_metadata(root, config, manifest)
    if metadata_errors:
        raise WorkflowError("source/manifest integrity failure: " + "; ".join(metadata_errors[:8]))
    unit = unit_by_arg(manifest, args.unit, default_next=False)
    if not args.check and unit["status"] not in {
        "in_progress", "auto_qa_pass", "independent_review", "needs_revision", "approved"
    }:
        raise WorkflowError("start the unit before synchronizing its translated headings")
    if not unit["path"].endswith(".md"):
        raise WorkflowError("heading-link synchronization applies only to Markdown units")
    source_value = source_text(root, config["source_commit"], unit["path"])
    target_value = (root / unit["path"]).read_text(encoding="utf-8")
    src_rows = heading_rows(source_value)
    dst_rows = heading_rows(target_value)
    mapping = validated_heading_mapping(src_rows, dst_rows)
    rewrite_mapping = heading_rewrite_mapping(root, config, unit, mapping)
    paths = [item["path"] for item in manifest["units"]]
    index = wiki_file_index(paths)
    status_by_path = {item["path"]: item["status"] for item in manifest["units"]}
    pending_writes: list[tuple[dict[str, Any], Path, bytes, str]] = []
    problems: list[str] = []
    changed_paths: list[str] = []
    for path in paths:
        if not path.endswith((".md", ".canvas")) or not (root / path).exists():
            continue
        old_bytes = (root / path).read_bytes()
        old_text = old_bytes.decode("utf-8")
        rewrite = rewrite_links_for_unit if path.endswith(".md") else rewrite_canvas_links_for_unit
        new_text, found = rewrite(
            old_text,
            current_path=path,
            target_path=unit["path"],
            index=index,
            mapping=rewrite_mapping,
            preserve_english_display=path != unit["path"] and status_by_path.get(path) in {"pending", "skipped"},
        )
        problems.extend(found)
        if new_text != old_text:
            changed_paths.append(path)
            changed_unit = next(item for item in manifest["units"] if item["path"] == path)
            pending_writes.append((changed_unit, root / path, new_text.encode("utf-8"), sha256_bytes(old_bytes)))
    if problems:
        raise WorkflowError("link synchronization is ambiguous:\n" + "\n".join(sorted(set(problems))[:40]))
    for changed_unit, _, _, old_hash in pending_writes:
        if changed_unit["id"] == unit["id"]:
            continue
        status = changed_unit.get("status")
        if status not in {"pending", "skipped", "completed", "consistency_review"}:
            raise WorkflowError(
                f"cannot generate an inbound-link edit for {changed_unit['id']} in status {status!r}"
            )
        if status in {"pending", "skipped"} and old_hash != expected_head_sha256(changed_unit):
            raise WorkflowError(f"pending inbound unit {changed_unit['id']} has unrecognized worktree drift")
        if status == "completed" and old_hash != changed_unit.get("target_sha256"):
            raise WorkflowError(f"completed inbound unit {changed_unit['id']} drifted before link synchronization")
        if status == "consistency_review" and old_hash != changed_unit.get("consistency_review", {}).get("target_sha256"):
            raise WorkflowError(f"consistency-review unit {changed_unit['id']} drifted before resynchronization")
    style_delta_preflights: dict[str, dict[str, Any]] = {}
    for changed_unit, _, data, _ in pending_writes:
        if changed_unit["id"] == unit["id"] or changed_unit.get("status") not in {
            "completed", "consistency_review",
        }:
            continue
        prior_report = load_json(state_dir(root) / REPORTS_DIR / f"{changed_unit['id']}.json")
        validate_style_flags_report(prior_report)
        rewritten_text = data.decode("utf-8")
        rewritten_flags = style_watch_findings(
            root, style_fragments_for_target(changed_unit["path"], rewritten_text)
        )
        rewritten_fingerprint = style_flags_fingerprint(rewritten_flags)
        if rewritten_fingerprint == prior_report["style_flags_sha256"]:
            continue
        style_delta_preflights[changed_unit["id"]] = {
            "previous_style_flags_sha256": prior_report["style_flags_sha256"],
            "generated_style_flags_sha256": rewritten_fingerprint,
            "generated_style_flags": rewritten_flags,
            "acknowledged_at": utc_now() if not args.check and args.allow_style_delta else None,
            "reason": (args.style_delta_reason or "").strip(),
        }
    if not args.check:
        if style_delta_preflights and not args.allow_style_delta:
            details = []
            for unit_id, preflight in sorted(style_delta_preflights.items()):
                flags = preflight["generated_style_flags"]
                summary = ", ".join(
                    f"{flag['rule_id']}@{flag['location']}={flag['literal']!r}" for flag in flags[:6]
                ) or "reviewed occurrences were removed/relocated"
                details.append(f"{unit_id}: {summary}")
            raise WorkflowError(
                "link synchronization would change Russian-reviewed style-watch evidence in completed units; "
                "inspect and fix a genuine heading defect now, or rerun with --allow-style-delta and a "
                "nonempty --style-delta-reason before final independent delta review: "
                + "; ".join(details)
            )
        if style_delta_preflights and not (args.style_delta_reason or "").strip():
            raise WorkflowError("--allow-style-delta requires a nonempty --style-delta-reason")
        if args.allow_style_delta and not style_delta_preflights:
            raise WorkflowError("--allow-style-delta was supplied but synchronization creates no style-watch delta")
    if args.check:
        if changed_paths:
            print("Link synchronization required in:")
            for path in changed_paths:
                print(path)
            for unit_id, preflight in sorted(style_delta_preflights.items()):
                print(
                    f"STYLE-DELTA {unit_id}: {preflight['previous_style_flags_sha256']} -> "
                    f"{preflight['generated_style_flags_sha256']}"
                )
            return 1
        print("Heading links are synchronized")
        return 0
    for changed_unit, path, data, old_hash in pending_writes:
        atomic_write_bytes(path, data)
        new_hash = sha256_bytes(data)
        if changed_unit["id"] == unit["id"]:
            continue
        if changed_unit["status"] in {"pending", "skipped"}:
            changed_unit["expected_head_sha256"] = new_hash
            previous_record = changed_unit.get("generated_link_update", {})
            chain = list(previous_record.get("chain", []))
            chain.append(
                {
                    "trigger_unit": unit["id"],
                    "updated_at": utc_now(),
                    "previous_sha256": old_hash,
                    "target_sha256": new_hash,
                }
            )
            changed_unit["generated_link_update"] = {
                "trigger_unit": unit["id"],
                "updated_at": utc_now(),
                "previous_sha256": old_hash,
                "target_sha256": new_hash,
                "origin_source_sha256": changed_unit["source_sha256"],
                "chain": chain,
            }
        elif changed_unit["status"] == "completed":
            changed_unit["status"] = "consistency_review"
            changed_unit["consistency_review"] = {
                "trigger_unit": unit["id"],
                "trigger_translator": unit.get("translator"),
                "detected_at": utc_now(),
                "previous_target_sha256": old_hash,
                "target_sha256": new_hash,
                "reason": "generated inbound heading-link update",
            }
            if changed_unit["id"] in style_delta_preflights:
                changed_unit["consistency_review"]["style_delta_preflight"] = style_delta_preflights[
                    changed_unit["id"]
                ]
        elif changed_unit["status"] == "consistency_review":
            record = changed_unit["consistency_review"]
            record.setdefault("history", []).append(
                {
                    "trigger_unit": unit["id"],
                    "updated_at": utc_now(),
                    "previous_target_sha256": old_hash,
                    "target_sha256": new_hash,
                }
            )
            record["trigger_unit"] = unit["id"]
            record["trigger_translator"] = unit.get("translator")
            record["last_updated_at"] = utc_now()
            record["target_sha256"] = new_hash
            if changed_unit["id"] in style_delta_preflights:
                record["style_delta_preflight"] = style_delta_preflights[changed_unit["id"]]
            else:
                record.pop("style_delta_preflight", None)
    heading_state_path = state_dir(root) / HEADING_MAP_NAME
    heading_state = load_json(heading_state_path)
    heading_state.setdefault("files", {})[unit["path"]] = {
        "unit_id": unit["id"],
        "source_commit": config["source_commit"],
        "source_heading_sha256": sha256_text("\n".join(row["plain"] for row in src_rows)),
        "target_heading_sha256": sha256_text("\n".join(row["plain"] for row in dst_rows)),
        "updated_at": utc_now(),
        "headings": mapping,
    }
    atomic_write_json(heading_state_path, heading_state)
    save_manifest(root, manifest)
    print(f"Synchronized heading links for {unit['id']}; changed {len(changed_paths)} files")
    for path in changed_paths:
        print(path)
    return 0


def cmd_revalidate_links(args: argparse.Namespace) -> int:
    root = repo_root()
    config, manifest = load_state(root)
    ensure_mutation_branch(root, config)
    ensure_source_ancestor(root, config)
    metadata_errors = validate_source_metadata(root, config, manifest)
    if metadata_errors:
        raise WorkflowError("source/manifest integrity failure: " + "; ".join(metadata_errors[:8]))
    unit = unit_by_arg(manifest, args.unit, default_next=False)
    if unit.get("status") != "consistency_review":
        raise WorkflowError("link revalidation applies only to a completed unit awaiting consistency review")
    record = unit.get("consistency_review", {})
    trigger_unit = next(
        (item for item in manifest["units"] if item["id"] == record.get("trigger_unit")),
        None,
    )
    if trigger_unit is None:
        raise WorkflowError("consistency-review trigger unit is missing from the manifest")
    trigger_translator = str(record.get("trigger_translator", "")).strip()
    if not trigger_translator or trigger_translator != str(trigger_unit.get("translator", "")).strip():
        raise WorkflowError("consistency-review trigger-translator provenance is missing or stale")
    unrelated_active = [
        item["id"] for item in active_units(manifest)
        if item["id"] not in {unit["id"], trigger_unit["id"]}
        and item.get("status") != "consistency_review"
    ]
    if unrelated_active:
        raise WorkflowError(
            "resolve unrelated active units before link revalidation: " + ", ".join(unrelated_active)
        )
    current_hash = sha256_bytes((root / unit["path"]).read_bytes())
    if current_hash != record.get("target_sha256"):
        raise WorkflowError("consistency-review target changed after the generated link update")
    reviewer = args.reviewer.strip()
    if not reviewer:
        raise WorkflowError("link consistency reviewer identity is empty")
    if reviewer in {unit.get("translator"), trigger_unit.get("translator")}:
        raise WorkflowError(
            "link consistency reviewer must be independent from both the inbound and triggering translators"
        )
    notes = Path(args.notes_file).read_text(encoding="utf-8").strip()
    if not notes:
        raise WorkflowError("link consistency notes must document the navigation checks")
    report_path = state_dir(root) / REPORTS_DIR / f"{unit['id']}.json"
    previous_report = load_json(report_path)
    validate_style_flags_report(previous_report)
    style_review = load_json(state_dir(root) / REVIEWS_DIR / unit["id"] / "russian-style.json")
    validate_review_identity(style_review, unit, "russian-style")
    validate_style_review_record(style_review)
    if style_review.get("verdict") != "pass":
        raise WorkflowError("prior semantic Russian-style review is not a pass")
    report = qa_unit(root, config, manifest, unit)
    if not report["pass"]:
        print_qa_report(report)
        raise WorkflowError("deterministic QA failed during link consistency review")
    validate_style_flags_report(report)
    semantic_fingerprint = str(style_review.get("style_flags_sha256", ""))
    style_changed = report["style_flags_sha256"] != semantic_fingerprint
    style_delta: dict[str, Any] | None = None
    supplied_style_delta = any(
        (args.style_reviewer, args.style_notes_file, args.style_dispositions_file)
    )
    if style_changed:
        if not all((args.style_reviewer, args.style_notes_file, args.style_dispositions_file)):
            print_qa_report(report)
            raise WorkflowError(
                "generated navigation changed the reviewed Russian style-watch evidence; "
                "revise/resynchronize a genuine defect, or provide an independent --style-reviewer, "
                "--style-notes-file, and identity-bound --style-dispositions-file for the current flags"
            )
        style_reviewer = args.style_reviewer.strip()
        if not style_reviewer or style_reviewer in {
            reviewer, unit.get("translator"), trigger_translator
        }:
            raise WorkflowError(
                "link-delta Russian-style reviewer must be independent from both translators and the link reviewer"
            )
        style_notes = Path(args.style_notes_file).read_text(encoding="utf-8").strip()
        if not style_notes:
            raise WorkflowError("link-delta Russian-style notes must document the visible-language check")
        style_dispositions = load_style_dispositions(args.style_dispositions_file, report, unit)
        style_delta = {
            "schema_version": 1,
            "role": "russian-style-link-delta",
            "reviewer": style_reviewer,
            "reviewed_at": utc_now(),
            "notes": style_notes,
            "target_sha256": report["target_sha256"],
            "style_flags_sha256": report["style_flags_sha256"],
            "reviewed_style_flag_keys": sorted(str(flag["key"]) for flag in report["style_flags"]),
            "style_dispositions": style_dispositions,
        }
    elif supplied_style_delta:
        raise WorkflowError("style-delta review arguments are allowed only when navigation changed style-watch evidence")
    style_transition = {
        "semantic_style_flags_sha256": semantic_fingerprint,
        "current_style_flags_sha256": report["style_flags_sha256"],
        "changed": style_changed,
        "review": style_delta,
    }
    validate_link_style_transition(
        style_transition,
        semantic_fingerprint,
        report,
        unit,
        reviewer,
        trigger_translator,
    )
    archive_record(report_path)
    atomic_write_json(report_path, report)
    review_path = state_dir(root) / REVIEWS_DIR / unit["id"] / "link-consistency.json"
    archive_record(review_path)
    atomic_write_json(
        review_path,
        {
            "schema_version": 1,
            "unit_id": unit["id"],
            "path": unit["path"],
            "role": "link-consistency",
            "reviewer": reviewer,
            "reviewed_at": utc_now(),
            "verdict": "pass",
            "notes": notes,
            "style_transition": style_transition,
            **qa_identity(report),
            "trigger": record,
        },
    )
    unit.update(
        {
            "status": "completed",
            "target_sha256": report["target_sha256"],
            "completed_project_hashes": report.get("project_hashes", {}),
            "completed_workflow_hashes": report.get("workflow_hashes", {}),
            "consistency_review_resolved_at": utc_now(),
            "consistency_review_reviewer": reviewer,
            "link_consistency_reviewed_at": utc_now(),
            "link_consistency_reviewer": reviewer,
        }
    )
    unit.pop("consistency_review", None)
    save_manifest(root, manifest)
    print(f"Revalidated generated inbound links for {unit['id']}")
    return 0


def qa_identity(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "unit_id": report.get("unit_id"),
        "path": report.get("path"),
        "source_commit": report.get("source_commit"),
        "source_sha256": report.get("source_sha256"),
        "target_sha256": report.get("target_sha256"),
        "authority_hashes": report.get("authority_hashes", {}),
        "workflow_hashes": report.get("workflow_hashes", {}),
    }


def validate_review_identity(review: dict[str, Any], unit: dict[str, Any], role: str) -> None:
    if review.get("schema_version") != 1:
        raise WorkflowError(f"{role} review has an unsupported schema")
    if review.get("unit_id") != unit["id"] or review.get("path") != unit["path"]:
        raise WorkflowError(f"{role} review belongs to a different unit/path")
    if review.get("role") != role:
        raise WorkflowError(f"{role} review record has mismatched role identity")
    reviewer = str(review.get("reviewer", "")).strip()
    if not reviewer:
        raise WorkflowError(f"{role} review has no reviewer identity")
    if reviewer == unit.get("translator"):
        raise WorkflowError(f"{role} reviewer is not independent from the translator")


def load_current_qa(
    root: Path, config: dict[str, Any], manifest: dict[str, Any], unit: dict[str, Any]
) -> dict[str, Any]:
    metadata_errors = validate_source_metadata(root, config, manifest)
    if metadata_errors:
        raise WorkflowError("source/manifest integrity failure: " + "; ".join(metadata_errors[:8]))
    path = state_dir(root) / REPORTS_DIR / f"{unit['id']}.json"
    report = load_json(path)
    target_hash = sha256_bytes((root / unit["path"]).read_bytes())
    if report.get("target_sha256") != target_hash:
        raise WorkflowError("QA report is stale; rerun qa --write-report after the latest content change")
    if not report.get("pass"):
        raise WorkflowError("latest QA report does not pass")
    validate_style_flags_report(report)
    expected = {
        "unit_id": unit["id"],
        "path": unit["path"],
        "source_commit": config["source_commit"],
        "source_sha256": unit["source_sha256"],
        "target_sha256": target_hash,
        "authority_hashes": authority_hashes(root),
        "workflow_hashes": workflow_hashes(root),
    }
    if qa_identity(report) != expected:
        raise WorkflowError("QA report identity is stale; rerun qa --write-report after source/authority/workflow changes")
    return report


def archive_record(path: Path) -> None:
    if not path.exists():
        return
    history = path.parent / "history"
    history.mkdir(parents=True, exist_ok=True)
    destination = history / f"{compact_timestamp()}-{path.name}"
    counter = 2
    while destination.exists():
        destination = history / f"{compact_timestamp()}-{counter}-{path.name}"
        counter += 1
    os.replace(path, destination)


def cmd_review(args: argparse.Namespace) -> int:
    root = repo_root()
    config, manifest = load_state(root)
    ensure_mutation_branch(root, config)
    ensure_source_ancestor(root, config)
    unit = unit_by_arg(manifest, args.unit, default_next=False)
    require_no_outstanding_consistency(manifest, unit["id"])
    if unit["status"] not in {"auto_qa_pass", "independent_review", "needs_revision", "approved"}:
        raise WorkflowError("record reviews only after a started unit has a passing written QA report")
    if args.role not in config["required_review_roles"]:
        raise WorkflowError(f"unknown review role {args.role!r}")
    reviewer = args.reviewer.strip()
    if not reviewer:
        raise WorkflowError("reviewer identity must be nonempty")
    if reviewer == unit.get("translator"):
        raise WorkflowError("reviewer must be independent from the translator")
    report = load_current_qa(root, config, manifest, unit)
    if args.role == "russian-style":
        if args.verdict == "pass" or args.style_dispositions_file:
            style_dispositions = load_style_dispositions(args.style_dispositions_file, report, unit)
            style_flag_keys = sorted(str(flag["key"]) for flag in validate_style_flags_report(report))
        else:
            style_dispositions = []
            style_flag_keys = []
    else:
        if args.style_dispositions_file:
            raise WorkflowError("only the Russian-style review accepts style-watch dispositions")
        style_dispositions = []
        style_flag_keys = []
    category_scores = {
        "fidelity": args.fidelity,
        "mechanics": args.mechanics,
        "terminology": args.terminology,
        "language": args.language,
        "navigation": args.navigation,
        "typography": args.typography,
    }
    for category, value in category_scores.items():
        if not 0 <= value <= 5:
            raise WorkflowError(f"{category} rating must be between 0 and 5")
    weights = {
        "fidelity": 30,
        "mechanics": 25,
        "terminology": 15,
        "language": 15,
        "navigation": 10,
        "typography": 5,
    }
    weighted_score = round(sum(weights[key] * category_scores[key] / 5 for key in weights), 1)
    issue_counts = {"blocker": args.blockers, "major": args.majors, "minor": args.minors}
    if any(value < 0 for value in issue_counts.values()):
        raise WorkflowError("review issue counts cannot be negative")
    if args.verdict == "pass" and (
        weighted_score < config["minimum_review_score"]
        or args.blockers != 0
        or args.majors != 0
        or min(category_scores.values()) < 4
    ):
        raise WorkflowError(
            "a passing review requires the minimum weighted score, all ratings >= 4, and zero blockers/majors"
        )
    notes_path = Path(args.notes_file)
    notes = notes_path.read_text(encoding="utf-8").strip()
    if not notes:
        raise WorkflowError("review notes must document what was checked")
    review_dir = state_dir(root) / REVIEWS_DIR / unit["id"]
    review_dir.mkdir(parents=True, exist_ok=True)
    for other_role in config["required_review_roles"]:
        other_path = review_dir / f"{other_role}.json"
        if other_role != args.role and other_path.exists():
            other = load_json(other_path)
            if other.get("reviewer") == reviewer:
                raise WorkflowError("the two required reviews must use different reviewers")
    review = {
        "schema_version": 1,
        "unit_id": unit["id"],
        "path": unit["path"],
        "role": args.role,
        "reviewer": reviewer,
        "reviewed_at": utc_now(),
        "target_sha256": report["target_sha256"],
        "source_commit": report["source_commit"],
        "source_sha256": report["source_sha256"],
        "verdict": args.verdict,
        "score": weighted_score,
        "category_scores": category_scores,
        "unresolved_issues": args.blockers + args.majors,
        "issue_counts": issue_counts,
        "notes": notes,
        "authority_hashes": report.get("authority_hashes", {}),
        "workflow_hashes": report.get("workflow_hashes", {}),
    }
    if args.role == "russian-style":
        review.update(
            {
                "style_flags_sha256": report["style_flags_sha256"],
                "reviewed_style_flag_keys": style_flag_keys,
                "style_dispositions": style_dispositions,
            }
        )
    review_path = review_dir / f"{args.role}.json"
    archive_record(review_path)
    atomic_write_json(review_path, review)
    if args.verdict == "fail":
        unit["status"] = "needs_revision"
    else:
        passing = 0
        for role in config["required_review_roles"]:
            path = review_dir / f"{role}.json"
            if path.exists():
                value = load_json(path)
                try:
                    validate_review_identity(value, unit, role)
                    validate_style_review_record(value, report)
                except WorkflowError:
                    continue
                if value.get("verdict") == "pass" and qa_identity(value) == qa_identity(report):
                    passing += 1
        unit["status"] = "approved" if passing == len(config["required_review_roles"]) else "independent_review"
    save_manifest(root, manifest)
    print(f"Recorded {args.role} review for {unit['id']}: {args.verdict} ({weighted_score}/100)")
    return 0


def passing_reviews(
    root: Path,
    config: dict[str, Any],
    unit: dict[str, Any],
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    review_dir = state_dir(root) / REVIEWS_DIR / unit["id"]
    for role in config["required_review_roles"]:
        review_path = review_dir / f"{role}.json"
        if not review_path.exists():
            raise WorkflowError(f"missing required {role} review")
        review = load_json(review_path)
        validate_review_identity(review, unit, role)
        validate_style_review_record(review, report)
        if review.get("verdict") != "pass" or qa_identity(review) != qa_identity(report):
            raise WorkflowError(f"{role} review is failing or stale")
        if review.get("score", 0) < config["minimum_review_score"] or review.get("unresolved_issues") != 0:
            raise WorkflowError(f"{role} review does not meet the quality gate")
        issue_counts = review.get("issue_counts", {})
        if set(issue_counts) != {"blocker", "major", "minor"}:
            raise WorkflowError(f"{role} review lacks structured issue counts")
        if issue_counts["blocker"] or issue_counts["major"]:
            raise WorkflowError(f"{role} review has unresolved blocker/major findings")
        scores = review.get("category_scores", {})
        if set(scores) != {"fidelity", "mechanics", "terminology", "language", "navigation", "typography"}:
            raise WorkflowError(f"{role} review lacks structured category ratings")
        if min(scores.values()) < 4:
            raise WorkflowError(f"{role} review has a category below 4/5")
        result.append(review)
    if len({review["reviewer"] for review in result}) != len(result):
        raise WorkflowError("required review roles must use independent reviewers")
    return result


def cmd_learn(args: argparse.Namespace) -> int:
    root = repo_root()
    config, manifest = load_state(root)
    ensure_mutation_branch(root, config)
    ensure_source_ancestor(root, config)
    unit = unit_by_arg(manifest, args.unit, default_next=False)
    require_no_outstanding_consistency(manifest, unit["id"])
    if unit["status"] != "approved":
        raise WorkflowError("record learning only after both required reviews approve the current unit")
    report = load_current_qa(root, config, manifest, unit)
    passing_reviews(root, config, unit, report)
    if not args.terms_reviewed:
        raise WorkflowError("learning cannot finish until term candidates were explicitly reviewed")
    if not args.style_watch_reviewed:
        raise WorkflowError("learning cannot finish until style-watch candidates were explicitly reviewed")
    curator = args.curator.strip()
    if not curator:
        raise WorkflowError("learning curator identity must be nonempty")
    lesson = Path(args.lesson_file).read_text(encoding="utf-8").strip()
    if not lesson:
        raise WorkflowError("the retrospective lesson file is empty")
    lessons_path = state_dir(root) / "lessons.md"
    existing = lessons_path.read_text(encoding="utf-8") if lessons_path.exists() else "# Reviewed Translation Lessons\n"
    entry = f"\n## {utc_now()[:10]} — {unit['id']}\n\nCurator: `{curator}`\n\n{lesson}\n"
    atomic_write_text(lessons_path, existing.rstrip() + "\n" + entry)
    learning = {
        "schema_version": 1,
        "unit_id": unit["id"],
        "path": unit["path"],
        "curator": curator,
        "recorded_at": utc_now(),
        "target_sha256": report["target_sha256"],
        "source_commit": report["source_commit"],
        "source_sha256": report["source_sha256"],
        "authority_hashes": report.get("authority_hashes", {}),
        "terms_reviewed": True,
        "style_watch_reviewed": True,
        "project_hashes": project_hashes(root),
        "workflow_hashes": workflow_hashes(root),
        "lesson": lesson,
    }
    learning_path = state_dir(root) / REVIEWS_DIR / unit["id"] / "learning.json"
    archive_record(learning_path)
    atomic_write_json(learning_path, learning)
    unit["learning_recorded"] = True
    save_manifest(root, manifest)
    print(f"Recorded reviewed learning for {unit['id']}")
    return 0


def cmd_finish(args: argparse.Namespace) -> int:
    root = repo_root()
    config, manifest = load_state(root)
    ensure_mutation_branch(root, config)
    ensure_source_ancestor(root, config)
    unit = unit_by_arg(manifest, args.unit, default_next=False)
    require_no_outstanding_consistency(manifest, unit["id"])
    if unit["status"] != "approved":
        raise WorkflowError("finish requires an approved active unit")
    config_hash = sha256_bytes((state_dir(root) / CONFIG_NAME).read_bytes())
    if unit.get("started_config_sha256") != config_hash:
        raise WorkflowError("config changed during the active unit")
    progress = load_progress(root, config, unit)
    pending_segments = [item["segment"] for item in progress.get("segments", []) if item.get("status") != "completed"]
    if pending_segments:
        raise WorkflowError("finish requires every planned segment to be completed: " + ", ".join(map(str, pending_segments[:20])))
    ledger_path = unit_work_dir(root, unit) / "ledger.md"
    if not ledger_path.exists() or sha256_bytes(ledger_path.read_bytes()) == unit.get("initial_ledger_sha256"):
        raise WorkflowError("finish requires a reviewed update to the persistent translation ledger")
    ensure_finish_scope(root, config, manifest, unit)
    heading_errors = validate_heading_map_entry(root, config, unit)
    if heading_errors:
        raise WorkflowError("; ".join(heading_errors))
    report = qa_unit(root, config, manifest, unit)
    atomic_write_json(state_dir(root) / REPORTS_DIR / f"{unit['id']}.json", report)
    if not report["pass"]:
        print_qa_report(report)
        raise WorkflowError("final deterministic QA failed")
    target_hash = report["target_sha256"]
    passing_reviews(root, config, unit, report)
    learning_path = state_dir(root) / REVIEWS_DIR / unit["id"] / "learning.json"
    learning = load_json(learning_path)
    if learning.get("schema_version") != 1:
        raise WorkflowError("learning record has an unsupported schema")
    if learning.get("unit_id") != unit["id"] or learning.get("path") != unit["path"]:
        raise WorkflowError("learning record belongs to a different unit/path")
    if not str(learning.get("curator", "")).strip():
        raise WorkflowError("learning record has no curator identity")
    if (
        learning.get("target_sha256") != target_hash
        or not learning.get("terms_reviewed")
        or not learning.get("style_watch_reviewed")
    ):
        raise WorkflowError("learning record is stale or incomplete")
    if learning.get("workflow_hashes") != report.get("workflow_hashes"):
        raise WorkflowError("learning record used a stale workflow version")
    if qa_identity(learning) != qa_identity(report):
        raise WorkflowError("learning record used stale source or authority identity")
    current_hashes = project_hashes(root)
    learned_hashes = learning.get("project_hashes", {})
    for name in (
        "glossary.tsv", "term-candidates.tsv", STYLE_WATCH_NAME,
        "style-guide.md", "voice-cards.md", "lessons.md",
    ):
        if current_hashes.get(name) != learned_hashes.get(name):
            raise WorkflowError(f"{name} changed after learning was recorded; re-curate learning")
    unit.update(
        {
            "status": "completed",
            "completed_at": utc_now(),
            "target_sha256": target_hash,
            "semantic_target_sha256": target_hash,
            "qa_report": str((STATE_REL / REPORTS_DIR / f"{unit['id']}.json").as_posix()),
            "completed_project_hashes": project_hashes(root),
            "completed_workflow_hashes": workflow_hashes(root),
            "completion_minimum_review_score": config["minimum_review_score"],
            "completed_work_hashes": unit_work_hashes(root, unit),
        }
    )
    save_manifest(root, manifest)
    print(f"Completed {unit['id']}: {unit['path']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="pin a source commit and create the unit manifest")
    init.add_argument("--source-ref", default="HEAD")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    status = sub.add_parser("status", help="show branch, baseline, and unit state")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    seal = sub.add_parser("seal-workflow", help="approve and hash workflow-support changes between units")
    seal.add_argument("--reason", required=True)
    seal.set_defaults(func=cmd_seal_workflow)

    next_parser = sub.add_parser("next", help="show the next pending unit")
    next_parser.add_argument("--json", action="store_true")
    next_parser.set_defaults(func=cmd_next)

    start = sub.add_parser("start", help="lock one unit for translation")
    start.add_argument("unit", nargs="?")
    start.add_argument("--translator", required=True)
    start.add_argument("--reason")
    start.set_defaults(func=cmd_start)

    reopen = sub.add_parser("reopen", help="reopen an evidenced completed unit for semantic revision")
    reopen.add_argument("unit")
    reopen.add_argument("--translator", required=True)
    reopen.add_argument("--reason", required=True)
    reopen.set_defaults(func=cmd_reopen)

    context = sub.add_parser("context", help="emit a compact context packet")
    context.add_argument("unit", nargs="?")
    context.set_defaults(func=cmd_context)

    segments = sub.add_parser("segments", help="plan safe source segments")
    segments.add_argument("unit", nargs="?")
    segments.add_argument("--max-words", type=int)
    segments.set_defaults(func=cmd_segments)

    progress = sub.add_parser("progress", help="show persistent segment progress for the active unit")
    progress.add_argument("unit", nargs="?")
    progress.set_defaults(func=cmd_progress)

    segment_done = sub.add_parser("segment-done", help="mark one planned segment complete with notes")
    segment_done.add_argument("unit")
    segment_done.add_argument("segment", type=int)
    segment_done.add_argument("--agent", required=True)
    segment_done.add_argument("--notes-file", required=True)
    segment_done.set_defaults(func=cmd_segment_done)

    sync = sub.add_parser("sync-links", help="synchronize translated heading anchors vault-wide")
    sync.add_argument("unit")
    sync.add_argument("--check", action="store_true")
    sync.add_argument("--allow-style-delta", action="store_true")
    sync.add_argument("--style-delta-reason")
    sync.set_defaults(func=cmd_sync_links)

    revalidate = sub.add_parser("revalidate-links", help="review generated links in a completed inbound unit")
    revalidate.add_argument("unit")
    revalidate.add_argument("--reviewer", required=True)
    revalidate.add_argument("--notes-file", required=True)
    revalidate.add_argument("--style-reviewer")
    revalidate.add_argument("--style-notes-file")
    revalidate.add_argument("--style-dispositions-file")
    revalidate.set_defaults(func=cmd_revalidate_links)

    qa = sub.add_parser("qa", help="compare a target against its pinned source blob")
    qa.add_argument("unit", nargs="?")
    qa.add_argument("--write-report", action="store_true")
    qa.add_argument("--all-completed", action="store_true")
    qa.set_defaults(func=cmd_qa)

    review = sub.add_parser("review", help="record an independent review")
    review.add_argument("unit")
    review.add_argument("--role", required=True, choices=["fidelity", "russian-style"])
    review.add_argument("--reviewer", required=True)
    review.add_argument("--fidelity", required=True, type=float)
    review.add_argument("--mechanics", required=True, type=float)
    review.add_argument("--terminology", required=True, type=float)
    review.add_argument("--language", required=True, type=float)
    review.add_argument("--navigation", required=True, type=float)
    review.add_argument("--typography", required=True, type=float)
    review.add_argument("--verdict", required=True, choices=["pass", "fail"])
    review.add_argument("--blockers", required=True, type=int)
    review.add_argument("--majors", required=True, type=int)
    review.add_argument("--minors", required=True, type=int)
    review.add_argument("--notes-file", required=True)
    review.add_argument("--style-dispositions-file")
    review.set_defaults(func=cmd_review)

    learn = sub.add_parser("learn", help="record reviewed terminology/style learning")
    learn.add_argument("unit")
    learn.add_argument("--curator", required=True)
    learn.add_argument("--lesson-file", required=True)
    learn.add_argument("--terms-reviewed", action="store_true")
    learn.add_argument("--style-watch-reviewed", action="store_true")
    learn.set_defaults(func=cmd_learn)

    finish = sub.add_parser("finish", help="enforce all gates and complete a unit")
    finish.add_argument("unit")
    finish.set_defaults(func=cmd_finish)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except WorkflowError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
