---
name: Contract change
about: Propose a change to the published MCP or portable-object contracts
title: "[Contract] "
labels: ["contracts"]
assignees: []
---

## Contract area

Select the primary surface:

- MCP tool discovery
- `docs/contracts/schemas/` response wrappers
- `schemas/` portable evidence objects
- transport-visible behavior
- README or endpoint matrix alignment

## Motivation

Why is this contract change needed?

## Proposed change

Describe the exact contract delta.

## Boundary check

Explain why this contract belongs in CompTox MCP and does not duplicate sibling MCP ownership:

- `aop-mcp` for OECD-style mechanistic semantics
- `pbpk-mcp` for PBPK execution, qualification, uncertainty, and internal exposure outputs
- orchestration layers for BER logic and final decision policy

## Compatibility

Choose one:

- [ ] additive and backward-compatible
- [ ] breaking change
- [ ] documentation-only clarification

## Required follow-through

Check all items expected to move with this change:

- [ ] server registration or discovery metadata
- [ ] `docs/contracts/schemas/`
- [ ] `schemas/`
- [ ] `docs/contracts/endpoint-matrix.md`
- [ ] `README.md`
- [ ] `CHANGELOG.md`
- [ ] tests and fixtures

## Example payloads

Provide before/after payload examples when possible.

