"""Tests for the tenant_leakage check."""

from __future__ import annotations

from rag_agent_audit.checks.tenant_leakage import check_tenant_leakage
from rag_agent_audit.config import AuditTestCase
from rag_agent_audit.normalizer import NormalizedResponse

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


def _passed(result) -> bool:  # type: ignore[no-untyped-def]
    return result.passed


# ---------------------------------------------------------------------------
# Skipped: no rules defined
# ---------------------------------------------------------------------------


def test_skipped_when_both_lists_empty() -> None:
    result = check_tenant_leakage(_resp(["tenant-a/doc.md"]), [], [])
    assert _passed(result)
    assert "skipped" in result.message.lower()


# ---------------------------------------------------------------------------
# allowed_source_prefixes — passing cases
# ---------------------------------------------------------------------------


def test_passes_when_all_citations_match_prefix() -> None:
    result = check_tenant_leakage(
        _resp(citations=["tenant-a/doc.md", "tenant-a/faq.md"]),
        allowed_source_prefixes=["tenant-a/"],
        forbidden_tenant_ids=[],
    )
    assert _passed(result)


def test_passes_when_all_retrieved_match_prefix() -> None:
    result = check_tenant_leakage(
        _resp(retrieved=["tenant-a/doc.md", "tenant-a/faq.md"]),
        allowed_source_prefixes=["tenant-a/"],
        forbidden_tenant_ids=[],
    )
    assert _passed(result)


def test_passes_when_multiple_prefixes_and_each_source_matches_one() -> None:
    result = check_tenant_leakage(
        _resp(
            citations=["tenant-a/file.md", "tenant-b/other.md"],
            retrieved=["tenant-a/x.txt"],
        ),
        allowed_source_prefixes=["tenant-a/", "tenant-b/"],
        forbidden_tenant_ids=[],
    )
    assert _passed(result)


def test_passes_with_empty_citations_and_retrieved() -> None:
    result = check_tenant_leakage(
        _resp(citations=[], retrieved=[]),
        allowed_source_prefixes=["tenant-a/"],
        forbidden_tenant_ids=[],
    )
    assert _passed(result)
    assert "No tenant leakage detected" in result.message


def test_passes_when_no_citations_only_empty_retrieved() -> None:
    result = check_tenant_leakage(
        _resp(citations=["tenant-a/doc.md"], retrieved=[]),
        allowed_source_prefixes=["tenant-a/"],
        forbidden_tenant_ids=[],
    )
    assert _passed(result)


# ---------------------------------------------------------------------------
# allowed_source_prefixes — failing cases
# ---------------------------------------------------------------------------


def test_fails_when_citation_violates_prefix() -> None:
    result = check_tenant_leakage(
        _resp(citations=["tenant-b/evil.md"]),
        allowed_source_prefixes=["tenant-a/"],
        forbidden_tenant_ids=[],
    )
    assert not _passed(result)
    assert "tenant-b/evil.md" in result.message
    assert "[citation]" in result.message


def test_fails_when_retrieved_source_violates_prefix() -> None:
    result = check_tenant_leakage(
        _resp(retrieved=["tenant-b/secret.md"]),
        allowed_source_prefixes=["tenant-a/"],
        forbidden_tenant_ids=[],
    )
    assert not _passed(result)
    assert "tenant-b/secret.md" in result.message
    assert "[retrieved]" in result.message


def test_fails_when_one_of_many_citations_violates_prefix() -> None:
    result = check_tenant_leakage(
        _resp(citations=["tenant-a/ok.md", "tenant-b/bad.md"]),
        allowed_source_prefixes=["tenant-a/"],
        forbidden_tenant_ids=[],
    )
    assert not _passed(result)
    assert "tenant-b/bad.md" in result.message
    # The violation section must list the bad source tagged as [citation];
    # the good source should NOT appear in the violation section.
    violation_section = result.message.split("Actual citations")[0]
    assert "tenant-b/bad.md  [citation]" in violation_section
    assert "tenant-a/ok.md" not in violation_section


