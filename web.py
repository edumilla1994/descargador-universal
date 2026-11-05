# -*- coding: utf-8 -*-
"""
Web local del Descargador Universal.

Se abre en el navegador del PC y tambien en el movil si esta en la misma Wi-Fi.
Usa el mismo motor yt-dlp + ffmpeg que la app de escritorio.
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import uuid
import webbrowser
import zipfile
from pathlib import Path

from flask import Flask, Response, abort, jsonify, render_template, request, send_file

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from descargar import (  # noqa: E402
    CALIDADES, GANANCIAS, VERSION_APP, construir_comando, entorno,
    procesar_registro, texto_ganancia,
)

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
MAX_JOBS = 2
TTL = 3600

app = Flask(__name__, template_folder=str(BASE / "templates"), static_folder=str(BASE / "static"))
app.json.ensure_ascii = False

JOBS: dict[str, "Trabajo"] = {}
LOCK = threading.Lock()
INFO = {"lan": False, "ip": "127.0.0.1", "puerto": 8080}
CLAVE: str | None = None


class Trabajo:
    def __init__(self, url: str, calidad: str, ganancia: float) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.url = url
        self.calidad = calidad
        self.ganancia = ganancia
        self.carpeta = Path(tempfile.mkdtemp(prefix="descweb_"))
        self.registro = self.carpeta / "_registro.txt"
        self.proceso: subprocess.Popen | None = None
        self.estado = "esperando"
        self.pct = 0.0
        self.velocidad = ""
        self.archivo: str | None = None
        self.error: str | None = None
        self.detalle = ""
        self.cancelado = False
        self.creado = time.time()
        self.hilo = threading.Thread(target=self._trabajar, daemon=True)

    def _trabajar(self) -> None:
        self.estado = "descargando"
        cmd = construir_comando(
            [self.url], self.carpeta, self.calidad, None, False, False,
            registro=self.registro,
        )
        try:
            self.proceso = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="replace", env=entorno(),
                creationflags=CREATE_NO_WINDOW,
            )
            assert self.proceso.stdout is not None
            for linea in self.proceso.stdout:
                linea = linea.rstrip()
                if not linea:
                    continue
                self.detalle = (self.detalle + linea + "\n")[-4000:]
                m = re.search(r"\[download\]\s+(\d+(?:\.\d+)?)%", linea)
                if m:
                    self.pct = float(m.group(1))
                    vel = re.search(r"at\s+([\d.]+\s*[KMG]iB/s)", linea)
                    self.velocidad = vel.group(1) if vel else ""
            codigo = self.proceso.wait()
        except Exception as exc:  # noqa: BLE001
            self.estado = "error"
            self.error = str(exc)
            return
        finally:
            self.proceso = None

        if self.cancelado:
            self.estado = "cancelado"
            return
        if codigo != 0:
            self.estado = "error"
            self.error = "No se pudo descargar. Revisa el enlace o el registro."
            return

        self.estado = "procesando"
        self.pct = 100
        self.velocidad = ""
        try:
            resultados = procesar_registro(self.registro, self.ganancia)
            archivos = [Path(ruta) for ruta, _ in resultados if Path(ruta).is_file()]
            if not archivos:
                archivos = [
                    f for f in self.carpeta.iterdir()
                    if f.is_file() and f.name != "_registro.txt"
                    and f.suffix.lower() not in (".part", ".ytdl", ".json")
                ]
            if not archivos:
                self.estado = "error"
                self.error = "No se genero ningun archivo."
                return
            if len(archivos) == 1:
                self.archivo = archivos[0].name
            else:
                destino = self.carpeta / "descarga.zip"
                with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as paquete:
                    for f in archivos:
                        paquete.write(f, f.name)
                self.archivo = destino.name
            self.estado = "listo"
        except Exception as exc:  # noqa: BLE001
            self.estado = "error"
            self.error = f"Error al convertir: {exc}"
        finally:
            self.registro.unlink(missing_ok=True)

    def cancelar(self) -> None:
        self.cancelado = True
        if self.proceso and self.proceso.poll() is None:
            try:
                self.proceso.terminate()
            except Exception:
                pass

    def a_dict(self) -> dict:
        return {
            "id": self.id,
            "estado": self.estado,
            "pct": round(self.pct, 1),
            "velocidad": self.velocidad,
            "archivo": self.archivo,
            "error": self.error,
            "calidad": self.calidad,
            "ganancia": self.ganancia,
            "detalle": self.detalle[-800:] if self.estado == "error" else "",
        }


def _ip_lan() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def _ip_cliente() -> str:
    """IP real, teniendo en cuenta el tunel de Cloudflare."""
    cf = request.headers.get("CF-Connecting-IP")
    if cf:
        return cf.strip()
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or ""


def _es_local() -> bool:
    return _ip_cliente() in ("127.0.0.1", "::1")


def _puerto_libre(preferido: int, host: str) -> int:
    for puerto in range(preferido, preferido + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, puerto))
                return puerto
            except OSError:
                continue
    raise SystemExit(f"No encontre un puerto libre desde {preferido}.")


def _es_nuestro(puerto: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{puerto}/api/info", timeout=1.5) as r:
            datos = json.loads(r.read().decode("utf-8"))
        return datos.get("app") == "descargador"
    except Exception:
        return False


def _ruta_inicio() -> Path:
    return Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "Descargador Web.vbs"


def _leer_puerto() -> int | None:
    try:
        return int((BASE / "web.puerto").read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _guardar_puerto(puerto: int) -> None:
    try:
        (BASE / "web.puerto").write_text(str(puerto), encoding="utf-8")
    except Exception:
        pass


def _borrar_puerto() -> None:
    (BASE / "web.puerto").unlink(missing_ok=True)


def _alternar_inicio() -> bool:
    if os.name != "nt":
        raise RuntimeError("Solo disponible en Windows.")
    ruta = _ruta_inicio()
    if ruta.exists():
        ruta.unlink()
        return False
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
        exe = exe[:-4] + "w.exe"
    clave = "".join(c for c in (CLAVE or "") if c.isalnum() or c in "-_")
    extra = f" --clave {clave}" if clave else ""
    contenido = (
        'Set sh = CreateObject("WScript.Shell")\r\n'
        f'sh.Run """{exe}"" ""{BASE / "web.py"}"" --lan{extra}", 0, False\r\n'
    )
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding="utf-8")
    return True


