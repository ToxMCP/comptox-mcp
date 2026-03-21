# Contributing to EPA CompTox MCP Server

Thanks for contributing. `comptox-mcp` is part of the broader ToxMCP suite, so changes here need to keep two things true at the same time:

- the server stays useful as a standalone MCP
- the public boundary stays clean for downstream AOP, PBPK, O-QT, and future orchestration consumers

## Project boundary

The released `v0.2.x` public server is an evidence-federation MCP. The canonical public surface is the default tool catalog exposed by `src/epacomp_tox/server.py`:

- chemical
- hazard
- exposure
- bioactivity
- metadata
- cheminformatics
- chemical list
- interop

Predictive and orchestrator code still exists in-repo, but it remains experimental until it is explicitly registered in the default server, documented in the README, covered by response contracts, and protected by release-gate tests.

## Before you start

If you are new to the repository, start with:

- [README.md](README.md)
- [docs/architecture_overview.md](docs/architecture_overview.md)
- [docs/contracts/README.md](docs/contracts/README.md)
- [schemas/README.md](schemas/README.md)
- [docs/development_guide.md](docs/development_guide.md)
- [open issues](https://github.com/ToxMCP/comptox-mcp/issues)

## Types of contributions

### Bug reports

Open an issue and include:

- a clear title
- steps to reproduce
- expected behavior vs. actual behavior
- environment details such as OS, Python version, and relevant config flags
- representative logs or payload fragments when available

### Enhancements

Open an issue describing:

- the problem you are trying to solve
- the proposed behavior
- any contract or schema impact
- why the change belongs in CompTox MCP rather than a sibling MCP

### Pull requests

1. Branch from `main`.
2. Make the smallest coherent change that solves the problem.
3. Add or update tests and docs with the code change.
4. Run the validation checks listed below.
5. Open a PR that explains the change, validation performed, and whether the public MCP surface changed.

## Validation expectations

Run these before opening a PR:

```bash
python -m black --check src tests
python -m isort --check-only src tests
python -m pytest -q
```

If your change affects the public surface, also make sure these release-sensitive checks still pass:

- `tests/test_tool_catalog_snapshot.py`
- `tests/test_portable_schemas.py`
- `tests/test_domain_contracts.py`
- `tests/test_cross_suite_handoffs.py`
- `tests/test_mcp_conformance_suite.py`

## Public contract changes

Changes to tool discovery, schemas, or transport-visible behavior should update the relevant contract and documentation together.

When you change the public MCP surface, check all of these:

- server registration and discovery metadata
- `docs/contracts/schemas/` response wrappers
- root `schemas/` portable objects when handoff payloads change
- `docs/contracts/endpoint-matrix.md`
- `README.md`
- `CHANGELOG.md`
- regression tests and fixtures

CompTox should stay lean at the suite boundary:

- do not duplicate OECD-style AOP semantics owned by `aop-mcp`
- do not duplicate PBPK execution or qualification objects owned by `pbpk-mcp`
- do not present experimental predictive/orchestrator code as canonical public surface unless the runtime, docs, and tests all agree

## Style and review expectations

- Follow [PEP 8](https://peps.python.org/pep-0008/) and keep changes readable.
- Use `black` and `isort` for formatting.
- Prefer focused patches over broad rewrites.
- Add comments only when they materially improve readability.
- Keep user-facing docs aligned with the live tool catalog.

## Support and security

- For general help, usage questions, or feature ideas, see [SUPPORT.md](SUPPORT.md).
- For vulnerabilities, use the private process in [SECURITY.md](SECURITY.md).

## Code of conduct

This project is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). By participating, you agree to uphold that code.
