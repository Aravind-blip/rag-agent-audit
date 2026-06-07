"""Tests for the known_sources check."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rag_agent_audit.adapters.mock import MockAdapter
from rag_agent_audit.checks.known_sources import check_known_sources, load_known_sources
from rag_agent_audit.cli import app
from rag_agent_audit.config import AuditTestCase, load_suite
from rag_agent_audit.corpus import ScanRecord, record_to_jsonl
from rag_agent_audit.normalizer import NormalizedResponse
from rag_agent_audit.runner import run_suite

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resp(
    citations: list[str] | None = None,
    retrieved: list[str] | None = None,
) -> NormalizedResponse:
    return NormalizedResponse(
        answer="some answer",
        citations=citations or [],
        retrieved_sources=retrieved or [],
    )


def _known(*paths: str) -> frozenset[str]:
    return frozenset(paths)


def _write_manifest(tmp_path: Path, *paths: str) -> Path:
    manifest = tmp_path / "corpus-manifest.jsonl"
    records = [
        ScanRecord(path=p, size_bytes=10, extension=Path(p).suffix or ".md", tenant_id=None)
        for p in paths
    ]
    manifest.write_text(
        "\n".join(record_to_jsonl(r) for r in records) + "\n",
        encoding="utf-8",
    )
    return manifest


def _write_suite(tmp_path: Path, yaml_body: str) -> Path:
    config = tmp_path / "audit.yaml"
    config.write_text(textwrap.dedent(yaml_body), encoding="utf-8")
    return config


def _run(yaml_body: str, tmp_path: Path, manifest_paths: list[str] | None = None) -> list:
    """Write suite and optional manifest to tmp_path, then run."""
    if manifest_paths is not None:
        _write_manifest(tmp_path, *manifest_paths)
    config = _write_suite(tmp_path, yaml_body)
    suite = load_suite(config)
    adapter = MockAdapter(suite.response_mapping)
    return run_suite(suite, adapter, config_dir=config.parent)


# ---------------------------------------------------------------------------
# check_known_sources — skipped
# ---------------------------------------------------------------------------


def test_skipped_when_require_false() -> None:
    result = check_known_sources(_resp(["a/doc.md"]), False, _known("a/doc.md"), "manifest.jsonl")
    assert result.passed
    assert "skipped" in result.message.lower()


def test_skipped_check_name_is_known_sources() -> None:
    result = check_known_sources(_resp(), False, None, "")
    assert result.check_name == "known_sources"


# ---------------------------------------------------------------------------
# check_known_sources — no manifest configured
# ---------------------------------------------------------------------------


def test_fail_when_require_true_but_no_manifest_configured() -> None:
    result = check_known_sources(_resp(["a.md"]), True, None, "")
    assert not result.passed
    assert "known_sources_manifest" in result.message
    assert "configured on the suite" in result.message


def test_no_manifest_message_contains_suggestion() -> None:
    result = check_known_sources(_resp(["a.md"]), True, None, "")
    assert "Suggestion" in result.message


# ---------------------------------------------------------------------------
# check_known_sources — pass cases
# ---------------------------------------------------------------------------


def test_pass_when_all_citations_known() -> None:
    result = check_known_sources(
        _resp(citations=["org_a/doc.md", "org_a/faq.md"]),
        True,
        _known("org_a/doc.md", "org_a/faq.md"),
        "manifest.jsonl",
    )
    assert result.passed


def test_pass_when_all_retrieved_known() -> None:
    result = check_known_sources(
        _resp(retrieved=["org_a/doc.md"]),
        True,
        _known("org_a/doc.md"),
        "manifest.jsonl",
    )
    assert result.passed


def test_pass_when_both_citations_and_retrieved_known() -> None:
    result = check_known_sources(
        _resp(citations=["a.md"], retrieved=["b.md"]),
        True,
        _known("a.md", "b.md"),
        "manifest.jsonl",
    )
    assert result.passed


def test_pass_when_sources_empty() -> None:
    result = check_known_sources(_resp(citations=[], retrieved=[]), True, _known("a.md"), "m.jsonl")
    assert result.passed


def test_pass_message_when_sources_empty() -> None:
    result = check_known_sources(_resp(), True, _known("a.md"), "m.jsonl")
    assert "No citations" in result.message


def test_pass_message_when_all_known() -> None:
    result = check_known_sources(_resp(citations=["a.md"]), True, _known("a.md"), "m.jsonl")
    assert "All sources exist" in result.message


# ---------------------------------------------------------------------------
# check_known_sources — fail cases
# ---------------------------------------------------------------------------


def test_fail_when_citation_unknown() -> None:
    result = check_known_sources(
        _resp(citations=["unknown.md"]),
        True,
        _known("known.md"),
        "manifest.jsonl",
    )
    assert not result.passed
    assert "unknown.md" in result.message
    assert "citation" in result.message.lower()


def test_fail_when_retrieved_unknown() -> None:
    result = check_known_sources(
        _resp(retrieved=["shadow/private.md"]),
        True,
        _known("org_a/doc.md"),
        "manifest.jsonl",
    )
    assert not result.passed
    assert "shadow/private.md" in result.message
    assert "retrieved" in result.message.lower()


def test_fail_when_both_citation_and_retrieved_unknown() -> None:
    result = check_known_sources(
        _resp(citations=["cit_unknown.md"], retrieved=["ret_unknown.md"]),
        True,
        _known("other.md"),
        "manifest.jsonl",
    )
    assert not result.passed
    assert "cit_unknown.md" in result.message
    assert "ret_unknown.md" in result.message


def test_fail_when_one_citation_unknown_one_known() -> None:
    # Use names with no shared substrings to avoid false positives.
    result = check_known_sources(
        _resp(citations=["org_a/policy.md", "shadow/private.md"]),
        True,
        _known("org_a/policy.md"),
        "manifest.jsonl",
    )
    assert not result.passed
    assert "shadow/private.md" in result.message
    # The violation section lists only the unknown source.
    unknown_section = result.message.split("Actual citations")[0]
    assert "  - shadow/private.md" in unknown_section
    assert "  - org_a/policy.md" not in unknown_section


# ---------------------------------------------------------------------------
# check_known_sources — failure message format
# ---------------------------------------------------------------------------


def test_failure_message_starts_with_check_failed() -> None:
    result = check_known_sources(
        _resp(citations=["bad.md"]), True, _known("good.md"), "corpus-manifest.jsonl"
    )
    assert result.message.startswith("Check failed: known_sources")


def test_failure_message_contains_manifest_label() -> None:
    result = check_known_sources(
        _resp(citations=["bad.md"]), True, _known("good.md"), "corpus-manifest.jsonl"
    )
    assert "corpus-manifest.jsonl" in result.message


def test_failure_message_contains_actual_citations() -> None:
    result = check_known_sources(
        _resp(citations=["bad.md"]), True, _known("good.md"), "m.jsonl"
    )
    assert "Actual citations" in result.message
    assert "bad.md" in result.message


def test_failure_message_contains_actual_retrieved() -> None:
    result = check_known_sources(
        _resp(retrieved=["bad.md"]), True, _known("good.md"), "m.jsonl"
    )
    assert "Actual retrieved sources" in result.message


def test_failure_message_contains_suggestion() -> None:
    result = check_known_sources(
        _resp(citations=["bad.md"]), True, _known("good.md"), "m.jsonl"
    )
    assert "Suggestion" in result.message


def test_failure_message_contains_known_source_manifest_section() -> None:
    result = check_known_sources(
        _resp(citations=["bad.md"]), True, _known("good.md"), "my-manifest.jsonl"
    )
    assert "Known source manifest" in result.message
    assert "my-manifest.jsonl" in result.message


# ---------------------------------------------------------------------------
# check_known_sources — exact matching
# ---------------------------------------------------------------------------


def test_exact_match_only_case_sensitive() -> None:
    """'Refund.md' != 'refund.md' — the check is case-sensitive."""
    result = check_known_sources(
        _resp(citations=["Refund.md"]),
        True,
        _known("refund.md"),
        "m.jsonl",
    )
    assert not result.passed


def test_exact_match_no_prefix_stripping() -> None:
    """'org_a/doc.md' != 'doc.md'."""
    result = check_known_sources(
        _resp(citations=["doc.md"]),
        True,
        _known("org_a/doc.md"),
        "m.jsonl",
    )
    assert not result.passed


def test_exact_match_path_must_match_fully() -> None:
    result = check_known_sources(
        _resp(citations=["org_a/doc.md"]),
        True,
        _known("org_a/doc.md"),
        "m.jsonl",
    )
    assert result.passed


# ---------------------------------------------------------------------------
# check_known_sources — deduplication
# ---------------------------------------------------------------------------


def test_deduplicates_unknown_citations() -> None:
    """The same unknown source repeated multiple times appears once in diagnostic."""
    result = check_known_sources(
        _resp(citations=["bad.md", "bad.md", "bad.md"]),
        True,
        _known("good.md"),
        "m.jsonl",
    )
    assert not result.passed
    # Count occurrences of the unknown path in the unknown section only
    unknown_section = result.message.split("Actual citations")[0]
    assert unknown_section.count("bad.md") == 1


def test_deduplicates_unknown_retrieved() -> None:
    result = check_known_sources(
        _resp(retrieved=["shadow.md", "shadow.md"]),
        True,
        _known("good.md"),
        "m.jsonl",
    )
    unknown_section = result.message.split("Actual retrieved")[0]
    assert unknown_section.count("shadow.md") == 1


# ---------------------------------------------------------------------------
# load_known_sources
# ---------------------------------------------------------------------------


def test_load_known_sources_returns_frozenset_of_paths(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path, "org_a/doc.md", "org_b/faq.txt")
    result = load_known_sources(manifest)
    assert isinstance(result, frozenset)
    assert "org_a/doc.md" in result
    assert "org_b/faq.txt" in result


def test_load_known_sources_empty_file(tmp_path: Path) -> None:
    manifest = tmp_path / "empty.jsonl"
    manifest.write_text("", encoding="utf-8")
    result = load_known_sources(manifest)
    assert result == frozenset()


def test_load_known_sources_raises_on_malformed_json(tmp_path: Path) -> None:
    manifest = tmp_path / "corpus-manifest.jsonl"
    good = record_to_jsonl(
        ScanRecord(path="good/doc.md", size_bytes=10, extension=".md", tenant_id=None)
    )
    manifest.write_text(good + "\nNOT JSON\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        load_known_sources(manifest)


def test_load_known_sources_error_includes_manifest_name_for_bad_json(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "corpus-manifest.jsonl"
    manifest.write_text("NOT JSON\n", encoding="utf-8")
    with pytest.raises(ValueError, match="corpus-manifest.jsonl"):
        load_known_sources(manifest)


def test_load_known_sources_error_includes_line_number_for_bad_json(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "corpus-manifest.jsonl"
    good = record_to_jsonl(
        ScanRecord(path="a.md", size_bytes=10, extension=".md", tenant_id=None)
    )
    # Bad JSON is on line 3 (after two good lines).
    manifest.write_text(good + "\n" + good + "\nBAD JSON\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 3"):
        load_known_sources(manifest)


def test_load_known_sources_raises_on_missing_path_field(tmp_path: Path) -> None:
    import json

    manifest = tmp_path / "corpus-manifest.jsonl"
    manifest.write_text(
        json.dumps({"size_bytes": 10, "extension": ".md"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing required field 'path'"):
        load_known_sources(manifest)


def test_load_known_sources_missing_path_includes_manifest_name(tmp_path: Path) -> None:
    import json

    manifest = tmp_path / "corpus-manifest.jsonl"
    manifest.write_text(json.dumps({"extension": ".md"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="corpus-manifest.jsonl"):
        load_known_sources(manifest)


def test_load_known_sources_missing_path_includes_line_number(tmp_path: Path) -> None:
    import json

    good = record_to_jsonl(
        ScanRecord(path="a.md", size_bytes=10, extension=".md", tenant_id=None)
    )
    manifest = tmp_path / "corpus-manifest.jsonl"
    # Missing-path record is on line 2.
    manifest.write_text(
        good + "\n" + json.dumps({"extension": ".md"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="line 2"):
        load_known_sources(manifest)


def test_load_known_sources_raises_on_empty_path_string(tmp_path: Path) -> None:
    import json

    manifest = tmp_path / "corpus-manifest.jsonl"
    manifest.write_text(json.dumps({"path": ""}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid 'path'"):
        load_known_sources(manifest)


def test_load_known_sources_raises_on_non_string_path(tmp_path: Path) -> None:
    import json

    manifest = tmp_path / "corpus-manifest.jsonl"
    manifest.write_text(json.dumps({"path": 42}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid 'path'"):
        load_known_sources(manifest)


def test_load_known_sources_invalid_path_includes_manifest_name(tmp_path: Path) -> None:
    import json

    manifest = tmp_path / "corpus-manifest.jsonl"
    manifest.write_text(json.dumps({"path": ""}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="corpus-manifest.jsonl"):
        load_known_sources(manifest)


def test_load_known_sources_invalid_path_includes_line_number(tmp_path: Path) -> None:
    import json

    good = record_to_jsonl(
        ScanRecord(path="a.md", size_bytes=10, extension=".md", tenant_id=None)
    )
    manifest = tmp_path / "corpus-manifest.jsonl"
    manifest.write_text(good + "\n" + json.dumps({"path": ""}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 2"):
        load_known_sources(manifest)


def test_load_known_sources_blank_lines_ignored_no_error(tmp_path: Path) -> None:
    """Blank lines between valid records must not raise."""
    good = record_to_jsonl(
        ScanRecord(path="a.md", size_bytes=10, extension=".md", tenant_id=None)
    )
    manifest = tmp_path / "corpus-manifest.jsonl"
    manifest.write_text("\n" + good + "\n\n", encoding="utf-8")
    result = load_known_sources(manifest)
    assert result == frozenset({"a.md"})


# ---------------------------------------------------------------------------
# config schema
# ---------------------------------------------------------------------------


def test_config_accepts_known_sources_manifest(tmp_path: Path) -> None:
    config = _write_suite(
        tmp_path,
        """\
        suite: test-suite
        mode: mock
        known_sources_manifest: corpus-manifest.jsonl
        tests:
          - name: t1
            question: q
            mock_response:
              answer: ok
        """,
    )
    suite = load_suite(config)
    assert suite.known_sources_manifest == "corpus-manifest.jsonl"


def test_config_accepts_require_known_sources(tmp_path: Path) -> None:
    config = _write_suite(
        tmp_path,
        """\
        suite: test-suite
        mode: mock
        tests:
          - name: t1
            question: q
            mock_response:
              answer: ok
            require_known_sources: true
        """,
    )
    suite = load_suite(config)
    assert suite.tests[0].require_known_sources is True


def test_config_defaults_known_sources_manifest_to_none(tmp_path: Path) -> None:
    config = _write_suite(
        tmp_path,
        """\
        suite: s
        mode: mock
        tests:
          - name: t1
            question: q
            mock_response:
              answer: ok
        """,
    )
    suite = load_suite(config)
    assert suite.known_sources_manifest is None


def test_config_defaults_require_known_sources_to_false(tmp_path: Path) -> None:
    tc = AuditTestCase(name="t1", question="q")
    assert tc.require_known_sources is False


# ---------------------------------------------------------------------------
# run_suite integration — manifest path resolution
# ---------------------------------------------------------------------------


def test_manifest_path_resolves_relative_to_config(tmp_path: Path) -> None:
    """A relative manifest path in the config resolves next to the YAML file."""
    _write_manifest(tmp_path, "org_a/doc.md")
    results = _run(
        """\
        suite: s
        mode: mock
        known_sources_manifest: corpus-manifest.jsonl
        tests:
          - name: known-source-test
            question: q
            mock_response:
              answer: ok
              citations:
                - source: org_a/doc.md
            require_known_sources: true
        """,
        tmp_path,
    )
    assert results[0].passed


def test_manifest_path_absolute(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path, "org_a/doc.md")
    results = _run(
        f"""\
        suite: s
        mode: mock
        known_sources_manifest: {manifest}
        tests:
          - name: absolute-path-test
            question: q
            mock_response:
              answer: ok
              citations:
                - source: org_a/doc.md
            require_known_sources: true
        """,
        tmp_path,
    )
    assert results[0].passed


def test_missing_manifest_raises_file_not_found(tmp_path: Path) -> None:
    config = _write_suite(
        tmp_path,
        """\
        suite: s
        mode: mock
        known_sources_manifest: nonexistent.jsonl
        tests:
          - name: t1
            question: q
            mock_response:
              answer: ok
            require_known_sources: true
        """,
    )
    suite = load_suite(config)
    adapter = MockAdapter(suite.response_mapping)
    with pytest.raises(FileNotFoundError, match="nonexistent.jsonl"):
        run_suite(suite, adapter, config_dir=config.parent)


def test_malformed_manifest_raises_value_error(tmp_path: Path) -> None:

    manifest = tmp_path / "corpus-manifest.jsonl"
    manifest.write_text("NOT JSON\n", encoding="utf-8")
    config = _write_suite(
        tmp_path,
        """\
        suite: s
        mode: mock
        known_sources_manifest: corpus-manifest.jsonl
        tests:
          - name: t1
            question: q
            mock_response:
              answer: ok
            require_known_sources: true
        """,
    )
    suite = load_suite(config)
    adapter = MockAdapter(suite.response_mapping)
    with pytest.raises(ValueError, match="invalid JSON"):
        run_suite(suite, adapter, config_dir=config.parent)


def test_manifest_missing_path_raises_value_error(tmp_path: Path) -> None:
    import json

    manifest = tmp_path / "corpus-manifest.jsonl"
    manifest.write_text(json.dumps({"extension": ".md"}) + "\n", encoding="utf-8")
    config = _write_suite(
        tmp_path,
        """\
        suite: s
        mode: mock
        known_sources_manifest: corpus-manifest.jsonl
        tests:
          - name: t1
            question: q
            mock_response:
              answer: ok
            require_known_sources: true
        """,
    )
    suite = load_suite(config)
    adapter = MockAdapter(suite.response_mapping)
    with pytest.raises(ValueError, match="missing required field 'path'"):
        run_suite(suite, adapter, config_dir=config.parent)


def test_run_suite_known_sources_pass(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "org_a/refund_policy.md")
    results = _run(
        """\
        suite: s
        mode: mock
        known_sources_manifest: corpus-manifest.jsonl
        tests:
          - name: known-citation
            question: q
            mock_response:
              answer: ok
              citations:
                - source: org_a/refund_policy.md
            require_known_sources: true
        """,
        tmp_path,
    )
    ks = next(cr for cr in results[0].check_results if cr.check_name == "known_sources")
    assert ks.passed


def test_run_suite_known_sources_fail_on_unknown(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "org_a/refund_policy.md")
    results = _run(
        """\
        suite: s
        mode: mock
        known_sources_manifest: corpus-manifest.jsonl
        tests:
          - name: unknown-citation
            question: q
            mock_response:
              answer: ok
              citations:
                - source: shadow/unknown.md
            require_known_sources: true
        """,
        tmp_path,
    )
    ks = next(cr for cr in results[0].check_results if cr.check_name == "known_sources")
    assert not ks.passed
    assert "shadow/unknown.md" in ks.message


def test_run_suite_no_manifest_require_true_fails(tmp_path: Path) -> None:
    """require_known_sources=true with no suite-level manifest fails the check."""
    results = _run(
        """\
        suite: s
        mode: mock
        tests:
          - name: no-manifest
            question: q
            mock_response:
              answer: ok
              citations:
                - source: any.md
            require_known_sources: true
        """,
        tmp_path,
    )
    ks = next(cr for cr in results[0].check_results if cr.check_name == "known_sources")
    assert not ks.passed


def test_run_suite_require_false_skips_even_with_manifest(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "org_a/doc.md")
    results = _run(
        """\
        suite: s
        mode: mock
        known_sources_manifest: corpus-manifest.jsonl
        tests:
          - name: skip-check
            question: q
            mock_response:
              answer: ok
              citations:
                - source: completely_unknown.md
        """,
        tmp_path,
    )
    ks = next(cr for cr in results[0].check_results if cr.check_name == "known_sources")
    assert ks.passed  # skipped because require_known_sources defaults to False


def test_run_suite_manifest_loaded_once_for_all_tests(tmp_path: Path) -> None:
    """All tests in the suite share the same loaded manifest set."""
    _write_manifest(tmp_path, "a.md", "b.md")
    results = _run(
        """\
        suite: s
        mode: mock
        known_sources_manifest: corpus-manifest.jsonl
        tests:
          - name: test-a
            question: q
            mock_response:
              answer: ok
              citations:
                - source: a.md
            require_known_sources: true
          - name: test-b
            question: q
            mock_response:
              answer: ok
              citations:
                - source: b.md
            require_known_sources: true
        """,
        tmp_path,
    )
    for r in results:
        ks = next(cr for cr in r.check_results if cr.check_name == "known_sources")
        assert ks.passed


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def test_cli_run_passes_with_known_sources(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "org_a/doc.md")
    config = _write_suite(
        tmp_path,
        """\
        suite: s
        mode: mock
        known_sources_manifest: corpus-manifest.jsonl
        tests:
          - name: known-citation
            question: q
            mock_response:
              answer: ok
              citations:
                - source: org_a/doc.md
            require_known_sources: true
        """,
    )
    result = runner.invoke(app, ["run", str(config)])
    assert result.exit_code == 0


def test_cli_run_exits_1_on_unknown_source(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "org_a/doc.md")
    config = _write_suite(
        tmp_path,
        """\
        suite: s
        mode: mock
        known_sources_manifest: corpus-manifest.jsonl
        tests:
          - name: unknown-citation
            question: q
            mock_response:
              answer: ok
              citations:
                - source: shadow/unknown.md
            require_known_sources: true
        """,
    )
    result = runner.invoke(app, ["run", str(config)])
    assert result.exit_code == 1


def test_cli_run_exits_2_on_missing_manifest(tmp_path: Path) -> None:
    config = _write_suite(
        tmp_path,
        """\
        suite: s
        mode: mock
        known_sources_manifest: nonexistent.jsonl
        tests:
          - name: t1
            question: q
            mock_response:
              answer: ok
            require_known_sources: true
        """,
    )
    result = runner.invoke(app, ["run", str(config)])
    assert result.exit_code == 2


def test_cli_run_exits_2_on_malformed_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "corpus-manifest.jsonl"
    manifest.write_text("NOT JSON\n", encoding="utf-8")
    config = _write_suite(
        tmp_path,
        """\
        suite: s
        mode: mock
        known_sources_manifest: corpus-manifest.jsonl
        tests:
          - name: t1
            question: q
            mock_response:
              answer: ok
            require_known_sources: true
        """,
    )
    result = runner.invoke(app, ["run", str(config)])
    assert result.exit_code == 2


def test_cli_run_exits_2_on_manifest_missing_path_field(tmp_path: Path) -> None:
    import json

    manifest = tmp_path / "corpus-manifest.jsonl"
    manifest.write_text(json.dumps({"size_bytes": 10}) + "\n", encoding="utf-8")
    config = _write_suite(
        tmp_path,
        """\
        suite: s
        mode: mock
        known_sources_manifest: corpus-manifest.jsonl
        tests:
          - name: t1
            question: q
            mock_response:
              answer: ok
            require_known_sources: true
        """,
    )
    result = runner.invoke(app, ["run", str(config)])
    assert result.exit_code == 2


def test_cli_validate_accepts_known_sources_manifest(tmp_path: Path) -> None:
    """validate does not check that the manifest file exists — only run does."""
    config = _write_suite(
        tmp_path,
        """\
        suite: s
        mode: mock
        known_sources_manifest: does-not-exist-yet.jsonl
        tests:
          - name: t1
            question: q
            mock_response:
              answer: ok
        """,
    )
    result = runner.invoke(app, ["validate", str(config)])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Existing examples still validate and run
# ---------------------------------------------------------------------------


_EXAMPLES = Path(__file__).parent.parent / "examples"


def test_basic_example_still_runs() -> None:
    result = runner.invoke(app, ["run", str(_EXAMPLES / "basic" / "audit.yaml")])
    assert result.exit_code == 0


def test_multi_tenant_example_still_validates() -> None:
    result = runner.invoke(
        app, ["validate", str(_EXAMPLES / "multi-tenant-rag" / "audit.yaml")]
    )
    assert result.exit_code == 0


def test_prompt_injection_example_still_validates() -> None:
    result = runner.invoke(
        app, ["validate", str(_EXAMPLES / "prompt-injection" / "audit.yaml")]
    )
    assert result.exit_code == 0
