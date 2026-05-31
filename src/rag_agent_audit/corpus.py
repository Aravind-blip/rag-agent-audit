"""
Corpus scanning and inventory.

scan_corpus      — stream ScanRecord objects from a directory tree.
record_to_jsonl  — serialize a ScanRecord to a JSONL line.
record_from_jsonl — deserialize a JSONL line to a ScanRecord.
compute_stats    — aggregate StatsResult from a ScanRecord stream.
format_stats     — format StatsResult as a human-readable report.
"""

from __future__ import annotations

import heapq
import json
import os
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

DEFAULT_INCLUDE_EXT_STR: str = ".md,.txt,.html,.json,.yaml,.yml,.pdf"

DEFAULT_INCLUDE_EXTS: frozenset[str] = frozenset(DEFAULT_INCLUDE_EXT_STR.split(","))

DEFAULT_EXCLUDE_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "node_modules",
        "dist",
        "build",
    }
)

RISKY_KEYWORDS: tuple[str, ...] = (
    "secret",
    "credential",
    "password",
    "token",
    "api_key",
    "apikey",
)

_TOP_N_LARGEST: int = 10
_MAX_DISPLAY_DUPLICATES: int = 20
_MAX_PATHS_PER_DUPLICATE: int = 5
_MAX_DISPLAY_RISKY: int = 20


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ScanRecord:
    """One file entry in the corpus manifest."""

    path: str  # relative to root, forward slashes
    size_bytes: int
    extension: str
    tenant_id: str | None


@dataclass
class StatsResult:
    """Aggregated statistics over a corpus manifest."""

    total_files: int
    total_size_bytes: int
    by_extension: dict[str, int]  # extension → count, sorted alphabetically
    by_tenant: dict[str, int]  # tenant_id (or "(unknown)") → count
    duplicate_basenames: dict[str, list[str]]  # basename → [path, ...]
    risky_filenames: list[str]  # paths whose stem contains a risky keyword
    largest_files: list[tuple[str, int]]  # (path, size_bytes), up to _TOP_N_LARGEST


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def format_bytes(n: int) -> str:
    """Human-readable byte count."""
    if n < 1_024:
        return f"{n} B"
    if n < 1_048_576:
        return f"{n / 1_024:.1f} KB"
    if n < 1_073_741_824:
        return f"{n / 1_048_576:.1f} MB"
    return f"{n / 1_073_741_824:.1f} GB"


def parse_include_exts(raw: str) -> frozenset[str]:
    """Parse a comma-separated extension string.

    Ensures each extension starts with '.' and is lowercased.
    """
    parts = [p.strip().lower() for p in raw.split(",") if p.strip()]
    return frozenset(p if p.startswith(".") else f".{p}" for p in parts)


def merge_exclude_dirs(extra: list[str] | None) -> frozenset[str]:
    """Merge user-supplied dir names (possibly comma-joined) with defaults."""
    result: set[str] = set(DEFAULT_EXCLUDE_DIRS)
    if extra:
        for item in extra:
            for part in item.split(","):
                part = part.strip()
                if part:
                    result.add(part)
    return frozenset(result)


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------


def scan_corpus(
    root: Path,
    *,
    include_exts: frozenset[str] = DEFAULT_INCLUDE_EXTS,
    exclude_dirs: frozenset[str] = DEFAULT_EXCLUDE_DIRS,
    tenant_segment: int | None = None,
    max_files: int | None = None,
    follow_symlinks: bool = False,
) -> Iterator[ScanRecord]:
    """Yield ScanRecord objects for each matching file under *root*.

    Streams results; does not load file content into memory.
    Directories in *exclude_dirs* are pruned before descent.
    Symlinks are not followed unless *follow_symlinks* is True.
    """
    count = 0
    for dirpath_str, dirnames, filenames in os.walk(
        root, followlinks=follow_symlinks, topdown=True
    ):
        # Prune excluded dirs in-place — os.walk will not descend into them.
        dirnames[:] = sorted(d for d in dirnames if d not in exclude_dirs)

        for filename in sorted(filenames):
            if max_files is not None and count >= max_files:
                return

            filepath = Path(dirpath_str) / filename
            ext = filepath.suffix.lower()

            if ext not in include_exts:
                continue

            try:
                size_bytes = filepath.stat().st_size
            except OSError:
                continue

            rel = filepath.relative_to(root)
            path_str = rel.as_posix()

            tenant_id: str | None = None
            if tenant_segment is not None:
                dir_parts = rel.parts[:-1]  # exclude filename
                if tenant_segment < len(dir_parts):
                    tenant_id = dir_parts[tenant_segment]

            yield ScanRecord(
                path=path_str,
                size_bytes=size_bytes,
                extension=ext,
                tenant_id=tenant_id,
            )
            count += 1


# ---------------------------------------------------------------------------
# JSONL serialization
# ---------------------------------------------------------------------------


