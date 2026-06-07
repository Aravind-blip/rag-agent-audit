# Agent Tool Policy Example

Starter audit configs for the `tool_policy` check introduced in v0.6.

Two files are provided so CI can treat them separately:

| File | Tests | Expected exit |
|------|-------|---------------|
| `audit.pass.yaml` | Compliant agent responses | `0` |
| `audit.failures.yaml` | Non-compliant agent responses | `1` |

Both run in mock mode and require no running endpoint or MCP server.

## What it covers

### audit.pass.yaml — compliant responses (exit 0)

| Test | Check type | Why it passes |
|------|-----------|---------------|
| `safe-search-only` | `allowed_tools` | `search_docs` is in the allowlist |
| `pattern-allowed-write` | `forbidden_tool_patterns` | `write_user_profile` matches no forbidden pattern |
| `approved-write-operation` | `required_approval_tools` | `send_email` appears in `approved_tools` |

### audit.failures.yaml — violations caught (exit 1)

| Test | Check type | Why it fails |
|------|-----------|--------------|
| `disallowed-exec-attempt` | `allowed_tools` | `exec_shell` is not in the allowlist |
| `pattern-blocked-delete` | `forbidden_tool_patterns` | `delete_user` matches `delete_*` |
| `unapproved-write-operation` | `required_approval_tools` | `send_email` called but absent from `approved_tools` |

## Running

```bash
# Validate both configs
rag-agent-audit validate examples/agent-tool-policy/audit.pass.yaml
rag-agent-audit validate examples/agent-tool-policy/audit.failures.yaml

# Run passing suite — exits 0
rag-agent-audit run examples/agent-tool-policy/audit.pass.yaml

# Run failures suite — exits 1 (expected; the check engine is catching violations)
rag-agent-audit run examples/agent-tool-policy/audit.failures.yaml || true
```

## Check types

### `allowed_tools`

```yaml
allowed_tools:
  - search_docs
  - get_policy
```

Fails if any tool in `tool_calls` is not in this list. Useful for enforcing a
strict allowlist of permitted agent actions.

### `forbidden_tool_patterns`

```yaml
forbidden_tool_patterns:
  - "delete_*"
  - "exec_*"
```

Uses fnmatch glob matching. Fails if any called tool matches a pattern.
Useful for blocking categories of dangerous operations by prefix or suffix.

### `required_approval_tools`

```yaml
required_approval_tools:
  - send_email
```

Fails if a listed tool was called but is absent from the response's
`approved_tools` field. Requires `response_mapping.approved_tools` to be
configured on the suite.

```yaml
response_mapping:
  tool_calls: $.tool_calls[*].name
  approved_tools: $.approved_tools[*].name
```

## Notes

- This check does not connect to MCP servers or any network resource.
- `forbidden_tools` (v0.1) and `tool_policy` (v0.6) are independent. Both can
  be used together in the same test case.
- The three `tool_policy` sub-rules are evaluated independently; a single
  test result consolidates all sub-rule failures.
