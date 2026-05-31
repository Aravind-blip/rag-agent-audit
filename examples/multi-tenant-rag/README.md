# Multi-tenant RAG test pack

A synthetic regression test pack for multi-tenant RAG systems.

This example simulates two fictional organizations sharing a RAG platform:

- **Org A — Acme Retail Co.** (customer and employee documents)
- **Org B — Beta Services Ltd.** (compensation policy and customer records, restricted)

The audit checks for known failure patterns: documents from one tenant
appearing in another tenant's answers or retriever output, credential
elicitation, prompt injection via a malicious vendor document, and dangerous
tool calls.

**This is a synthetic regression test pack, not a proof of tenant security,
compliance correctness, or access-control completeness.** Passing these tests
does not mean your system cannot leak data. It means the specific patterns
checked here did not appear in the responses at the time of the run. Combine
with access control design, penetration testing, and manual review.

---

## Corpus

All documents in `corpus/` are fully synthetic. No real customer data, real
company documents, real credentials, or real private information is included.

| File | Simulates |
|------|-----------|
| `org_a_refund_policy.md` | Org A public customer-facing refund policy |
| `org_a_employee_handbook.md` | Org A internal employee handbook |
| `org_b_compensation_policy.md` | Org B restricted HR compensation policy |
| `org_b_customer_records.md` | Org B restricted customer records (fictional names) |
| `malicious_vendor_policy.md` | A vendor document with an embedded prompt-injection attempt |

---

## What the tests check

| Test | Pattern |
|------|---------|
| `org-a-refund-policy-cited` | Correct document retrieved and cited for Org A query |
| `org-a-employee-handbook-cited` | Correct internal document retrieved for Org A query |
| `org-a-no-cross-tenant-compensation-citation` | Org B compensation policy not cited in Org A answer |
| `org-a-no-cross-tenant-compensation-retrieved` | Org B compensation policy not in retriever output |
| `org-a-no-cross-tenant-customer-records-citation` | Org B customer records not cited in Org A answer |
| `org-a-no-cross-tenant-customer-records-retrieved` | Org B customer records not in retriever output |
| `private-api-key-request-fallback` | Credential elicitation produces fallback + no secret strings |
| `injection-instruction-not-echoed` | Malicious vendor doc injection text not echoed in answer |
| `dangerous-action-no-forbidden-tools` | Dangerous action request does not call forbidden tools |
| `out-of-corpus-question-fallback` | Out-of-corpus question produces fallback, not hallucination |

---

## Prerequisites

- A local RAG application responding at `http://localhost:8000/chat`
- The corpus files from `corpus/` indexed into your application
- Tenant isolation configured so that queries identified as Org A cannot
  retrieve documents belonging to Org B

The `audit.yaml` sends a `tenant_id: "org-a"` default field. Adapt this to
match your application's tenant context mechanism (header, request body field,
JWT claim, etc.).

---

## Validate without a running endpoint

```bash
rag-agent-audit validate examples/multi-tenant-rag/audit.yaml
```

This checks the config structure without sending any HTTP requests.

---

## Run against a local RAG app

```bash
rag-agent-audit run examples/multi-tenant-rag/audit.yaml
```

With JUnit output for CI:

```bash
rag-agent-audit run examples/multi-tenant-rag/audit.yaml \
  --format junit \
  --output multi-tenant-results.xml
```

With Docker:

```bash
docker run --rm \
  --network host \
  -v "$PWD:/workspace" \
  rag-agent-audit run /workspace/examples/multi-tenant-rag/audit.yaml
```

`--network host` lets the container reach your app on `localhost:8000`.

---

## Adapting the config

### Change the endpoint

```yaml
endpoint: http://localhost:8000/chat  # replace with your app's URL
```

### Add authentication

```yaml
request:
  headers:
    authorization: "Bearer ${AUTH_TOKEN}"
    x-tenant-id: "${TENANT_ID}"
```

Set `AUTH_TOKEN` and `TENANT_ID` as environment variables before running:

```bash
AUTH_TOKEN=mytoken TENANT_ID=org-a rag-agent-audit run examples/multi-tenant-rag/audit.yaml
```

### Match your response shape

Use `rag-agent-audit inspect` to auto-detect your app's response fields:

```bash
rag-agent-audit inspect \
  --endpoint http://localhost:8000/chat \
  --question "What is the refund policy?"
```

Then update `response_mapping` in `audit.yaml` with the suggested paths.

### Remove tests that don't apply

If your app does not expose tool calls in the response, remove
`forbidden_tools` tests or update `response_mapping.tool_calls` to point at
the correct field.

If your app does not expose retriever output, `forbidden_retrieved_sources`
tests will always pass vacuously — remove them or add retriever debug output
to your response.

---

## Limitations

- **Requires a running RAG endpoint.** This example is not included in CI
  because there is no running app to test against. Run it locally against your
  own RAG application.
- **String matching only.** Checks use exact string matching (case-sensitive
  by default). Semantic similarity between retrieved document names and the
  `expected_sources` / `forbidden_sources` values is not evaluated.
- **Corpus must be indexed.** The corpus files are reference documents for
  your RAG ingestion pipeline — `rag-agent-audit` does not index them. You
  must load them into your app's vector store or retriever before running.
- **Tenant isolation depends on your app.** The `defaults.tenant_id` field is
  sent as a request body field. Whether and how your app enforces tenant
  isolation based on that field is entirely your application's responsibility.
- **Passing tests do not guarantee security.** The checks cover the specific
  patterns listed above. They are not exhaustive.
