# Support

Use the right channel for the right kind of request so the public issue tracker stays useful and security-sensitive reports stay private.

## Maintainer and contact

This project is maintained by [Ivo Djidrovski (`@senseibelbi`)](https://github.com/senseibelbi).

- For bugs, usage questions, documentation feedback, and feature requests, use [GitHub Issues](https://github.com/ToxMCP/comptox-mcp/issues).
- For private general inquiries, use the [in4r.ai contact form](https://www.in4r.ai/#contact).
- For vulnerabilities and other security-sensitive reports, use [GitHub's private security advisory channel](https://github.com/ToxMCP/comptox-mcp/security/advisories/new).

## When to open an issue

Use [GitHub Issues](https://github.com/ToxMCP/comptox-mcp/issues) for:

- bug reports
- feature requests
- public contract questions
- schema and interoperability proposals
- documentation fixes
- usage questions that are safe to discuss in public

When opening an issue, include enough context to make the report actionable:

- what you were trying to do
- relevant tool names, schema names, or endpoints
- representative request and response snippets when possible
- environment details such as Python version, transport mode, and whether you used live CTX credentials

## Before filing a support request

Check these first:

- [README.md](README.md)
- [docs/architecture_overview.md](docs/architecture_overview.md)
- [docs/contracts/README.md](docs/contracts/README.md)
- [schemas/README.md](schemas/README.md)
- [docs/development_guide.md](docs/development_guide.md)

## Security reports

Do not use public issues for vulnerabilities, credential exposure, auth bypasses, or other security-sensitive findings.

Use the private advisory workflow described in [SECURITY.md](SECURITY.md):

- https://github.com/ToxMCP/comptox-mcp/security/advisories/new

## Scope reminders

`comptox-mcp` is the suite's evidence-federation MCP. Support requests are most useful when they stay aligned with that boundary:

- CompTox MCP owns identity, hazard, exposure, bioactivity, metadata, and handoff packaging.
- `aop-mcp` owns OECD-style mechanistic semantics.
- `pbpk-mcp` owns PBPK execution, qualification, uncertainty, and internal exposure outputs.
- Experimental predictive/orchestrator code in this repository is not part of the default public MCP catalog unless explicitly documented and registered.

## Response expectations

This is an open-source project and response times are best-effort. Clear, reproducible reports get the fastest triage.