def record_to_jsonl(record: ScanRecord) -> str:
    """Serialize a ScanRecord to a single JSONL line (no trailing newline)."""
    return json.dumps(asdict(record), ensure_ascii=False)


def record_from_jsonl(line: str) -> ScanRecord:
    """Deserialize a single JSONL line to a ScanRecord.

    Raises json.JSONDecodeError or KeyError on malformed input.
    """
    data: dict[str, Any] = json.loads(line)
    return ScanRecord(
        path=data["path"],
        size_bytes=int(data["size_bytes"]),
        extension=data["extension"],
        tenant_id=data.get("tenant_id"),
    )


def iter_manifest(path: Path) -> Iterator[ScanRecord]:
    """Stream ScanRecord objects from a JSONL manifest file.

    Skips blank lines and lines that fail to parse (with no exception raised).
    """
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield record_from_jsonl(line)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def compute_stats(records: Iterator[ScanRecord]) -> StatsResult:
    """Aggregate statistics from a stream of ScanRecord objects.

    Accumulates in O(n) memory (necessary for duplicate-basename detection).
    Uses a heap for the largest-files list to avoid a full sort.
    """
    total_files = 0
    total_size_bytes = 0
    by_extension: dict[str, int] = defaultdict(int)
    by_tenant: dict[str, int] = defaultdict(int)
    basenames: dict[str, list[str]] = defaultdict(list)
    risky: list[str] = []
    all_sizes: list[tuple[str, int]] = []

    for record in records:
        total_files += 1
        total_size_bytes += record.size_bytes
        by_extension[record.extension] += 1
        by_tenant[record.tenant_id or "(unknown)"] += 1

        basename = record.path.split("/")[-1]
        basenames[basename].append(record.path)

        stem = Path(record.path).stem.lower()
        if any(kw in stem for kw in RISKY_KEYWORDS):
            risky.append(record.path)

        all_sizes.append((record.path, record.size_bytes))

    duplicate_basenames: dict[str, list[str]] = {
        k: sorted(v) for k, v in basenames.items() if len(v) > 1
    }

    largest = heapq.nlargest(_TOP_N_LARGEST, all_sizes, key=lambda x: x[1])

    return StatsResult(
        total_files=total_files,
        total_size_bytes=total_size_bytes,
        by_extension=dict(sorted(by_extension.items())),
        by_tenant=dict(sorted(by_tenant.items())),
        duplicate_basenames=duplicate_basenames,
        risky_filenames=sorted(risky),
        largest_files=largest,
    )


def format_stats(stats: StatsResult) -> str:
    """Format a StatsResult as a human-readable, deterministic report."""
    lines: list[str] = []

    lines.append(f"Total files   : {stats.total_files}")
    lines.append(f"Total size    : {format_bytes(stats.total_size_bytes)}")

    lines.append("")
    lines.append("By extension:")
    if stats.by_extension:
        for ext, cnt in sorted(stats.by_extension.items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"  {ext or '(none)':<14} {cnt}")
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("By tenant:")
    if stats.by_tenant:
        for tenant, cnt in sorted(stats.by_tenant.items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"  {tenant:<24} {cnt}")
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("Duplicate basenames:")
    if stats.duplicate_basenames:
        sorted_dupes = sorted(stats.duplicate_basenames)
        shown_dupes = sorted_dupes[:_MAX_DISPLAY_DUPLICATES]
        hidden_dupes = len(sorted_dupes) - len(shown_dupes)
        for basename in shown_dupes:
            lines.append(f"  {basename}")
            paths = stats.duplicate_basenames[basename]
            shown_paths = paths[:_MAX_PATHS_PER_DUPLICATE]
            hidden_paths = len(paths) - len(shown_paths)
            for p in shown_paths:
                lines.append(f"    - {p}")
            if hidden_paths:
                lines.append(f"    ... and {hidden_paths} more paths.")
        if hidden_dupes:
            lines.append(f"  ... and {hidden_dupes} more duplicate basenames.")
    else:
        lines.append("  None.")

    lines.append("")
    lines.append("Risky-looking filenames:")
    if stats.risky_filenames:
        shown_risky = stats.risky_filenames[:_MAX_DISPLAY_RISKY]
        hidden_risky = len(stats.risky_filenames) - len(shown_risky)
        for p in shown_risky:
            lines.append(f"  ! {p}")
        if hidden_risky:
            lines.append(f"  ... and {hidden_risky} more risky-looking filenames.")
    else:
        lines.append("  None.")

    lines.append("")
    lines.append(f"Largest files (top {_TOP_N_LARGEST}):")
    if stats.largest_files:
        for path, size in stats.largest_files:
            lines.append(f"  {format_bytes(size):<12} {path}")
    else:
        lines.append("  (none)")

    return "\n".join(lines)