def test_prefix_violation_message_contains_check_failed_header() -> None:
    result = check_tenant_leakage(
        _resp(citations=["other-tenant/doc.md"]),
        allowed_source_prefixes=["tenant-a/"],
        forbidden_tenant_ids=[],
    )
    assert "Check failed: tenant_leakage" in result.message


def test_prefix_violation_message_contains_allowed_prefixes() -> None:
    result = check_tenant_leakage(
        _resp(citations=["bad/doc.md"]),
        allowed_source_prefixes=["tenant-a/", "tenant-b/"],
        forbidden_tenant_ids=[],
    )
    assert "tenant-a/" in result.message
    assert "tenant-b/" in result.message
    assert "Allowed source prefixes" in result.message


def test_prefix_violation_message_contains_actual_citations() -> None:
    result = check_tenant_leakage(
        _resp(citations=["bad/doc.md"]),
        allowed_source_prefixes=["good/"],
        forbidden_tenant_ids=[],
    )
    assert "Actual citations" in result.message
    assert "bad/doc.md" in result.message


def test_prefix_violation_message_contains_suggestion() -> None:
    result = check_tenant_leakage(
        _resp(citations=["bad/doc.md"]),
        allowed_source_prefixes=["good/"],
        forbidden_tenant_ids=[],
    )
    assert "Suggestion" in result.message


# ---------------------------------------------------------------------------
# forbidden_tenant_ids — passing cases
# ---------------------------------------------------------------------------


def test_passes_when_no_forbidden_id_in_citations() -> None:
    result = check_tenant_leakage(
        _resp(citations=["tenant-a/doc.md"]),
        allowed_source_prefixes=[],
        forbidden_tenant_ids=["tenant-b"],
    )
    assert _passed(result)


def test_passes_when_no_forbidden_id_in_retrieved() -> None:
    result = check_tenant_leakage(
        _resp(retrieved=["tenant-a/doc.md"]),
        allowed_source_prefixes=[],
        forbidden_tenant_ids=["tenant-b"],
    )
    assert _passed(result)


# ---------------------------------------------------------------------------
# forbidden_tenant_ids — failing cases
# ---------------------------------------------------------------------------


def test_fails_when_citation_contains_forbidden_id() -> None:
    result = check_tenant_leakage(
        _resp(citations=["tenant-b/doc.md"]),
        allowed_source_prefixes=[],
        forbidden_tenant_ids=["tenant-b"],
    )
    assert not _passed(result)
    assert "tenant-b/doc.md" in result.message
    assert "[citation]" in result.message


def test_fails_when_retrieved_contains_forbidden_id() -> None:
    result = check_tenant_leakage(
        _resp(retrieved=["acme-tenant-b-private/secret.md"]),
        allowed_source_prefixes=[],
        forbidden_tenant_ids=["tenant-b"],
    )
    assert not _passed(result)
    assert "acme-tenant-b-private/secret.md" in result.message
    assert "[retrieved]" in result.message


def test_forbidden_id_is_substring_match() -> None:
    """Forbidden ID 'corp-x' should match 'docs/corp-x-internal/policy.md'."""
    result = check_tenant_leakage(
        _resp(citations=["docs/corp-x-internal/policy.md"]),
        allowed_source_prefixes=[],
        forbidden_tenant_ids=["corp-x"],
    )
    assert not _passed(result)


def test_forbidden_id_violation_message_contains_check_failed_header() -> None:
    result = check_tenant_leakage(
        _resp(citations=["tenant-b/doc.md"]),
        allowed_source_prefixes=[],
        forbidden_tenant_ids=["tenant-b"],
    )
    assert "Check failed: tenant_leakage" in result.message


def test_forbidden_id_violation_message_contains_forbidden_ids_section() -> None:
    result = check_tenant_leakage(
        _resp(citations=["tenant-b/doc.md"]),
        allowed_source_prefixes=[],
        forbidden_tenant_ids=["tenant-b", "corp-x"],
    )
    assert "Forbidden tenant IDs" in result.message
    assert "tenant-b" in result.message
    assert "corp-x" in result.message


