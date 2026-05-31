"""Tests for the corpus generate-tests command and its core logic."""

from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from rag_agent_audit.cli import app
from rag_agent_audit.config import load_suite
from rag_agent_audit.corpus import ScanRecord, record_to_jsonl
from rag_agent_audit.corpus_generate import (
    _slugify,
    _unique_name,
    generate_tests,
    generate_tests_yaml,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rec(
    path: str,
    tenant_id: str | None = None,
    size_bytes: int = 100,
) -> ScanRecord:
    ext = Path(path).suffix.lower() or ".md"
    return ScanRecord(path=path, size_bytes=size_bytes, extension=ext, tenant_id=tenant_id)


def _records(*paths: str, tenant_id: str | None = None) -> list[ScanRecord]:
    return [_rec(p, tenant_id=tenant_id) for p in paths]


def _write_manifest(tmp_path: Path, records: list[ScanRecord]) -> Path:
    manifest = tmp_path / "manifest.jsonl"
    lines = [record_to_jsonl(r) for r in records]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


# ---------------------------------------------------------------------------
# _slugify unit tests
# ---------------------------------------------------------------------------


def test_slugify_lowercases_and_replaces_special_chars() -> None:
    assert _slugify("org_a/Refund Policy.md") == "org-a-refund-policy-md"


def test_slugify_strips_leading_trailing_hyphens() -> None:
    result = _slugify("---hello---")
    assert result == "hello"


def test_slugify_handles_dots() -> None:
    assert _slugify("file.md") == "file-md"


def test_slugify_truncates_at_max_len() -> None:
    long = "a" * 100
    result = _slugify(long, max_len=20)
    assert len(result) <= 20


def test_slugify_result_matches_config_regex() -> None:
    import re

    for text in ["org_a/doc.md", "Secret Token Policy", "  123-abc ", "tenant-b"]:
        slug = _slugify(text)
        assert re.match(r"^[a-z0-9][a-z0-9\-]*$", slug), f"bad slug: {slug!r}"


# ---------------------------------------------------------------------------
# _unique_name unit tests
# ---------------------------------------------------------------------------


def test_unique_name_returns_base_when_unused() -> None:
    used: set[str] = set()
    assert _unique_name("source-coverage-foo", used) == "source-coverage-foo"


def test_unique_name_appends_suffix_on_collision() -> None:
    used: set[str] = {"source-coverage-foo"}
    result = _unique_name("source-coverage-foo", used)
    assert result != "source-coverage-foo"
    assert result.endswith("-2")


def test_unique_name_increments_suffix_until_free() -> None:
    used: set[str] = {"base", "base-2", "base-3"}
    result = _unique_name("base", used)
    assert result == "base-4"


# ---------------------------------------------------------------------------
# generate_tests — structure and counts
# ---------------------------------------------------------------------------


def test_generate_tests_produces_source_coverage_tests() -> None:
    recs = _records("org_a/refund_policy.md", "org_a/handbook.md")
    result = generate_tests(iter(recs))
    assert result.source_test_count == 2
    names = [t["name"] for t in result.suite_dict["tests"]]
    assert any(n.startswith("source-coverage-") for n in names)


def test_generate_tests_source_coverage_has_expected_sources() -> None:
    recs = [_rec("org_a/refund_policy.md")]
    result = generate_tests(iter(recs))
    source_tests = [
        t for t in result.suite_dict["tests"] if t["name"].startswith("source-coverage-")
    ]
    assert source_tests[0]["expected_sources"] == ["org_a/refund_policy.md"]


def test_generate_tests_source_coverage_question_contains_path() -> None:
    recs = [_rec("org_a/refund_policy.md")]
    result = generate_tests(iter(recs))
    source_tests = [
        t for t in result.suite_dict["tests"] if t["name"].startswith("source-coverage-")
    ]
    assert "org_a/refund_policy.md" in source_tests[0]["question"]


def test_generate_tests_risky_file_detected() -> None:
    recs = [_rec("org_b/secret_token_policy.md")]
    result = generate_tests(iter(recs))
    assert result.risky_test_count == 1
    risky = [t for t in result.suite_dict["tests"] if t["name"].startswith("risky-source-")]
    assert len(risky) == 1


def test_generate_tests_risky_file_has_must_not_contain() -> None:
    recs = [_rec("org_b/secret_token_policy.md")]
    result = generate_tests(iter(recs))
    risky = [t for t in result.suite_dict["tests"] if t["name"].startswith("risky-source-")]
    mnc = risky[0]["must_not_contain"]
    assert "password=" in mnc
    assert "token=" in mnc
    assert "api_key=" in mnc
    assert "secret=" in mnc


def test_generate_tests_risky_file_has_should_fallback_true() -> None:
    recs = [_rec("config/api_key_settings.yaml")]
    result = generate_tests(iter(recs))
    risky = [t for t in result.suite_dict["tests"] if t["name"].startswith("risky-source-")]
    assert risky[0]["should_fallback"] is True


def test_generate_tests_non_risky_file_not_in_risky_tests() -> None:
    recs = _records("org_a/refund_policy.md", "org_a/faq.md")
    result = generate_tests(iter(recs))
    assert result.risky_test_count == 0


def test_generate_tests_tenant_prefix_tests_created_when_tenant_ids_present() -> None:
    recs = [_rec("org_a/doc.md", tenant_id="org_a"), _rec("org_b/doc.md", tenant_id="org_b")]
    result = generate_tests(iter(recs))
    assert result.tenant_prefix_test_count == 2
    tenant = [t for t in result.suite_dict["tests"] if t["name"].startswith("tenant-prefix-")]
    assert len(tenant) == 2


def test_generate_tests_tenant_prefix_has_allowed_source_prefixes() -> None:
    recs = [_rec("org_a/doc.md", tenant_id="org_a")]
    result = generate_tests(iter(recs))
    tenant = [t for t in result.suite_dict["tests"] if t["name"].startswith("tenant-prefix-")]
    assert tenant[0]["allowed_source_prefixes"] == ["org_a/"]


def test_generate_tests_no_tenant_tests_when_no_tenant_ids() -> None:
    recs = [_rec("doc.md")]
    result = generate_tests(iter(recs))
    assert result.tenant_prefix_test_count == 0
    assert not any(t["name"].startswith("tenant-prefix-") for t in result.suite_dict["tests"])


def test_generate_tests_duplicate_tenant_ids_produce_one_test_each() -> None:
    recs = [
        _rec("org_a/a.md", tenant_id="org_a"),
        _rec("org_a/b.md", tenant_id="org_a"),  # same tenant
    ]
    result = generate_tests(iter(recs))
    assert result.tenant_prefix_test_count == 1


def test_generate_tests_total_count_is_sum_of_categories() -> None:
    recs = [
        _rec("org_a/doc.md", tenant_id="org_a"),
        _rec("org_b/secret_key.md", tenant_id="org_b"),
    ]
    result = generate_tests(iter(recs))
    # 2 source + 1 risky + 2 tenant = 5
    assert result.total_test_count == result.source_test_count + result.risky_test_count + result.tenant_prefix_test_count  # noqa: E501


# ---------------------------------------------------------------------------
# generate_tests — max limits
# ---------------------------------------------------------------------------


def test_generate_tests_respects_max_source_tests() -> None:
    recs = [_rec(f"org_a/doc_{i}.md") for i in range(10)]
    result = generate_tests(iter(recs), max_source_tests=3)
    assert result.source_test_count == 3


def test_generate_tests_respects_max_risky_tests() -> None:
    recs = [_rec(f"org_a/secret_{i}.md") for i in range(10)]
    result = generate_tests(iter(recs), max_risky_tests=2)
    assert result.risky_test_count == 2


def test_generate_tests_max_source_tests_zero_skips_source_tests() -> None:
    recs = [_rec("org_a/doc.md")]
    result = generate_tests(iter(recs), max_source_tests=0)
    assert result.source_test_count == 0
    assert not any(t["name"].startswith("source-coverage-") for t in result.suite_dict["tests"])


def test_generate_tests_max_risky_tests_zero_skips_risky_tests() -> None:
    recs = [_rec("org_a/secret_key.md")]
    result = generate_tests(iter(recs), max_risky_tests=0)
    assert result.risky_test_count == 0


def test_generate_tests_does_not_exceed_max_source_tests_for_large_manifest() -> None:
    recs = [_rec(f"org/file_{i}.md") for i in range(100)]
    result = generate_tests(iter(recs), max_source_tests=20)
    assert result.source_test_count == 20


def test_generate_tests_does_not_exceed_max_risky_tests_for_large_manifest() -> None:
    recs = [_rec(f"org/token_{i}.md") for i in range(50)]
    result = generate_tests(iter(recs), max_risky_tests=5)
    assert result.risky_test_count == 5


# ---------------------------------------------------------------------------
# generate_tests — deterministic ordering
# ---------------------------------------------------------------------------


def test_generate_tests_source_order_is_manifest_order() -> None:
    recs = [_rec("b/doc.md"), _rec("a/doc.md"), _rec("c/doc.md")]
    result = generate_tests(iter(recs))
    source_tests = [
        t for t in result.suite_dict["tests"] if t["name"].startswith("source-coverage-")
    ]
    paths = [t["expected_sources"][0] for t in source_tests]
    assert paths == ["b/doc.md", "a/doc.md", "c/doc.md"]


def test_generate_tests_tenant_order_is_alphabetical() -> None:
    recs = [
        _rec("c/doc.md", tenant_id="zzz"),
        _rec("a/doc.md", tenant_id="aaa"),
        _rec("b/doc.md", tenant_id="mmm"),
    ]
    result = generate_tests(iter(recs))
    tenant_tests = [
        t for t in result.suite_dict["tests"] if t["name"].startswith("tenant-prefix-")
    ]
    prefixes = [t["allowed_source_prefixes"][0] for t in tenant_tests]
    assert prefixes == ["aaa/", "mmm/", "zzz/"]


def test_generate_tests_is_deterministic_for_same_input() -> None:
    recs = [_rec(f"org/file_{i}.md", tenant_id="t1") for i in range(10)]
    result1 = generate_tests(iter(recs))
    result2 = generate_tests(iter(recs))
    names1 = [t["name"] for t in result1.suite_dict["tests"]]
    names2 = [t["name"] for t in result2.suite_dict["tests"]]
    assert names1 == names2


# ---------------------------------------------------------------------------
# generate_tests — ordering within output: source → risky → tenant
# ---------------------------------------------------------------------------


def test_generate_tests_ordering_source_before_risky_before_tenant() -> None:
    recs = [
        _rec("org_a/doc.md", tenant_id="org_a"),
        _rec("org_a/api_key_policy.md", tenant_id="org_a"),
    ]
    result = generate_tests(iter(recs))
    tests = result.suite_dict["tests"]
    names = [t["name"] for t in tests]
    source_indices = [i for i, n in enumerate(names) if n.startswith("source-coverage-")]
    risky_indices = [i for i, n in enumerate(names) if n.startswith("risky-source-")]
    tenant_indices = [i for i, n in enumerate(names) if n.startswith("tenant-prefix-")]
    assert source_indices
    assert risky_indices
    assert tenant_indices
    assert max(source_indices) < min(risky_indices)
    assert max(risky_indices) < min(tenant_indices)


# ---------------------------------------------------------------------------
# generate_tests — name collision deduplication
# ---------------------------------------------------------------------------


def test_generate_tests_deduplicates_colliding_slugs() -> None:
    # Two different paths that produce the same slug: "a/b.md" and "a-b.md"
    recs = [_rec("a/b.md"), _rec("a-b.md")]
    result = generate_tests(iter(recs))
    names = [t["name"] for t in result.suite_dict["tests"]]
    assert len(names) == len(set(names)), "Duplicate test names found"


# ---------------------------------------------------------------------------
# generate_tests — suite structure
# ---------------------------------------------------------------------------


def test_generate_tests_suite_name_embedded() -> None:
    recs = [_rec("doc.md")]
    result = generate_tests(iter(recs), suite_name="my-custom-suite")
    assert result.suite_dict["suite"] == "my-custom-suite"


def test_generate_tests_endpoint_embedded() -> None:
    recs = [_rec("doc.md")]
    result = generate_tests(iter(recs), endpoint="http://example.com/api")
    assert result.suite_dict["endpoint"] == "http://example.com/api"


def test_generate_tests_mode_is_http() -> None:
    recs = [_rec("doc.md")]
    result = generate_tests(iter(recs))
    assert result.suite_dict["mode"] == "http"


def test_generate_tests_has_response_mapping() -> None:
    recs = [_rec("doc.md")]
    result = generate_tests(iter(recs))
    rm = result.suite_dict["response_mapping"]
    assert "answer" in rm
    assert "citations" in rm
    assert "retrieved_sources" in rm
    assert "tool_calls" in rm


def test_generate_tests_has_fallback_patterns() -> None:
    recs = [_rec("doc.md")]
    result = generate_tests(iter(recs))
    patterns = result.suite_dict["fallback_patterns"]
    assert isinstance(patterns, list)
    assert len(patterns) > 0
    assert any("could not find" in p for p in patterns)


def test_generate_tests_tenant_prefix_format_applied() -> None:
    recs = [_rec("org_a/doc.md", tenant_id="org_a")]
    result = generate_tests(iter(recs), tenant_prefix_format="tenants/{tenant_id}/")
    tenant = [t for t in result.suite_dict["tests"] if t["name"].startswith("tenant-prefix-")]
    assert tenant[0]["allowed_source_prefixes"] == ["tenants/org_a/"]


# ---------------------------------------------------------------------------
# generate_tests — empty manifest
# ---------------------------------------------------------------------------


def test_generate_tests_empty_manifest_returns_zero_tests() -> None:
    result = generate_tests(iter([]))
    assert result.total_test_count == 0
    assert result.suite_dict["tests"] == []


# ---------------------------------------------------------------------------
# generate_tests_yaml — YAML output and round-trip validation
# ---------------------------------------------------------------------------


def test_generate_tests_yaml_output_is_valid_yaml() -> None:
    recs = [_rec("org_a/doc.md", tenant_id="org_a")]
    yaml_str, _ = generate_tests_yaml(iter(recs))
    parsed = yaml.safe_load(yaml_str)
    assert isinstance(parsed, dict)
    assert parsed["suite"] == "generated-corpus-audit"


def test_generate_tests_yaml_has_header_comment() -> None:
    recs = [_rec("doc.md")]
    yaml_str, _ = generate_tests_yaml(iter(recs))
    assert yaml_str.startswith("#")
    assert "generate-tests" in yaml_str


def test_generate_tests_yaml_validates_through_load_suite(tmp_path: Path) -> None:
    recs = [
        _rec("org_a/refund_policy.md", tenant_id="org_a"),
        _rec("org_b/secret_key.yaml", tenant_id="org_b"),
    ]
    yaml_str, _ = generate_tests_yaml(iter(recs))
    config_path = tmp_path / "generated.yaml"
    config_path.write_text(yaml_str, encoding="utf-8")
    suite = load_suite(config_path)
    assert suite.suite == "generated-corpus-audit"
    assert suite.mode == "http"
    assert len(suite.tests) > 0


def test_generate_tests_yaml_all_test_names_valid_slugs(tmp_path: Path) -> None:
    import re

    recs = [
        _rec("org_a/refund_policy.md", tenant_id="org_a"),
        _rec("org_b/secret_credentials.md", tenant_id="org_b"),
        _rec("plain/doc.md"),
    ]
    yaml_str, _ = generate_tests_yaml(iter(recs))
    parsed = yaml.safe_load(yaml_str)
    for test in parsed["tests"]:
        name = test["name"]
        assert re.match(r"^[a-z0-9][a-z0-9\-]*$", name), f"Invalid test name: {name!r}"


# ---------------------------------------------------------------------------
# CLI — corpus generate-tests
# ---------------------------------------------------------------------------


def test_cli_generate_tests_to_stdout(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path, [_rec("org_a/doc.md")])
    result = runner.invoke(app, ["corpus", "generate-tests", str(manifest)])
    assert result.exit_code == 0
    parsed = yaml.safe_load(result.output)
    assert parsed["suite"] == "generated-corpus-audit"


def test_cli_generate_tests_to_file(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path, [_rec("org_a/doc.md", tenant_id="org_a")])
    output = tmp_path / "generated.yaml"
    result = runner.invoke(
        app,
        ["corpus", "generate-tests", str(manifest), "--output", str(output)],
    )
    assert result.exit_code == 0
    assert output.exists()
    suite = load_suite(output)
    assert len(suite.tests) > 0


def test_cli_generate_tests_custom_suite_name(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path, [_rec("doc.md")])
    result = runner.invoke(
        app,
        ["corpus", "generate-tests", str(manifest), "--suite", "my-custom-suite"],
    )
    assert result.exit_code == 0
    parsed = yaml.safe_load(result.output)
    assert parsed["suite"] == "my-custom-suite"


def test_cli_generate_tests_custom_endpoint(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path, [_rec("doc.md")])
    result = runner.invoke(
        app,
        ["corpus", "generate-tests", str(manifest), "--endpoint", "http://my-app:9000/chat"],
    )
    assert result.exit_code == 0
    parsed = yaml.safe_load(result.output)
    assert parsed["endpoint"] == "http://my-app:9000/chat"


def test_cli_generate_tests_respects_max_source_tests(tmp_path: Path) -> None:
    recs = [_rec(f"org/doc_{i}.md") for i in range(10)]
    manifest = _write_manifest(tmp_path, recs)
    result = runner.invoke(
        app,
        ["corpus", "generate-tests", str(manifest), "--max-source-tests", "3"],
    )
    assert result.exit_code == 0
    parsed = yaml.safe_load(result.output)
    source = [t for t in parsed["tests"] if t["name"].startswith("source-coverage-")]
    assert len(source) == 3


def test_cli_generate_tests_respects_max_risky_tests(tmp_path: Path) -> None:
    recs = [_rec(f"org/secret_{i}.md") for i in range(10)]
    manifest = _write_manifest(tmp_path, recs)
    result = runner.invoke(
        app,
        ["corpus", "generate-tests", str(manifest), "--max-risky-tests", "2"],
    )
    assert result.exit_code == 0
    parsed = yaml.safe_load(result.output)
    risky = [t for t in parsed["tests"] if t["name"].startswith("risky-source-")]
    assert len(risky) == 2


def test_cli_generate_tests_includes_tenant_tests(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [
            _rec("org_a/doc.md", tenant_id="org_a"),
            _rec("org_b/doc.md", tenant_id="org_b"),
        ],
    )
    result = runner.invoke(app, ["corpus", "generate-tests", str(manifest)])
    assert result.exit_code == 0
    parsed = yaml.safe_load(result.output)
    tenant = [t for t in parsed["tests"] if t["name"].startswith("tenant-prefix-")]
    assert len(tenant) == 2


def test_cli_generate_tests_no_tenant_tests_without_tenant_ids(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path, [_rec("doc.md")])
    result = runner.invoke(app, ["corpus", "generate-tests", str(manifest)])
    assert result.exit_code == 0
    parsed = yaml.safe_load(result.output)
    tenant = [t for t in parsed["tests"] if t["name"].startswith("tenant-prefix-")]
    assert len(tenant) == 0


def test_cli_generate_tests_empty_manifest_exits_nonzero(tmp_path: Path) -> None:
    manifest = tmp_path / "empty.jsonl"
    manifest.write_text("", encoding="utf-8")
    result = runner.invoke(app, ["corpus", "generate-tests", str(manifest)])
    assert result.exit_code == 1


def test_cli_generate_tests_missing_manifest_exits_2(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["corpus", "generate-tests", str(tmp_path / "nonexistent.jsonl")]
    )
    assert result.exit_code == 2


def test_cli_generate_tests_malformed_jsonl_skips_bad_lines(tmp_path: Path) -> None:
    """Malformed lines are silently skipped by iter_manifest; valid lines produce tests."""
    manifest = tmp_path / "mixed.jsonl"
    good_line = record_to_jsonl(_rec("org_a/doc.md"))
    manifest.write_text(
        "NOT VALID JSON\n" + good_line + "\n{bad: json}\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["corpus", "generate-tests", str(manifest)])
    assert result.exit_code == 0
    parsed = yaml.safe_load(result.output)
    assert len(parsed["tests"]) >= 1


def test_cli_generate_tests_output_validates(tmp_path: Path) -> None:
    """End-to-end: generate → write → validate."""
    recs = [
        _rec("org_a/refund_policy.md", tenant_id="org_a"),
        _rec("org_b/secret_token_policy.md", tenant_id="org_b"),
    ]
    manifest = _write_manifest(tmp_path, recs)
    output = tmp_path / "generated.yaml"

    gen_result = runner.invoke(
        app,
        [
            "corpus",
            "generate-tests",
            str(manifest),
            "--output",
            str(output),
            "--max-source-tests",
            "5",
            "--max-risky-tests",
            "5",
        ],
    )
    assert gen_result.exit_code == 0
    assert output.exists()

    val_result = runner.invoke(app, ["validate", str(output)])
    assert val_result.exit_code == 0


def test_cli_generate_tests_full_pipeline_with_scan(tmp_path: Path) -> None:
    """Scan a temp directory, then generate tests from the manifest."""
    corpus_dir = tmp_path / "corpus"
    (corpus_dir / "org_a").mkdir(parents=True)
    (corpus_dir / "org_b").mkdir(parents=True)
    (corpus_dir / "org_a" / "refund_policy.md").write_text("refund policy", encoding="utf-8")
    (corpus_dir / "org_b" / "secret_creds.md").write_text("secrets", encoding="utf-8")

    manifest = tmp_path / "manifest.jsonl"
    scan_result = runner.invoke(
        app,
        [
            "corpus",
            "scan",
            str(corpus_dir),
            "--output",
            str(manifest),
            "--tenant-from-path",
            "0",
        ],
    )
    assert scan_result.exit_code == 0

    output = tmp_path / "generated.yaml"
    gen_result = runner.invoke(
        app,
        ["corpus", "generate-tests", str(manifest), "--output", str(output)],
    )
    assert gen_result.exit_code == 0

    val_result = runner.invoke(app, ["validate", str(output)])
    assert val_result.exit_code == 0

    suite = load_suite(output)
    # Should have source, risky (secret_creds), and tenant tests
    names = [t.name for t in suite.tests]
    assert any(n.startswith("source-coverage-") for n in names)
    assert any(n.startswith("risky-source-") for n in names)
    assert any(n.startswith("tenant-prefix-") for n in names)
