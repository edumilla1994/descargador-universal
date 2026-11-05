# -*- coding: utf-8 -*-
"""
Descargador universal basado en yt-dlp.

Sirve para YouTube, Facebook, X (Twitter), Instagram, TikTok, Twitch, Vimeo,
Reddit, SoundCloud y ~1800 sitios mas. La lista completa esta en:
https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md

El motor se puede actualizar solo desde GitHub, sin tocar Python.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

VERSION_APP = "1.0.0"
FROZEN = bool(getattr(sys, "frozen", False))

if FROZEN:
    BASE = Path(sys.executable).resolve().parent
else:
    BASE = Path(__file__).resolve().parent

BIN_DIR = BASE / "bin"
NOMBRE_YTDLP = "yt-dlp.exe" if os.name == "nt" else "yt-dlp"
NOMBRE_FFMPEG = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
YTDLP_LOCAL = BIN_DIR / NOMBRE_YTDLP
FFMPEG_LOCAL = BIN_DIR / NOMBRE_FFMPEG
SALIDA_DEFECTO = (Path.home() / "Downloads" / "Descargador") if FROZEN else (BASE / "Descargas")


def _datos_usuario() -> Path:
    """Carpeta escribible para el yt-dlp actualizado (fuera de /opt o Program Files)."""
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Descargador"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Descargador"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "descargador"


if FROZEN:
    BIN_USUARIO = _datos_usuario() / "bin"
    YTDLP_USUARIO = BIN_USUARIO / NOMBRE_YTDLP
else:
    BIN_USUARIO = BIN_DIR
    YTDLP_USUARIO = YTDLP_LOCAL

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

RELEASES_API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
PYPI_API = "https://pypi.org/pypi/yt-dlp/json"
RELEASE_FILE = {
    "nt": "yt-dlp.exe",
    "darwin": "yt-dlp_macos",
    "linux": "yt-dlp_linux",
}

CALIDADES = {
    "mejor": ["-f", "bv*+ba/b"],
    "1080": ["-f", "bv*+ba/b", "-S", "res:1080"],
    "720": ["-f", "bv*+ba/b", "-S", "res:720"],
    "480": ["-f", "bv*+ba/b", "-S", "res:480"],
    "audio": [
        "-f", "ba/b",
        "-x", "--audio-format", "mp3", "--audio-quality", "0",
        "--embed-thumbnail", "--embed-metadata",
    ],
}

NAVEGADORES = ["chrome", "edge", "firefox", "brave", "opera", "vivaldi", "chromium", "safari"]


def ejecutable_ytdlp() -> list[str]:
    """Prioriza el binario actualizado del usuario, luego el incluido y el del sistema."""
    if YTDLP_USUARIO.is_file():
        return [str(YTDLP_USUARIO)]
    if YTDLP_LOCAL.is_file():
        return [str(YTDLP_LOCAL)]
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    return [sys.executable, "-m", "yt_dlp"]


def entorno() -> dict[str, str]:
    """PATH con los bin locales incluidos y salida UTF-8."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    for carpeta in (BIN_USUARIO, BIN_DIR):
        if carpeta.is_dir():
            env["PATH"] = str(carpeta) + os.pathsep + env.get("PATH", "")
    return env


def clave_version(texto: str | None) -> tuple[int, ...]:
    numeros = [int(n) for n in re.findall(r"\d+", texto or "")[:4]]
    return tuple(numeros) or (0,)