@app.after_request
def _cabeceras(resp):
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


@app.before_request
def _auth():
    if not CLAVE:
        return None
    auth = request.authorization
    if not auth or auth.username != "descargador" or auth.password != CLAVE:
        return Response("Acceso restringido", 401, {"WWW-Authenticate": 'Basic realm="Descargador"'})
    return None


@app.get("/")
def inicio():
    return render_template("index.html", version=VERSION_APP)


@app.get("/api/info")
def api_info():
    local = _es_local()
    return jsonify(
        app="descargador",
        lan=bool(INFO["lan"]),
        ip=INFO["ip"],
        puerto=INFO["puerto"],
        local=local,
        inicio=_ruta_inicio().exists() if os.name == "nt" else False,
        version=VERSION_APP,
    )


@app.post("/api/descargar")
def api_descargar():
    datos = request.get_json(silent=True) or {}
    url = str(datos.get("url", "")).strip()
    if not url:
        return jsonify(error="Pega un enlace primero."), 400
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    if not re.match(r"^https?://[^\s/]+\.[^\s/]+", url, re.I):
        return jsonify(error="El enlace no es valido."), 400

    calidad = str(datos.get("calidad", "mejor"))
    if calidad not in CALIDADES:
        calidad = "mejor"
    try:
        ganancia = float(datos.get("ganancia", 1.0))
    except (TypeError, ValueError):
        ganancia = 1.0
    if ganancia not in GANANCIAS:
        ganancia = 1.0

    with LOCK:
        activos = sum(1 for j in JOBS.values() if j.estado in ("esperando", "descargando", "procesando"))
        if activos >= MAX_JOBS:
            return jsonify(error="Ya hay 2 descargas en curso. Espera un momento."), 429
        trabajo = Trabajo(url, calidad, ganancia)
        JOBS[trabajo.id] = trabajo
        trabajo.hilo.start()
    return jsonify(id=trabajo.id)


@app.get("/api/estado/<jid>")
def api_estado(jid: str):
    trabajo = JOBS.get(jid)
    if not trabajo:
        return jsonify(error="Esa descarga no existe."), 404
    return jsonify(trabajo.a_dict())


