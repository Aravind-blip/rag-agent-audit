"""
Tenant leakage check.

check_tenant_leakage: Fails if any citation or retrieved source violates
                      allowed source prefixes or contains a forbidden tenant ID.
"""

from __future__ import annotations

from rag_agent_audit.checks.diagnostics import format_list
from rag_agent_audit.normalizer import NormalizedResponse
from rag_agent_audit.result import CheckResult

_CHECK_NAME = "tenant_leakage"


def _prefix_violations(sources: list[str], allowed_prefixes: list[str]) -> list[str]:
    """Return sources that do not start with any of the allowed prefixes."""
    return [s for s in sources if not any(s.startswith(p) for p in allowed_prefixes)]


def _forbidden_id_violations(sources: list[str], forbidden_ids: list[str]) -> list[str]:
    """Return sources that contain any of the forbidden tenant IDs (substring)."""
    return [s for s in sources if any(fid in s for fid in forbidden_ids)]


def check_tenant_leakage(
    response: NormalizedResponse,
    allowed_source_prefixes: list[str],
    forbidden_tenant_ids: list[str],
) -> CheckResult:
    """Check that all citation and retrieved sources conform to tenant rules.

    allowed_source_prefixes
        Every observed source must start with one of these prefixes.
        Empty sources lists are not a failure.

    forbidden_tenant_ids
        No observed source may contain any of these strings (substring match).

    When both lists are empty the check is skipped.
    """
    if not allowed_source_prefixes and not forbidden_tenant_ids:
        return CheckResult(_CHECK_NAME, True, "No tenant rules defined; skipped.")

    # ── Collect violations ─────────────────────────────────────────────────
    prefix_viol_cit: list[str] = []
    prefix_viol_ret: list[str] = []
    id_viol_cit: list[str] = []
    id_viol_ret: list[str] = []

    if allowed_source_prefixes:
        prefix_viol_cit = _prefix_violations(response.citations, allowed_source_prefixes)
        prefix_viol_ret = _prefix_violations(
            response.retrieved_sources, allowed_source_prefixes
        )

    if forbidden_tenant_ids:
        id_viol_cit = _forbidden_id_violations(response.citations, forbidden_tenant_ids)
        id_viol_ret = _forbidden_id_violations(
            response.retrieved_sources, forbidden_tenant_ids
        )

    any_violation = any(
        [prefix_viol_cit, prefix_viol_ret, id_viol_cit, id_viol_ret]
    )

    if not any_violation:
        return CheckResult(_CHECK_NAME, True, "No tenant leakage detected.")

    # ── Build diagnostic message ───────────────────────────────────────────
    parts: list[str] = [f"Check failed: {_CHECK_NAME}"]

    if prefix_viol_cit or prefix_viol_ret:
        parts.append("\nSources not matching allowed prefixes:")
        for src in prefix_viol_cit:
            parts.append(f"  - {src}  [citation]")
        for src in prefix_viol_ret:
            parts.append(f"  - {src}  [retrieved]")

    if id_viol_cit or id_viol_ret:
        parts.append("\nSources matching forbidden tenant IDs:")
        for src in id_viol_cit:
            parts.append(f"  - {src}  [citation]")
        for src in id_viol_ret:
            parts.append(f"  - {src}  [retrieved]")

    if allowed_source_prefixes:
        parts.append("\nAllowed source prefixes:")
        parts.append(format_list(allowed_source_prefixes))

    if forbidden_tenant_ids:
        parts.append("\nForbidden tenant IDs:")
        parts.append(format_list(forbidden_tenant_ids))

    parts.append("\nActual citations:")
    parts.append(format_list(response.citations))

    parts.append("\nActual retrieved sources:")
    parts.append(format_list(response.retrieved_sources))

    parts.append(
        "\nSuggestion:\n"
        "  Check retriever filters, tenant authorization, or citation rendering."
    )

    return CheckResult(_CHECK_NAME, False, "\n".join(parts))