def version_local_ytdlp() -> str | None:
    try:
        r = subprocess.run(
            ejecutable_ytdlp() + ["--version"],
            capture_output=True, text=True, timeout=30, env=entorno(),
            creationflags=CREATE_NO_WINDOW,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().splitlines()[0].strip()
    except Exception:
        pass
    return None


def version_remota_ytdlp() -> str | None:
    """Ultima version publicada. Primero GitHub, si falla PyPI."""
    cabeceras = {
        "User-Agent": f"DescargadorUniversal/{VERSION_APP}",
        "Accept": "application/vnd.github+json",
    }
    try:
        req = urllib.request.Request(RELEASES_API, headers=cabeceras)
        with urllib.request.urlopen(req, timeout=20) as resp:
            datos = json.loads(resp.read().decode("utf-8"))
        etiqueta = datos.get("tag_name")
        if etiqueta:
            return str(etiqueta).lstrip("v")
    except Exception:
        pass

    try:
        req = urllib.request.Request(PYPI_API, headers={"User-Agent": cabeceras["User-Agent"]})
        with urllib.request.urlopen(req, timeout=20) as resp:
            datos = json.loads(resp.read().decode("utf-8"))
        return str(datos["info"]["version"])
    except Exception:
        return None


def hay_actualizacion() -> tuple[bool, str | None, str | None]:
    local = version_local_ytdlp()
    remota = version_remota_ytdlp()
    if not remota:
        return False, local, remota
    if not local:
        return True, local, remota
    return clave_version(remota) > clave_version(local), local, remota


def archivo_release() -> str:
    if os.name == "nt":
        return RELEASE_FILE["nt"]
    if sys.platform == "darwin":
        return RELEASE_FILE["darwin"]
    return RELEASE_FILE["linux"]


def descargar_ytdlp(destino: str | Path | None = None, progreso=None) -> str:
    """Descarga el yt-dlp standalone y lo deja listo. Devuelve su version."""
    destino = Path(destino) if destino else YTDLP_USUARIO
    destino.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/yt-dlp/yt-dlp/releases/latest/download/{archivo_release()}"
    temporal = destino.with_name(destino.name + ".nuevo")
    if temporal.exists():
        temporal.unlink()

    req = urllib.request.Request(url, headers={"User-Agent": f"DescargadorUniversal/{VERSION_APP}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp, open(temporal, "wb") as salida:
            total = int(resp.headers.get("Content-Length") or 0)
            leido = 0
            while True:
                bloque = resp.read(1024 * 256)
                if not bloque:
                    break
                salida.write(bloque)
                leido += len(bloque)
                if progreso:
                    progreso(leido, total)
        if os.name != "nt":
            os.chmod(temporal, 0o755)

        r = subprocess.run(
            [str(temporal), "--version"],
            capture_output=True, text=True, timeout=60, env=entorno(),
            creationflags=CREATE_NO_WINDOW,
        )
        if r.returncode != 0 or not r.stdout.strip():
            raise RuntimeError("El binario descargado no responde.")
        version = r.stdout.strip().splitlines()[0].strip()
        os.replace(temporal, destino)
        return version
    except Exception:
        if temporal.exists():
            try:
                temporal.unlink()
            except OSError:
                pass
        raise


def version_ffmpeg() -> str | None:
    candidatos = []
    if FFMPEG_LOCAL.is_file():
        candidatos.append(str(FFMPEG_LOCAL))
    exe = shutil.which("ffmpeg")
    if exe and exe not in candidatos:
        candidatos.append(exe)
    for candidato in candidatos:
        try:
            r = subprocess.run(
                [candidato, "-version"],
                capture_output=True, text=True, timeout=20, env=entorno(),
                creationflags=CREATE_NO_WINDOW,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip().splitlines()[0]
        except Exception:
            continue
    return None


def diagnostico() -> str:
    lineas = [
        f"Descargador Universal {VERSION_APP}",
        f"Empaquetado: {FROZEN}",
        f"Carpeta base: {BASE}",
        f"yt-dlp: {version_local_ytdlp() or 'no encontrado'}",
        f"yt-dlp remoto: {version_remota_ytdlp() or 'sin conexion'}",
        f"ffmpeg: {version_ffmpeg() or 'no encontrado'}",
    ]
    try:
        import quickjs  # noqa: F401

        lineas.append("quickjs: incluido")
    except Exception:
        lineas.append("quickjs: no")
    lineas += [
        f"Python: {sys.version.splitlines()[0]}",
        f"Plataforma: {sys.platform}",
    ]
    return "\n".join(lineas)


def construir_comando(
    urls: list[str],
    salida: str | Path = SALIDA_DEFECTO,
    calidad: str = "mejor",
    cookies: str | None = None,
    playlist: bool = False,
    subtitulos: bool = False,
    formatos: bool = False,
) -> list[str]:
    """Arma la linea de comandos completa de yt-dlp."""
    cmd = ejecutable_ytdlp()
    cmd += [
        "--newline",
        "--no-color",
        "--windows-filenames",
        "--trim-filenames", "200",
        "--retries", "10",
        "--fragment-retries", "10",
        "--concurrent-fragments", "4",
        "--merge-output-format", "mp4/mkv",
        "--embed-metadata",
    ]

    if FFMPEG_LOCAL.is_file():
        cmd += ["--ffmpeg-location", str(FFMPEG_LOCAL)]

    # YouTube exige un motor JavaScript para resolver algunos formatos.
    runtime_js = None
    if shutil.which("deno"):
        runtime_js = "deno"
    elif shutil.which("node"):
        runtime_js = "node"
    else:
        try:
            import quickjs  # noqa: F401

            runtime_js = "quickjs"
        except Exception:
            runtime_js = None
    if runtime_js:
        cmd += ["--js-runtimes", runtime_js]

    if cookies and cookies.lower() not in ("", "ninguno", "none"):
        # Acepta un navegador (chrome, firefox...) o la ruta de un cookies.txt
        if cookies.lower().endswith(".txt") or Path(cookies).is_file():
            cmd += ["--cookies", str(Path(cookies).expanduser())]
        else:
            cmd += ["--cookies-from-browser", cookies]

    cmd += ["--yes-playlist"] if playlist else ["--no-playlist"]

    if subtitulos:
        cmd += ["--write-subs", "--embed-subs", "--sub-langs", "es.*,en.*"]

    if formatos:
        return cmd + ["-F"] + urls

    cmd += CALIDADES.get(calidad, CALIDADES["mejor"])

    plantilla = (
        "%(playlist_title).120B/%(playlist_index)03d - %(title).150B [%(id)s].%(ext)s"
        if playlist
        else "%(title).150B [%(id)s].%(ext)s"
    )
    cmd += ["-P", str(salida), "-o", plantilla]
    return cmd + urls


def descargar(
    urls: list[str],
    salida: str | Path = SALIDA_DEFECTO,
    calidad: str = "mejor",
    cookies: str | None = None,
    playlist: bool = False,
    subtitulos: bool = False,
) -> int:
    """Ejecuta la descarga y muestra el progreso en consola."""
    Path(salida).mkdir(parents=True, exist_ok=True)
    cmd = construir_comando(urls, salida, calidad, cookies, playlist, subtitulos)
    print("Ejecutando:", " ".join(cmd[:3]), "...")
    resultado = subprocess.run(cmd, env=entorno())
    if resultado.returncode == 0:
        print("\nListo. Archivos en:", Path(salida).resolve())
    return resultado.returncode


def main() -> int:
    p = argparse.ArgumentParser(
        description="Descarga video o audio de YouTube, Facebook, X, Instagram, TikTok y ~1800 sitios mas.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python descargar.py https://youtu.be/XXXX\n"
            "  python descargar.py -c 1080 https://www.facebook.com/watch?v=XXXX\n"
            "  python descargar.py -c audio --cookies firefox https://x.com/usuario/status/XXXX\n"
            "  python descargar.py --lista https://www.youtube.com/playlist?list=XXXX\n"
            "\nMantenimiento:\n"
            "  python descargar.py --diagnostico\n"
            "  python descargar.py --actualizar\n"
        ),
    )
    p.add_argument("urls", nargs="*", help="Uno o varios enlaces")
    p.add_argument("-o", "--salida", default=str(SALIDA_DEFECTO), help="Carpeta destino")
    p.add_argument("-c", "--calidad", default="mejor", choices=list(CALIDADES), help="Calidad de descarga")
    p.add_argument("--cookies", default=None, metavar="NAVEGADOR|ARCHIVO",
                   help="Cookies de un navegador (" + ", ".join(NAVEGADORES) + ") o ruta a un cookies.txt")
    p.add_argument("--lista", action="store_true", help="Descargar la playlist completa")
    p.add_argument("--subtitulos", action="store_true", help="Descargar e incrustar subtitulos")
    p.add_argument("--formatos", action="store_true", help="Solo listar los formatos disponibles")
    p.add_argument("--diagnostico", action="store_true", help="Mostrar versiones y rutas")
    p.add_argument("--actualizar", action="store_true", help="Actualizar yt-dlp a la ultima version")

    args = p.parse_args()

    if args.diagnostico:
        print(diagnostico())
        return 0

    if args.actualizar:
        try:
            version = descargar_ytdlp()
            print(f"yt-dlp actualizado a {version}")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"No se pudo actualizar: {exc}")
            return 1

    if not args.urls:
        p.error("Falta al menos un enlace (o usa --diagnostico / --actualizar).")

    if args.formatos:
        cmd = construir_comando(args.urls, args.salida, args.calidad, args.cookies,
                                args.lista, args.subtitulos, formatos=True)
        return subprocess.run(cmd, env=entorno()).returncode

    try:
        return descargar(args.urls, args.salida, args.calidad, args.cookies,
                         args.lista, args.subtitulos)
    except KeyboardInterrupt:
        print("\nCancelado.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
