# Release Process

This document describes how to publish `rag-agent-audit` to PyPI.

Publishing uses [Trusted Publishing (OIDC)](https://docs.pypi.org/trusted-publishers/)
— no PyPI API tokens or secrets are stored in the repository.

---

## Prerequisites

### 1. Configure Trusted Publishing on PyPI

Before the first release, register the GitHub Actions publisher on PyPI:

1. Go to <https://pypi.org/manage/project/rag-agent-audit/settings/publishing/>
   (create the project first with a manual upload if it does not yet exist).
2. Click **Add a new publisher** and fill in:
   - **Owner**: `Aravind-blip`
   - **Repository**: `rag-agent-audit`
   - **Workflow filename**: `publish-pypi.yml`
   - **Environment name**: `pypi`

### 2. Configure Trusted Publishing on TestPyPI (for dry runs)

Repeat the same steps at <https://test.pypi.org/manage/project/rag-agent-audit/settings/publishing/>
but use **Workflow filename**: `publish-testpypi.yml` and **Environment name**: `testpypi`.

### 3. Create GitHub Environments

In the repository settings → **Environments**, create two environments:

| Environment | Protection rules (recommended) |
|-------------|-------------------------------|
| `pypi` | Require approval from a maintainer before deploying |
| `testpypi` | None (manual workflow already gates this) |

---

## Dry-run on TestPyPI

Before every production release, verify the package uploads and installs cleanly:

1. Go to **Actions → Publish to TestPyPI** in the GitHub UI.
2. Click **Run workflow** → **Run workflow**.
3. After it completes, verify the install:

```bash
pip install --index-url https://test.pypi.org/simple/ rag-agent-audit
rag-agent-audit --help
```

---

## Production Release

### Step 1 — Bump the version

Edit `pyproject.toml`:

```toml
[project]
version = "X.Y.Z"
```

### Step 2 — Update CHANGELOG

Add a dated entry at the top of `CHANGELOG.md`:

```markdown
## vX.Y.Z — YYYY-MM-DD
```

### Step 3 — Commit and push

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "chore: release vX.Y.Z"
git push origin main
```

### Step 4 — Create and push an annotated tag

```bash
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

### Step 5 — Publish the GitHub Release

1. Go to **Releases → Draft a new release** on GitHub.
2. Choose the tag `vX.Y.Z`.
3. Fill in the release title and paste the CHANGELOG entry as the description.
4. Click **Publish release**.

The `publish-pypi.yml` workflow triggers automatically and publishes the package.

### Step 6 — Verify the production install

Wait a minute for PyPI to index the release, then:

```bash
# Using pip
pip install rag-agent-audit

# Using pipx (recommended for CLI tools)
pipx install rag-agent-audit

rag-agent-audit --help
rag-agent-audit run examples/basic/audit.yaml
```

---

## Package validation (CI)

The `package.yml` workflow runs on every pull request and push to `main`.
It builds the sdist and wheel, runs `twine check`, and smoke-tests the wheel
in a clean virtual environment. Packaging regressions are caught before a
release is cut.

To run the same checks locally:

```bash
pip install build twine
python -m build
twine check dist/*

# Smoke test
python -m venv /tmp/smoke-env
/tmp/smoke-env/bin/pip install dist/*.whl
/tmp/smoke-env/bin/rag-agent-audit --help
```

---

## Workflows summary

| Workflow | Trigger | Target |
|----------|---------|--------|
| `package.yml` | PR / push to `main` | Local build + smoke test |
| `publish-testpypi.yml` | Manual (`workflow_dispatch`) | TestPyPI |
| `publish-pypi.yml` | GitHub Release published | PyPI |
