# Release Artifact Verification

This guide explains how to verify published `comptox-mcp` release artifacts with the GitHub CLI.

Releases published on or after **March 22, 2026** by [`release-sbom.yml`](../../.github/workflows/release-sbom.yml) include:

- built distribution artifacts (`dist/*.whl`, `dist/*.tar.gz`)
- a CycloneDX SBOM asset: `epacomp-tox-mcp.sbom.cdx.json`
- a provenance attestation bundle: `release-provenance.bundle.json`
- an SBOM attestation bundle: `release-sbom-attestation.bundle.json`

Older releases may not contain these assets.

## Prerequisites

- GitHub CLI with attestation support (`gh attestation verify`, `gh attestation download`, `gh attestation trusted-root`)
- access to the target release assets, either via `gh release download` or the GitHub release page

The commands below assume the canonical repository is `ToxMCP/comptox-mcp`.

## Step 1: Download the release assets

Download the published release assets into a temporary directory:

```bash
TAG=v0.2.2
mkdir -p /tmp/comptox-release
gh release download "$TAG" \
  -R ToxMCP/comptox-mcp \
  -D /tmp/comptox-release
```

Inspect the downloaded files:

```bash
ls -1 /tmp/comptox-release
```

## Step 2: Verify release provenance online

Verify the wheel or source distribution against the repository and the exact signer workflow:

```bash
gh attestation verify /tmp/comptox-release/*.whl \
  -R ToxMCP/comptox-mcp \
  --signer-workflow ToxMCP/comptox-mcp/.github/workflows/release-sbom.yml
```

You can do the same for the source distribution:

```bash
gh attestation verify /tmp/comptox-release/*.tar.gz \
  -R ToxMCP/comptox-mcp \
  --signer-workflow ToxMCP/comptox-mcp/.github/workflows/release-sbom.yml
```

For a tagged release, you can tighten the identity further:

```bash
gh attestation verify /tmp/comptox-release/*.whl \
  -R ToxMCP/comptox-mcp \
  --signer-workflow ToxMCP/comptox-mcp/.github/workflows/release-sbom.yml \
  --source-ref "refs/tags/${TAG}"
```

## Step 3: Verify the SBOM attestation

The release workflow emits a CycloneDX SBOM and signs it as an SBOM attestation. GitHub's default verification predicate is SLSA provenance, so SBOM verification must set the predicate explicitly:

```bash
gh attestation verify /tmp/comptox-release/*.whl \
  -R ToxMCP/comptox-mcp \
  --signer-workflow ToxMCP/comptox-mcp/.github/workflows/release-sbom.yml \
  --predicate-type https://cyclonedx.org/bom
```

To inspect the attested SBOM payload:

```bash
gh attestation verify /tmp/comptox-release/*.whl \
  -R ToxMCP/comptox-mcp \
  --signer-workflow ToxMCP/comptox-mcp/.github/workflows/release-sbom.yml \
  --predicate-type https://cyclonedx.org/bom \
  --format json \
  --jq '.[].verificationResult.statement.predicate'
```

## Step 4: Verify offline or in an air-gapped environment

From an online machine, download the attestation bundle for the artifact:

```bash
gh attestation download /tmp/comptox-release/*.whl \
  -R ToxMCP/comptox-mcp
```

Download the current trusted roots:

```bash
gh attestation trusted-root > trusted_root.jsonl
```

Move the artifact, the downloaded bundle, and `trusted_root.jsonl` into the offline environment. Then run:

```bash
gh attestation verify /tmp/comptox-release/*.whl \
  -R ToxMCP/comptox-mcp \
  --bundle sha256:YOUR_DIGEST.jsonl \
  --custom-trusted-root trusted_root.jsonl \
  --signer-workflow ToxMCP/comptox-mcp/.github/workflows/release-sbom.yml
```

For offline SBOM verification, add the CycloneDX predicate:

```bash
gh attestation verify /tmp/comptox-release/*.whl \
  -R ToxMCP/comptox-mcp \
  --bundle sha256:YOUR_DIGEST.jsonl \
  --custom-trusted-root trusted_root.jsonl \
  --signer-workflow ToxMCP/comptox-mcp/.github/workflows/release-sbom.yml \
  --predicate-type https://cyclonedx.org/bom
```

## Expected outcome

Verification should succeed only when:

- the artifact matches the attested digest
- the attestation was issued for `ToxMCP/comptox-mcp`
- the signer workflow identity matches `.github/workflows/release-sbom.yml`
- the predicate type matches the expected claim (`https://slsa.dev/provenance/v1` by default, or `https://cyclonedx.org/bom` for the SBOM attestation)

## References

- [GitHub Docs: Using artifact attestations to establish provenance for builds](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)
- [GitHub Docs: Verifying attestations offline](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/verify-attestations-offline)
- [GitHub CLI manual: `gh attestation verify`](https://cli.github.com/manual/gh_attestation_verify)