def test_forbidden_id_violation_message_contains_actual_retrieved() -> None:
    result = check_tenant_leakage(
        _resp(retrieved=["tenant-b/doc.md"]),
        allowed_source_prefixes=[],
        forbidden_tenant_ids=["tenant-b"],
    )
    assert "Actual retrieved sources" in result.message
    assert "tenant-b/doc.md" in result.message


# ---------------------------------------------------------------------------
# Both rules active simultaneously
# ---------------------------------------------------------------------------


def test_both_rules_both_pass() -> None:
    result = check_tenant_leakage(
        _resp(
            citations=["tenant-a/good.md"],
            retrieved=["tenant-a/other.md"],
        ),
        allowed_source_prefixes=["tenant-a/"],
        forbidden_tenant_ids=["tenant-b"],
    )
    assert _passed(result)


def test_both_rules_prefix_fails_id_passes() -> None:
    result = check_tenant_leakage(
        _resp(citations=["other-tenant/doc.md"]),
        allowed_source_prefixes=["tenant-a/"],
        forbidden_tenant_ids=["tenant-b"],
    )
    assert not _passed(result)
    assert "Sources not matching allowed prefixes" in result.message


def test_both_rules_prefix_passes_id_fails() -> None:
    result = check_tenant_leakage(
        _resp(citations=["tenant-a/tenant-b-ref.md"]),
        allowed_source_prefixes=["tenant-a/"],
        forbidden_tenant_ids=["tenant-b"],
    )
    assert not _passed(result)
    assert "Sources matching forbidden tenant IDs" in result.message


def test_both_rules_both_fail_shows_both_sections() -> None:
    result = check_tenant_leakage(
        _resp(
            citations=["other/doc.md", "tenant-b/private.md"],
        ),
        allowed_source_prefixes=["tenant-a/"],
        forbidden_tenant_ids=["tenant-b"],
    )
    assert not _passed(result)
    assert "Sources not matching allowed prefixes" in result.message
    assert "Sources matching forbidden tenant IDs" in result.message


# ---------------------------------------------------------------------------
# check_name
# ---------------------------------------------------------------------------


def test_check_name_is_tenant_leakage() -> None:
    result = check_tenant_leakage(_resp(), ["tenant-a/"], [])
    assert result.check_name == "tenant_leakage"


def test_check_name_on_failure_is_tenant_leakage() -> None:
    result = check_tenant_leakage(_resp(citations=["bad/doc.md"]), ["tenant-a/"], [])
    assert result.check_name == "tenant_leakage"


# ---------------------------------------------------------------------------
# Config schema: new fields on AuditTestCase
# ---------------------------------------------------------------------------


def test_config_accepts_allowed_source_prefixes() -> None:
    tc = AuditTestCase(
        name="t1",
        question="What is the policy?",
        allowed_source_prefixes=["tenant-a/", "tenant-b/"],
    )
    assert tc.allowed_source_prefixes == ["tenant-a/", "tenant-b/"]


def test_config_accepts_forbidden_tenant_ids() -> None:
    tc = AuditTestCase(
        name="t1",
        question="What is the policy?",
        forbidden_tenant_ids=["tenant-x", "corp-y"],
    )
    assert tc.forbidden_tenant_ids == ["tenant-x", "corp-y"]


def test_config_defaults_both_fields_to_empty() -> None:
    tc = AuditTestCase(name="t1", question="q")
    assert tc.allowed_source_prefixes == []
    assert tc.forbidden_tenant_ids == []


def test_config_both_fields_together() -> None:
    tc = AuditTestCase(
        name="combined",
        question="q",
        allowed_source_prefixes=["tenant-a/"],
        forbidden_tenant_ids=["tenant-b"],
    )
    assert tc.allowed_source_prefixes == ["tenant-a/"]
    assert tc.forbidden_tenant_ids == ["tenant-b"]
