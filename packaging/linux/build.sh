#!/usr/bin/env bash
# Compila un .deb para Ubuntu/Debian usando Docker.
# Uso: bash packaging/linux/build.sh
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mkdir -p "$RAIZ/instaladores"

docker run --rm \
  -v "$RAIZ:/src:ro" \
  -v "$RAIZ/instaladores:/salida" \
  ubuntu:22.04 \
  bash /src/packaging/linux/build_en_container.sh
