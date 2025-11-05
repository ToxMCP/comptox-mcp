#!/usr/bin/env bash
# Build and validate documentation artefacts.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== Rendering model cards ==="
python "$ROOT_DIR/scripts/render_model_cards.py"

echo "=== Checking markdown links ==="
python "$ROOT_DIR/scripts/check_docs_links.py"

echo "Documentation build completed."
