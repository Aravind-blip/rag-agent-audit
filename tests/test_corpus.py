"""Tests for corpus scan and stats commands."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from rag_agent_audit.cli import app
from rag_agent_audit.corpus import (
    DEFAULT_EXCLUDE_DIRS,
    ScanRecord,
    StatsResult,
    compute_stats,
    format_bytes,
    format_stats,
    iter_manifest,
    merge_exclude_dirs,
    parse_include_exts,
    record_from_jsonl,
    record_to_jsonl,
    scan_corpus,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_file(path: Path, content: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _records(tmp_path: Path, **kwargs: object) -> list[ScanRecord]:
    return list(scan_corpus(tmp_path, **kwargs))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# parse_include_exts
# ---------------------------------------------------------------------------


def test_parse_include_exts_normalizes_to_lowercase() -> None:
    result = parse_include_exts(".MD,.TXT")
    assert ".md" in result
    assert ".txt" in result


def test_parse_include_exts_adds_dot_if_missing() -> None:
    result = parse_include_exts("md,txt")
    assert ".md" in result
    assert ".txt" in result


# ---------------------------------------------------------------------------
# format_bytes
# ---------------------------------------------------------------------------


def test_format_bytes_bytes() -> None:
    assert format_bytes(500) == "500 B"


def test_format_bytes_kilobytes() -> None:
    assert format_bytes(2048) == "2.0 KB"


def test_format_bytes_megabytes() -> None:
    assert format_bytes(2 * 1024 * 1024) == "2.0 MB"


# ---------------------------------------------------------------------------
# record_to_jsonl / record_from_jsonl
# ---------------------------------------------------------------------------


def test_record_round_trips_through_jsonl() -> None:
    r = ScanRecord(path="org_a/doc.md", size_bytes=42, extension=".md", tenant_id="org_a")
    line = record_to_jsonl(r)
    parsed = json.loads(line)
    assert parsed["path"] == "org_a/doc.md"
    assert parsed["size_bytes"] == 42
    assert parsed["extension"] == ".md"
    assert parsed["tenant_id"] == "org_a"


def test_record_round_trips_null_tenant() -> None:
    r = ScanRecord(path="doc.md", size_bytes=10, extension=".md", tenant_id=None)
    line = record_to_jsonl(r)
    r2 = record_from_jsonl(line)
    assert r2.tenant_id is None


# ---------------------------------------------------------------------------
# scan_corpus — basic behavior
# ---------------------------------------------------------------------------


def test_scan_writes_valid_jsonl(tmp_path: Path) -> None:
    _make_file(tmp_path / "a.md", "hello")
    _make_file(tmp_path / "b.txt", "world")
    records = _records(tmp_path)
    assert len(records) == 2
    for rec in records:
        line = record_to_jsonl(rec)
        data = json.loads(line)
        assert "path" in data
        assert "size_bytes" in data
        assert "extension" in data
        assert "tenant_id" in data


def test_scan_path_uses_forward_slashes(tmp_path: Path) -> None:
    _make_file(tmp_path / "sub" / "doc.md")
    records = _records(tmp_path)
    assert records[0].path == "sub/doc.md"


def test_scan_extension_is_lowercase(tmp_path: Path) -> None:
    _make_file(tmp_path / "DOC.MD", "content")
    records = _records(tmp_path)
    assert records[0].extension == ".md"


def test_scan_size_bytes_is_populated(tmp_path: Path) -> None:
    content = "hello world"
    _make_file(tmp_path / "doc.md", content)
    records = _records(tmp_path)
    assert records[0].size_bytes == len(content.encode())


# ---------------------------------------------------------------------------
# scan_corpus — include extensions
# ---------------------------------------------------------------------------


def test_scan_respects_include_extensions(tmp_path: Path) -> None:
    _make_file(tmp_path / "a.md")
    _make_file(tmp_path / "b.py")   # .py not in defaults
    _make_file(tmp_path / "c.sh")   # .sh not in defaults
    records = _records(tmp_path)
    assert len(records) == 1
    assert records[0].extension == ".md"


def test_scan_custom_include_extensions(tmp_path: Path) -> None:
    _make_file(tmp_path / "a.py")
    _make_file(tmp_path / "b.md")
    records = _records(tmp_path, include_exts=parse_include_exts(".py"))
    assert len(records) == 1
    assert records[0].extension == ".py"


# ---------------------------------------------------------------------------
# scan_corpus — excluded directories
# ---------------------------------------------------------------------------


def test_scan_excludes_default_ignored_dirs(tmp_path: Path) -> None:
    _make_file(tmp_path / "docs" / "policy.md")
    for excluded in (".git", ".venv", "__pycache__", "node_modules"):
        _make_file(tmp_path / excluded / "readme.md")

    records = _records(tmp_path)
    paths = [r.path for r in records]
    assert "docs/policy.md" in paths
    for excluded in (".git", ".venv", "__pycache__", "node_modules"):
        assert f"{excluded}/readme.md" not in paths


def test_scan_custom_exclude_dir(tmp_path: Path) -> None:
    _make_file(tmp_path / "internal" / "secret.md")
    _make_file(tmp_path / "public" / "policy.md")

    records = _records(tmp_path, exclude_dirs=DEFAULT_EXCLUDE_DIRS | {"internal"})
    paths = [r.path for r in records]
    assert "public/policy.md" in paths
    assert "internal/secret.md" not in paths


def test_merge_exclude_dirs_adds_to_defaults() -> None:
    result = merge_exclude_dirs(["mydir"])
    assert "mydir" in result
    assert ".git" in result  # defaults preserved


def test_merge_exclude_dirs_splits_commas() -> None:
    result = merge_exclude_dirs(["dir1,dir2"])
    assert "dir1" in result
    assert "dir2" in result


def test_merge_exclude_dirs_handles_none() -> None:
    result = merge_exclude_dirs(None)
    assert ".git" in result


# ---------------------------------------------------------------------------
# scan_corpus — tenant inference
# ---------------------------------------------------------------------------


def test_scan_infers_tenant_from_segment_0(tmp_path: Path) -> None:
    _make_file(tmp_path / "org_a" / "doc.md")
    _make_file(tmp_path / "org_b" / "doc.md")
    records = _records(tmp_path, tenant_segment=0)
    tenants = {r.tenant_id for r in records}
    assert tenants == {"org_a", "org_b"}


def test_scan_infers_tenant_from_segment_1(tmp_path: Path) -> None:
    _make_file(tmp_path / "data" / "tenant_x" / "doc.md")
    records = _records(tmp_path, tenant_segment=1)
    assert records[0].tenant_id == "tenant_x"


def test_scan_tenant_none_for_root_level_file(tmp_path: Path) -> None:
    _make_file(tmp_path / "doc.md")
    records = _records(tmp_path, tenant_segment=0)
    assert records[0].tenant_id is None


def test_scan_tenant_none_when_segment_not_set(tmp_path: Path) -> None:
    _make_file(tmp_path / "org_a" / "doc.md")
    records = _records(tmp_path)
    assert records[0].tenant_id is None


# ---------------------------------------------------------------------------
# scan_corpus — max_files
# ---------------------------------------------------------------------------


def test_scan_respects_max_files(tmp_path: Path) -> None:
    for i in range(10):
        _make_file(tmp_path / f"doc_{i:02d}.md")
    records = _records(tmp_path, max_files=3)
    assert len(records) == 3


def test_scan_max_files_zero_returns_empty(tmp_path: Path) -> None:
    _make_file(tmp_path / "doc.md")
    records = _records(tmp_path, max_files=0)
    assert records == []


# ---------------------------------------------------------------------------
# scan_corpus — scale guard (500 files)
# ---------------------------------------------------------------------------


def test_scan_handles_many_files(tmp_path: Path) -> None:
    """Scanning 500 small files must complete without error."""
    n = 500
    for i in range(n):
        subdir = tmp_path / f"org_{i % 5}"
        subdir.mkdir(exist_ok=True)
        (subdir / f"doc_{i:04d}.md").write_text(f"content {i}", encoding="utf-8")

    records = _records(tmp_path)
    assert len(records) == n


# ---------------------------------------------------------------------------
# compute_stats
# ---------------------------------------------------------------------------


def _stats(records: list[ScanRecord]) -> StatsResult:
    return compute_stats(iter(records))


def test_stats_total_files() -> None:
    records = [
        ScanRecord("a.md", 10, ".md", None),
        ScanRecord("b.txt", 20, ".txt", None),
    ]
    assert _stats(records).total_files == 2


def test_stats_total_size_bytes() -> None:
    records = [
        ScanRecord("a.md", 100, ".md", None),
        ScanRecord("b.md", 200, ".md", None),
    ]
    assert _stats(records).total_size_bytes == 300


def test_stats_counts_extensions() -> None:
    records = [
        ScanRecord("a.md", 10, ".md", None),
        ScanRecord("b.md", 10, ".md", None),
        ScanRecord("c.txt", 10, ".txt", None),
    ]
    s = _stats(records)
    assert s.by_extension == {".md": 2, ".txt": 1}


def test_stats_counts_tenants() -> None:
    records = [
        ScanRecord("org_a/doc.md", 10, ".md", "org_a"),
        ScanRecord("org_b/doc.md", 10, ".md", "org_b"),
        ScanRecord("root.md", 10, ".md", None),
    ]
    s = _stats(records)
    assert s.by_tenant["org_a"] == 1
    assert s.by_tenant["org_b"] == 1
    assert s.by_tenant["(unknown)"] == 1


def test_stats_detects_duplicate_basenames() -> None:
    records = [
        ScanRecord("org_a/config.md", 10, ".md", "org_a"),
        ScanRecord("org_b/config.md", 10, ".md", "org_b"),
        ScanRecord("unique.md", 10, ".md", None),
    ]
    s = _stats(records)
    assert "config.md" in s.duplicate_basenames
    assert len(s.duplicate_basenames["config.md"]) == 2
    assert "unique.md" not in s.duplicate_basenames


def test_stats_detects_risky_filenames() -> None:
    records = [
        ScanRecord("creds/api_key_backup.md", 10, ".md", None),
        ScanRecord("normal_doc.md", 10, ".md", None),
        ScanRecord("passwords.txt", 5, ".txt", None),
        ScanRecord("my_token_store.yaml", 5, ".yaml", None),
    ]
    s = _stats(records)
    assert "creds/api_key_backup.md" in s.risky_filenames
    assert "passwords.txt" in s.risky_filenames
    assert "my_token_store.yaml" in s.risky_filenames
    assert "normal_doc.md" not in s.risky_filenames


def test_stats_largest_files_ordered_by_size() -> None:
    records = [
        ScanRecord("small.md", 10, ".md", None),
        ScanRecord("large.md", 1000, ".md", None),
        ScanRecord("medium.md", 100, ".md", None),
    ]
    s = _stats(records)
    assert s.largest_files[0] == ("large.md", 1000)
    assert s.largest_files[1] == ("medium.md", 100)


def test_stats_empty_corpus() -> None:
    s = _stats([])
    assert s.total_files == 0
    assert s.total_size_bytes == 0
    assert s.by_extension == {}
    assert s.by_tenant == {}
    assert s.duplicate_basenames == {}
    assert s.risky_filenames == []
    assert s.largest_files == []


# ---------------------------------------------------------------------------
# format_stats
# ---------------------------------------------------------------------------


def test_format_stats_contains_total_files() -> None:
    s = _stats([ScanRecord("a.md", 10, ".md", "org_a")])
    report = format_stats(s)
    assert "Total files" in report
    assert "1" in report


def test_format_stats_contains_extension_section() -> None:
    s = _stats([ScanRecord("a.md", 10, ".md", None)])
    assert "By extension" in format_stats(s)
    assert ".md" in format_stats(s)


def test_format_stats_shows_none_for_no_duplicates() -> None:
    s = _stats([ScanRecord("a.md", 10, ".md", None)])
    assert "None." in format_stats(s)


def test_format_stats_shows_risky_files() -> None:
    s = _stats([ScanRecord("passwords.txt", 10, ".txt", None)])
    report = format_stats(s)
    assert "passwords.txt" in report
    assert "!" in report


def test_format_stats_duplicates_truncates_at_20_basenames() -> None:
    # 25 basenames each duplicated — only first 20 should appear, rest summarised.
    records = []
    for i in range(25):
        name = f"doc_{i:02d}.md"
        records.append(ScanRecord(f"org_a/{name}", 10, ".md", "org_a"))
        records.append(ScanRecord(f"org_b/{name}", 10, ".md", "org_b"))
    s = _stats(records)
    report = format_stats(s)
    # The 20th basename (index 19) should appear; the 21st (index 20) must not.
    sorted_names = sorted(f"doc_{i:02d}.md" for i in range(25))
    assert sorted_names[19] in report
    assert sorted_names[20] not in report
    assert "and 5 more duplicate basenames." in report


def test_format_stats_duplicates_truncates_paths_at_5() -> None:
    # One basename with 8 paths — only 5 should be listed, then "... and 3 more paths."
    records = [ScanRecord(f"org_{i}/config.md", 10, ".md", f"org_{i}") for i in range(8)]
    s = _stats(records)
    report = format_stats(s)
    assert "config.md" in report
    assert "and 3 more paths." in report
    # Exactly 5 "- " entries for this basename
    path_lines = [ln for ln in report.splitlines() if ln.strip().startswith("- org_")]
    assert len(path_lines) == 5


def test_format_stats_duplicates_no_truncation_at_exactly_20() -> None:
    # 20 basenames × 2 paths each — all shown, no summary line.
    records = []
    for i in range(20):
        name = f"doc_{i:02d}.md"
        records.append(ScanRecord(f"org_a/{name}", 10, ".md", "org_a"))
        records.append(ScanRecord(f"org_b/{name}", 10, ".md", "org_b"))
    s = _stats(records)
    report = format_stats(s)
    assert "more duplicate basenames" not in report


def test_format_stats_risky_truncates_at_20() -> None:
    # 25 risky filenames — only first 20 shown.
    records = [
        ScanRecord(f"dir/passwords_{i:02d}.txt", 10, ".txt", None) for i in range(25)
    ]
    s = _stats(records)
    report = format_stats(s)
    sorted_risky = sorted(f"dir/passwords_{i:02d}.txt" for i in range(25))
    assert sorted_risky[19] in report
    assert sorted_risky[20] not in report
    assert "and 5 more risky-looking filenames." in report


def test_format_stats_risky_no_truncation_at_exactly_20() -> None:
    records = [
        ScanRecord(f"dir/passwords_{i:02d}.txt", 10, ".txt", None) for i in range(20)
    ]
    s = _stats(records)
    report = format_stats(s)
    assert "more risky-looking filenames" not in report


# ---------------------------------------------------------------------------
# iter_manifest
# ---------------------------------------------------------------------------


def test_iter_manifest_reads_jsonl(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    records = [
        ScanRecord("a.md", 10, ".md", "org_a"),
        ScanRecord("b.txt", 20, ".txt", None),
    ]
    manifest.write_text(
        "\n".join(record_to_jsonl(r) for r in records) + "\n", encoding="utf-8"
    )
    result = list(iter_manifest(manifest))
    assert len(result) == 2
    assert result[0].path == "a.md"
    assert result[1].tenant_id is None


def test_iter_manifest_skips_blank_lines(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    r = ScanRecord("a.md", 10, ".md", None)
    manifest.write_text(f"\n{record_to_jsonl(r)}\n\n", encoding="utf-8")
    result = list(iter_manifest(manifest))
    assert len(result) == 1


def test_iter_manifest_skips_malformed_lines(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    r = ScanRecord("a.md", 10, ".md", None)
    manifest.write_text(f"{{invalid json}}\n{record_to_jsonl(r)}\n", encoding="utf-8")
    result = list(iter_manifest(manifest))
    assert len(result) == 1


# ---------------------------------------------------------------------------
# CLI — corpus scan
# ---------------------------------------------------------------------------


def test_cli_corpus_scan_creates_jsonl(tmp_path: Path) -> None:
    _make_file(tmp_path / "doc.md", "hello")
    manifest = tmp_path / "manifest.jsonl"

    result = runner.invoke(app, ["corpus", "scan", str(tmp_path), "--output", str(manifest)])
    assert result.exit_code == 0, result.output

    lines = [ln for ln in manifest.read_text().splitlines() if ln.strip()]
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["extension"] == ".md"


def test_cli_corpus_scan_with_tenant(tmp_path: Path) -> None:
    _make_file(tmp_path / "org_a" / "doc.md")
    manifest = tmp_path / "manifest.jsonl"

    result = runner.invoke(
        app,
        ["corpus", "scan", str(tmp_path), "--output", str(manifest), "--tenant-from-path", "0"],
    )
    assert result.exit_code == 0

    lines = [ln for ln in manifest.read_text().splitlines() if ln.strip()]
    data = json.loads(lines[0])
    assert data["tenant_id"] == "org_a"


def test_cli_corpus_scan_with_max_files(tmp_path: Path) -> None:
    for i in range(5):
        _make_file(tmp_path / f"doc_{i}.md")
    manifest = tmp_path / "manifest.jsonl"

    result = runner.invoke(
        app,
        ["corpus", "scan", str(tmp_path), "--output", str(manifest), "--max-files", "2"],
    )
    assert result.exit_code == 0
    lines = [ln for ln in manifest.read_text().splitlines() if ln.strip()]
    assert len(lines) == 2


def test_cli_corpus_scan_with_include_ext(tmp_path: Path) -> None:
    _make_file(tmp_path / "a.md")
    _make_file(tmp_path / "b.py")
    manifest = tmp_path / "manifest.jsonl"

    result = runner.invoke(
        app,
        ["corpus", "scan", str(tmp_path), "--output", str(manifest), "--include-ext", ".py"],
    )
    assert result.exit_code == 0
    lines = [ln for ln in manifest.read_text().splitlines() if ln.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0])["extension"] == ".py"


def test_cli_corpus_scan_missing_root(tmp_path: Path) -> None:
    result = runner.invoke(app, ["corpus", "scan", str(tmp_path / "nonexistent")])
    assert result.exit_code == 2


def test_cli_corpus_scan_stdout(tmp_path: Path) -> None:
    """Without --output, JSONL goes to stdout."""
    _make_file(tmp_path / "doc.md", "hello")
    result = runner.invoke(app, ["corpus", "scan", str(tmp_path)])
    assert result.exit_code == 0
    lines = [ln for ln in result.output.splitlines() if ln.strip() and ln.startswith("{")]
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["extension"] == ".md"


# ---------------------------------------------------------------------------
# CLI — corpus stats
# ---------------------------------------------------------------------------


def test_cli_corpus_stats_prints_report(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    records = [
        ScanRecord("org_a/doc.md", 100, ".md", "org_a"),
        ScanRecord("org_b/doc.md", 200, ".md", "org_b"),
    ]
    manifest.write_text(
        "\n".join(record_to_jsonl(r) for r in records) + "\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["corpus", "stats", str(manifest)])
    assert result.exit_code == 0
    assert "Total files" in result.output
    assert "By extension" in result.output
    assert "By tenant" in result.output


def test_cli_corpus_stats_missing_manifest(tmp_path: Path) -> None:
    result = runner.invoke(app, ["corpus", "stats", str(tmp_path / "nonexistent.jsonl")])
    assert result.exit_code == 2


def test_cli_corpus_stats_detects_risky_in_output(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    r = ScanRecord("backup/passwords.txt", 50, ".txt", None)
    manifest.write_text(record_to_jsonl(r) + "\n", encoding="utf-8")

    result = runner.invoke(app, ["corpus", "stats", str(manifest)])
    assert result.exit_code == 0
    assert "passwords.txt" in result.output
