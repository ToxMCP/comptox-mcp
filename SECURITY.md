# Security Policy

## Supported Versions

Security fixes are provided for the latest state of the `main` branch.

| Version | Supported |
| --- | --- |
| `main` | Yes |
| Older branches/tags | No |

## Reporting a Vulnerability

Please report suspected vulnerabilities through GitHub's private advisory channel:

- https://github.com/ToxMCP/comptox-mcp/security/advisories/new

Do not open public issues for security-sensitive reports.

For non-security questions, bug reports, or feature requests, use the guidance in [SUPPORT.md](SUPPORT.md).

When filing a report, include:

1. A clear description of the issue and impact.
2. Reproduction steps or a minimal proof of concept.
3. Affected versions/commit hashes.
4. Any suggested remediation, if available.

## Scope

Examples of issues that should be reported through the private advisory channel include:

1. Credential leakage or unsafe handling of `CTX_API_KEY` and related secrets.
2. Authentication or authorization bypass in the HTTP or WebSocket transports.
3. Sensitive data exposure through logs, metrics, traces, or MCP responses.
4. Contract or validation bypasses that expose unintended tools, schemas, or privileged actions.
5. Dependency vulnerabilities with credible impact on the deployed server.

## Response Expectations

Maintainers will aim to:

1. Acknowledge new reports within 3 business days.
2. Provide a status update or triage decision within 10 business days.
3. Coordinate remediation and disclosure timing with the reporter.

## Disclosure Guidance

- Keep details private until maintainers confirm a remediation and disclosure plan.
- Avoid posting proof-of-concept exploits or sensitive traces in public issues or pull requests.
- If you are unsure whether something is security-sensitive, err on the side of private disclosure first.