@app.get("/api/archivo/<jid>")
def api_archivo(jid: str):
    trabajo = JOBS.get(jid)
    if not trabajo or not trabajo.archivo:
        abort(404)
    ruta = (trabajo.carpeta / trabajo.archivo).resolve()
    if ruta.parent != trabajo.carpeta.resolve() or not ruta.is_file():
        abort(404)
    return send_file(ruta, as_attachment=True, download_name=trabajo.archivo, max_age=0)


@app.post("/api/cancelar/<jid>")
def api_cancelar(jid: str):
    trabajo = JOBS.get(jid)
    if not trabajo:
        return jsonify(error="Esa descarga no existe."), 404
    trabajo.cancelar()
    return jsonify(ok=True)


@app.get("/api/qr")
def api_qr():
    if not INFO["lan"]:
        abort(404)
    import segno

    url = f"http://{INFO['ip']}:{INFO['puerto']}"
    qr = segno.make(url, error="m")
    buffer = io.BytesIO()
    qr.save(buffer, kind="svg", scale=4, border=2, dark="#0f172a")
    return Response(buffer.getvalue(), mimetype="image/svg+xml")


@app.post("/api/inicio")
def api_inicio():
    if not _es_local():
        return jsonify(error="Solo desde el PC."), 403
    if request.headers.get("X-Descargador") != "1":
        return jsonify(error="Peticion no valida."), 403
    try:
        estado = _alternar_inicio()
    except Exception as exc:  # noqa: BLE001
        return jsonify(error=str(exc)), 400
    return jsonify(ok=True, inicio=estado)


@app.post("/api/detener")
def api_detener():
    if not _es_local():
        return jsonify(error="Solo desde el PC."), 403
    if request.headers.get("X-Descargador") != "1":
        return jsonify(error="Peticion no valida."), 403
    _borrar_puerto()
    threading.Timer(0.6, lambda: os._exit(0)).start()
    return jsonify(ok=True)


def _limpiar() -> None:
    while True:
        time.sleep(300)
        ahora = time.time()
        with LOCK:
            for jid, trabajo in list(JOBS.items()):
                if trabajo.estado in ("listo", "error", "cancelado") and ahora - trabajo.creado > TTL:
                    shutil.rmtree(trabajo.carpeta, ignore_errors=True)
                    JOBS.pop(jid, None)


def main() -> None:
    global CLAVE

    p = argparse.ArgumentParser(description="Web local del Descargador Universal.")
    p.add_argument("--puerto", type=int, default=8080, help="Puerto (por defecto 8080)")
    p.add_argument("--lan", action="store_true", help="Permitir acceso desde el movil en la misma Wi-Fi")
    p.add_argument("--abrir", action="store_true", help="Abrir el navegador al iniciar")
    p.add_argument("--clave", default=None, help="Pedir usuario 'descargador' y esta clave")
    args = p.parse_args()

    CLAVE = args.clave or None

    for existente in dict.fromkeys([args.puerto, _leer_puerto()]):
        if existente and _es_nuestro(existente):
            url = f"http://127.0.0.1:{existente}"
            print(f"El servidor ya esta corriendo en {url}")
            if args.abrir:
                webbrowser.open(url)
            return

    host = "0.0.0.0" if args.lan else "127.0.0.1"
    puerto = _puerto_libre(args.puerto, host)
    ip = _ip_lan() if args.lan else "127.0.0.1"
    INFO.update({"lan": bool(args.lan), "ip": ip, "puerto": puerto})
    _guardar_puerto(puerto)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(BASE / "web.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    if args.lan:
        print(f"PC:     http://127.0.0.1:{puerto}")
        print(f"Movil:  http://{ip}:{puerto}   (misma Wi-Fi)")
        if not CLAVE:
            print("Aviso: sin clave, cualquiera en tu Wi-Fi puede usarla.")
    else:
        print(f"Abre: http://127.0.0.1:{puerto}")
    if CLAVE:
        print("Acceso protegido con clave (usuario: descargador).")
    print("Cierra esta ventana para detener el servidor.")

    threading.Thread(target=_limpiar, daemon=True).start()
    if args.abrir:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{puerto}")).start()
    app.run(host=host, port=puerto, threaded=True, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
