# Developer Onboarding Checklist

## Access & Accounts
- [ ] Obtain EPA CompTox API credentials (store in secure manager, export `CTX_API_KEY` locally).
- [ ] Request access to shared observability dashboards and audit bucket.
- [ ] Join the Agentic SDK workspace / org with appropriate role.

## Local Environment
- [ ] Clone repository and run `pip install -e .[dev]` (see `docs/development_guide.md` for details).
- [ ] Copy `.env.example` to `.env.local` and populate CTX, audit, and transport env vars.
- [ ] Verify lint/test tooling: `pytest`, `black`, `isort`, `mypy` (optional).
- [ ] Launch transport locally (`uvicorn ...`) and execute `scripts/mcp_ws_client.py --list-tools`.

## Documentation & Architecture
- [ ] Read `README.md` (architecture overview) and `docs/architecture_overview.md`.
- [ ] Review guardrail policies in `docs/model_cards_and_policies.md`.
- [ ] Walk through Agentic integration guidance in `docs/agentic_sdk_integration.md` and run the Python quickstart.
- [ ] Review QA checklists in this folder to understand release expectations.

## First Contribution
- [ ] Run `pytest` (ensure green baseline).
- [ ] Implement or update a doc/example; open PR and request DX/QA review.
- [ ] Follow commit conventions and reference tracking IDs in PR description.

## Release Readiness Awareness
- [ ] Understand doc publishing pipeline (`scripts/build_docs.sh`, `.github/workflows/docs.yml` once configured).
- [ ] Review deployment runbooks (transport, predictive services) and shadow an on-call rotation if applicable.
- [ ] Attend guardrail/governance review to learn approval workflow.

## Confirmation
- [ ] Mentor/buddy walkthrough complete (name/date):
- [ ] New developer acknowledgement (name/date):
