#!/usr/bin/env bash
# Este script se ejecuta DENTRO del contenedor ubuntu:22.04.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  python3 python3-pip python3-tk binutils dpkg-dev ca-certificates curl libpython3.10

python3 -m pip install --no-cache-dir pyinstaller quickjs

rm -rf /work
mkdir -p /work/bin
cp /src/Barra.pyw /src/descargar.py /work/

curl -fsSL -o /work/bin/yt-dlp \
  "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux"
chmod +x /work/bin/yt-dlp

cd /work
python3 -m PyInstaller --noconfirm --clean --windowed --name Descargador \
  --add-binary "bin/yt-dlp:bin" \
  --collect-all quickjs \
  --contents-directory . \
  --distpath dist --workpath build \
  Barra.pyw

PAQUETE=/work/paquete
rm -rf "$PAQUETE"
mkdir -p \
  "$PAQUETE/DEBIAN" \
  "$PAQUETE/opt/descargador" \
  "$PAQUETE/usr/bin" \
  "$PAQUETE/usr/share/applications" \
  "$PAQUETE/usr/share/icons/hicolor/256x256/apps"

cp -a /work/dist/Descargador/. "$PAQUETE/opt/descargador/"
cp /src/packaging/linux/control "$PAQUETE/DEBIAN/control"
cp /src/packaging/linux/descargador.desktop "$PAQUETE/usr/share/applications/"
cp /src/assets/icono.png "$PAQUETE/usr/share/icons/hicolor/256x256/apps/descargador.png"

cat > "$PAQUETE/usr/bin/descargador" <<'EOF'
#!/bin/sh
exec /opt/descargador/Descargador "$@"
EOF
chmod +x "$PAQUETE/usr/bin/descargador"

dpkg-deb --build --root-owner-group "$PAQUETE" /salida/descargador_1.1.0_amd64.deb
