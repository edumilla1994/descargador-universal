#!/usr/bin/env python3
"""Descarga yt-dlp y ffmpeg a la carpeta bin/ para desarrollo o para el build."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from descargar import (  # noqa: E402
    BIN_DIR, NOMBRE_FFMPEG, NOMBRE_YTDLP, descargar_ytdlp, version_ffmpeg,
    version_local_ytdlp,
)

FFMPEG_WIN = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"


def asegurar_ytdlp(forzar: bool) -> None:
    destino = BIN_DIR / NOMBRE_YTDLP
    if destino.exists() and not forzar:
        print(f"yt-dlp ya esta: {version_local_ytdlp()}")
        return
    print("Descargando yt-dlp...")
    print(f"yt-dlp {descargar_ytdlp(destino)} listo")


def asegurar_ffmpeg(forzar: bool) -> None:
    if os.name != "nt":
        exe = shutil.which("ffmpeg")
        if exe:
            print(f"ffmpeg del sistema: {exe}")
        else:
            print("Falta ffmpeg. Instalalo con: sudo apt install ffmpeg  (o brew install ffmpeg)")
        return

    faltan = [n for n in ("ffmpeg.exe", "ffprobe.exe") if not (BIN_DIR / n).exists()]
    if not faltan and not forzar:
        print(f"ffmpeg ya esta: {version_ffmpeg()}")
        return

    print("Descargando ffmpeg (unos 200 MB)...")
    temporal = None
    try:
        with urllib.request.urlopen(FFMPEG_WIN, timeout=180) as respuesta:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as archivo:
                temporal = Path(archivo.name)
                shutil.copyfileobj(respuesta, archivo)
        with zipfile.ZipFile(temporal) as paquete:
            for miembro in paquete.infolist():
                nombre = Path(miembro.filename).name
                if nombre in ("ffmpeg.exe", "ffprobe.exe"):
                    with paquete.open(miembro) as origen, open(BIN_DIR / nombre, "wb") as destino:
                        shutil.copyfileobj(origen, destino)
        print(f"ffmpeg listo: {version_ffmpeg()}")
    finally:
        if temporal and temporal.exists():
            temporal.unlink()


def main() -> int:
    p = argparse.ArgumentParser(description="Descarga yt-dlp y ffmpeg para el proyecto.")
    p.add_argument("--forzar", action="store_true", help="Volver a descargar aunque existan")
    args = p.parse_args()

    BIN_DIR.mkdir(parents=True, exist_ok=True)
    asegurar_ytdlp(args.forzar)
    asegurar_ffmpeg(args.forzar)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
