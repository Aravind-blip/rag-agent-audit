"""
Known-sources check.

check_known_sources: Fails if any citation or retrieved source is not present
                     in the corpus manifest (exact path match).
load_known_sources:  Load a frozenset of paths from a JSONL manifest file.
"""

from __future__ import annotations

import json
from pathlib import Path

from rag_agent_audit.checks.diagnostics import format_list
from rag_agent_audit.normalizer import NormalizedResponse
from rag_agent_audit.result import CheckResult

_CHECK_NAME = "known_sources"


def load_known_sources(manifest_path: Path) -> frozenset[str]:
    """Return a frozenset of ``path`` values from a JSONL corpus manifest.

    Blank lines are silently ignored.  Any other problem raises ``ValueError``
    with the manifest filename and line number in the message.

    Raises
    ------
    ValueError
        If a non-blank line contains invalid JSON, is missing the ``path``
        field, or has a ``path`` value that is not a non-empty string.
    """
    name = manifest_path.name
    paths: set[str] = set()

    with open(manifest_path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line:
                continue  # blank lines are always ignored

            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Known sources manifest {name} has invalid JSON "
                    f"on line {lineno}: {exc.msg}"
                ) from exc

            if "path" not in data:
                raise ValueError(
                    f"Known sources manifest {name} is missing required "
                    f"field 'path' on line {lineno}."
                )

            path_val = data["path"]
            if not isinstance(path_val, str) or not path_val:
                raise ValueError(
                    f"Known sources manifest {name} has invalid 'path' "
                    f"on line {lineno}; expected non-empty string."
                )

            paths.add(path_val)

    return frozenset(paths)


def check_known_sources(
    response: NormalizedResponse,
    require: bool,
    known_sources: frozenset[str] | None,
    manifest_label: str,
) -> CheckResult:
    """Verify citations and retrieved sources exist in the corpus manifest.

    known_sources
        ``None`` means no manifest was configured on the suite.  Any other
        value (including an empty frozenset) means a manifest was specified
        but may have been empty.

    manifest_label
        The path string to display in failure messages (original config value).

    require
        When ``False`` the check is skipped unconditionally.
    """
    if not require:
        return CheckResult(_CHECK_NAME, True, "require_known_sources not set; skipped.")

    if known_sources is None:
        return CheckResult(
            _CHECK_NAME,
            False,
            "Check failed: known_sources\n"
            "require_known_sources is true but no known_sources_manifest is configured "
            "on the suite.\n"
            "\nSuggestion:\n"
            "  Add known_sources_manifest: <path-to-manifest.jsonl> to your suite config.",
        )

    # Both lists empty → trivially passes.
    if not response.citations and not response.retrieved_sources:
        return CheckResult(_CHECK_NAME, True, "No citations or retrieved sources; passed.")

    # Collect unknowns, deduplicating while preserving deterministic order.
    seen_cit: dict[str, None] = {}
    for s in response.citations:
        if s not in known_sources:
            seen_cit[s] = None

    seen_ret: dict[str, None] = {}
    for s in response.retrieved_sources:
        if s not in known_sources:
            seen_ret[s] = None

    unknown_cit = list(seen_cit)
    unknown_ret = list(seen_ret)

    if not unknown_cit and not unknown_ret:
        return CheckResult(_CHECK_NAME, True, "All sources exist in corpus manifest.")

    # ── Build diagnostic ───────────────────────────────────────────────────
    parts: list[str] = [f"Check failed: {_CHECK_NAME}"]

    if unknown_cit:
        parts.append("\nUnknown citation sources:")
        parts.append(format_list(unknown_cit))

    if unknown_ret:
        parts.append("\nUnknown retrieved sources:")
        parts.append(format_list(unknown_ret))

    parts.append(f"\nKnown source manifest:\n  {manifest_label}")

    parts.append("\nActual citations:")
    parts.append(format_list(response.citations))

    parts.append("\nActual retrieved sources:")
    parts.append(format_list(response.retrieved_sources))

    parts.append(
        "\nSuggestion:\n"
        "  Check citation mapping, retriever source IDs, or whether the corpus "
        "manifest is stale."
    )

    return CheckResult(_CHECK_NAME, False, "\n".join(parts))
