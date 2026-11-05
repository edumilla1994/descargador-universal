#!/usr/bin/env bash
# Compila la app y el .dmg en macOS. Debe ejecutarse EN un Mac.
# Uso: bash packaging/macos/build.sh
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$RAIZ"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Este script solo funciona en macOS." >&2
  exit 1
fi

command -v python3 >/dev/null || { echo "Falta python3."; exit 1; }
command -v ffmpeg >/dev/null || brew install ffmpeg

python3 -m venv .venv-build
source .venv-build/bin/activate
python -m pip install --upgrade pip
python -m pip install pyinstaller quickjs

mkdir -p bin
curl -fsSL -o bin/yt-dlp \
  "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos"
chmod +x bin/yt-dlp

python -m PyInstaller --noconfirm --clean --windowed --name Descargador \
  --icon "assets/icono.icns" \
  --add-binary "bin/yt-dlp:bin" \
  --collect-all quickjs \
  --contents-directory . \
  --distpath dist --workpath build \
  Barra.pyw

mkdir -p instaladores
rm -f "instaladores/DescargadorUniversal-1.1.0-macOS.dmg"
hdiutil create \
  -volname "Descargador Universal" \
  -srcfolder "dist/Descargador.app" \
  -ov -format UDZO \
  "instaladores/DescargadorUniversal-1.1.0-macOS.dmg"

echo "Listo: instaladores/DescargadorUniversal-1.1.0-macOS.dmg"
echo "Aviso: no esta firmado; en el Mac hay que abrirlo con clic derecho > Abrir."
