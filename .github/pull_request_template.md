---
name: Pull request
about: Propose a change to the project
title: ''
labels: ''
assignees: ''

---

## Summary

Describe what this PR changes and why.

## Scope

Check all that apply:

- [ ] code change
- [ ] docs-only change
- [ ] public MCP surface change
- [ ] schema or contract change
- [ ] interop or handoff change
- [ ] internal experimental work only

## Related issues

Link any related issues.

## Boundary notes

If this changes the public surface, explain why it belongs in `comptox-mcp` and does not duplicate sibling MCP ownership.

## Validation

List the commands or checks you ran.

```bash
python -m black --check src tests
python -m isort --check-only src tests
python -m pytest -q
```

If applicable, note whether you also updated:

- `docs/contracts/schemas/`
- `schemas/`
- `docs/contracts/endpoint-matrix.md`
- `README.md`
- `CHANGELOG.md`
- regression fixtures

## Checklist
- [ ] I have read the [CONTRIBUTING.md](CONTRIBUTING.md) file.
- [ ] I have added or updated tests to cover my changes.
- [ ] I have run `pytest` and all tests are passing.
- [ ] I have formatted my code with `isort` and `black`.
- [ ] If I changed the public surface, I updated the relevant contracts, README, changelog, and fixtures.
