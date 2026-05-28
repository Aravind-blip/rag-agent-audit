# Security Policy

## Scope

`rag-agent-audit` is a regression testing tool. It helps detect known RAG and agent failure patterns in pre-deployment testing. It does not guarantee security, compliance, privacy, or absence of vulnerabilities in the systems it tests.

## Reporting a vulnerability

If you find a security vulnerability in `rag-agent-audit` itself (not in the systems it tests), please do not open a public GitHub issue.

Email: aravindbandipelli@gmail.com

Include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact

You will receive a response within 5 business days. We will coordinate a fix and disclosure timeline with you.

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✓         |

## Security design notes

- `rag-agent-audit` does not store, log, or transmit response data outside the local process.
- HTTP adapter requests are made directly from the machine running the tool. No proxy or relay is involved.
- Environment variable expansion (`${VAR}`) is used for secrets. Never put secrets directly in `audit.yaml` files committed to source control.
- Mock responses in `audit.yaml` files should not contain real user data, PII, or production credentials.
