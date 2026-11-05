# -*- coding: utf-8 -*-
"""
Ventana para descargar video/audio de YouTube, Facebook, X, Instagram, TikTok
y ~1800 sitios mas. Usa yt-dlp (motor) + ffmpeg (union de video y audio).
"""

from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from descargar import (  # noqa: E402
    CALIDADES, NAVEGADORES, SALIDA_DEFECTO, construir_comando, entorno,
)

CONFIG = BASE / "config_gui.json"
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

ETIQUETAS_CALIDAD = [
    ("Mejor calidad (video)", "mejor"),
    ("1080p", "1080"),
    ("720p", "720"),
    ("480p", "480"),
    ("Solo audio (MP3)", "audio"),
]

ETIQUETAS_COOKIES = [("Sin cookies (recomendado para empezar)", "ninguno")] + [
    (n.capitalize(), n) for n in ("chrome", "edge", "firefox", "brave", "opera")
]


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Descargador universal · YouTube, Facebook, X, Instagram, TikTok...")
        self.geometry("820x600")
        self.minsize(720, 540)

        self.cola: queue.Queue = queue.Queue()
        self.proceso: subprocess.Popen | None = None
        self.hilo: threading.Thread | None = None
        self.cancelado = False

        self.salida = tk.StringVar(value=str(SALIDA_DEFECTO))
        self.calidad = tk.StringVar(value=ETIQUETAS_CALIDAD[0][0])
        self.cookies = tk.StringVar(value=ETIQUETAS_COOKIES[0][0])
        self.playlist = tk.BooleanVar(value=False)
        self.subtitulos = tk.BooleanVar(value=False)
        self.estado = tk.StringVar(value="Pega uno o varios enlaces y pulsa Descargar.")

        self._cargar_config()
        self._construir_ui()
        self.after(100, self._procesar_cola)
        self.protocol("WM_DELETE_WINDOW", self._cerrar)

    # ---------- interfaz ----------
    def _construir_ui(self) -> None:
        estilo = ttk.Style(self)
        try:
            estilo.theme_use("vista")
        except tk.TclError:
            pass
        estilo.configure("Titulo.TLabel", font=("Segoe UI", 16, "bold"))
        estilo.configure("Pista.TLabel", foreground="#555555")
        estilo.configure("TButton", padding=(10, 6))
        estilo.configure("Descargar.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 8))

        marco = ttk.Frame(self, padding=16)
        marco.pack(fill="both", expand=True)

        ttk.Label(marco, text="Descargador universal", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(
            marco,
            text="YouTube · Facebook · X · Instagram · TikTok · Twitch · Vimeo · SoundCloud · ~1800 sitios",
            style="Pista.TLabel",
        ).pack(anchor="w", pady=(0, 10))

        caja = ttk.LabelFrame(marco, text="Enlaces (uno por linea)", padding=8)
        caja.pack(fill="x")
        self.txt_urls = tk.Text(caja, height=3, wrap="none", font=("Consolas", 10),
                                relief="flat", highlightthickness=1, highlightbackground="#c8c8c8")
        self.txt_urls.pack(fill="x")
        self.txt_urls.bind("<Control-Return>", lambda _e: self._iniciar())

        fila_carpeta = ttk.Frame(marco)
        fila_carpeta.pack(fill="x", pady=(10, 0))
        ttk.Label(fila_carpeta, text="Guardar en:").pack(side="left")
        ttk.Entry(fila_carpeta, textvariable=self.salida).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(fila_carpeta, text="Elegir carpeta", command=self._elegir_carpeta).pack(side="left")

        opciones = ttk.Frame(marco)
        opciones.pack(fill="x", pady=(10, 0))
        ttk.Label(opciones, text="Calidad:").pack(side="left")
        combo_calidad = ttk.Combobox(opciones, textvariable=self.calidad, state="readonly", width=26,
                                     values=[e[0] for e in ETIQUETAS_CALIDAD])
        combo_calidad.pack(side="left", padx=(6, 16))

        ttk.Label(opciones, text="Cookies:").pack(side="left")
        combo_cookies = ttk.Combobox(opciones, textvariable=self.cookies, state="readonly", width=32,
                                     values=[e[0] for e in ETIQUETAS_COOKIES])
        combo_cookies.pack(side="left", padx=(6, 16))

        ttk.Checkbutton(opciones, text="Playlist completa", variable=self.playlist).pack(side="left")
        ttk.Checkbutton(opciones, text="Subtitulos", variable=self.subtitulos).pack(side="left", padx=(16, 0))

        botones = ttk.Frame(marco)
        botones.pack(fill="x", pady=(12, 0))
        self.btn_descargar = ttk.Button(botones, text="Descargar", style="Descargar.TButton",
                                        command=self._iniciar)
        self.btn_descargar.pack(side="left")
        self.btn_cancelar = ttk.Button(botones, text="Cancelar", command=self._cancelar, state="disabled")
        self.btn_cancelar.pack(side="left", padx=8)
        ttk.Button(botones, text="Abrir carpeta", command=self._abrir_carpeta).pack(side="left")
        ttk.Button(botones, text="Actualizar yt-dlp", command=self._actualizar).pack(side="right")

        self.barra = ttk.Progressbar(marco, mode="determinate", maximum=100)
        self.barra.pack(fill="x", pady=(12, 4))
        ttk.Label(marco, textvariable=self.estado, style="Pista.TLabel").pack(anchor="w")

        registro = ttk.LabelFrame(marco, text="Registro", padding=6)
        registro.pack(fill="both", expand=True, pady=(10, 0))
        self.txt_log = tk.Text(registro, height=10, wrap="word", font=("Consolas", 9),
                               state="disabled", relief="flat", background="#f7f7f7")
        scroll = ttk.Scrollbar(registro, command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.txt_log.pack(side="left", fill="both", expand=True)

    # ---------- config ----------
    def _cargar_config(self) -> None:
        try:
            datos = json.loads(CONFIG.read_text(encoding="utf-8"))
        except Exception:
            return
        if datos.get("salida"):
            self.salida.set(datos["salida"])
        if datos.get("calidad"):
            for etiqueta, valor in ETIQUETAS_CALIDAD:
                if valor == datos["calidad"]:
                    self.calidad.set(etiqueta)
        if datos.get("cookies"):
            for etiqueta, valor in ETIQUETAS_COOKIES:
                if valor == datos["cookies"]:
                    self.cookies.set(etiqueta)

    def _guardar_config(self) -> None:
        datos = {
            "salida": self.salida.get(),
            "calidad": dict((e, v) for e, v in ETIQUETAS_CALIDAD).get(self.calidad.get(), "mejor"),
            "cookies": dict((e, v) for e, v in ETIQUETAS_COOKIES).get(self.cookies.get(), "ninguno"),
        }
        try:
            CONFIG.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ---------- acciones ----------
    def _elegir_carpeta(self) -> None:
        carpeta = filedialog.askdirectory(initialdir=self.salida.get() or str(BASE))
        if carpeta:
            self.salida.set(carpeta)

    def _abrir_carpeta(self) -> None:
        ruta = Path(self.salida.get() or SALIDA_DEFECTO)
        ruta.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(ruta)  # type: ignore[attr-defined]
        else:
            webbrowser.open(ruta.as_uri())

    def _urls(self) -> list[str]:
        texto = self.txt_urls.get("1.0", "end")
        return [linea.strip() for linea in texto.splitlines() if linea.strip()]

    def _iniciar(self) -> None:
        if self.hilo and self.hilo.is_alive():
            return
        urls = self._urls()
        if not urls:
            messagebox.showinfo("Falta el enlace", "Pega al menos un enlace para descargar.")
            return

        salida = self.salida.get().strip() or str(SALIDA_DEFECTO)
        calidad = dict((e, v) for e, v in ETIQUETAS_CALIDAD).get(self.calidad.get(), "mejor")
        cookies = dict((e, v) for e, v in ETIQUETAS_COOKIES).get(self.cookies.get(), "ninguno")

        self._guardar_config()
        Path(salida).mkdir(parents=True, exist_ok=True)
        cmd = construir_comando(urls, salida, calidad, cookies, self.playlist.get(), self.subtitulos.get())

        self._limpiar_log()
        self._log("Carpeta: " + str(Path(salida).resolve()))
        self._log("Comando: " + " ".join(cmd[:6]) + " ...\n")
        self.barra["value"] = 0
        self.cancelado = False
        self.btn_descargar.configure(state="disabled")
        self.btn_cancelar.configure(state="normal")
        self.estado.set("Iniciando descarga...")

        self.hilo = threading.Thread(target=self._trabajar, args=(cmd,), daemon=True)
        self.hilo.start()

    def _trabajar(self, cmd: list[str]) -> None:
        try:
            self.proceso = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=entorno(),
                creationflags=CREATE_NO_WINDOW,
            )
            assert self.proceso.stdout is not None
            for linea in self.proceso.stdout:
                linea = linea.rstrip()
                if linea:
                    self.cola.put(("log", linea))
                m = re.search(r"\[download\]\s+(\d+(?:\.\d+)?)%", linea)
                if m:
                    self.cola.put(("pct", float(m.group(1))))
                    velocidad = re.search(r"at\s+([\d.]+\s*[KMG]iB/s)", linea)
                    self.cola.put(("estado", "Descargando... " + (velocidad.group(1) if velocidad else "")))
            codigo = self.proceso.wait()
        except Exception as exc:  # noqa: BLE001
            self.cola.put(("log", f"ERROR: {exc}"))
            codigo = 1
        finally:
            self.proceso = None
        self.cola.put(("fin", codigo))

    def _cancelar(self) -> None:
        if self.proceso and self.proceso.poll() is None:
            self.cancelado = True
            self.estado.set("Cancelando...")
            try:
                self.proceso.terminate()
            except Exception:
                pass

    def _actualizar(self) -> None:
        if self.hilo and self.hilo.is_alive():
            return
        self._log("\nActualizando yt-dlp... (puede tardar un minuto)")
        self.estado.set("Actualizando yt-dlp...")

        def tarea() -> None:
            try:
                python = sys.executable
                if python.lower().endswith("pythonw.exe"):
                    python = python[:-6] + ".exe"
                r = subprocess.run(
                    [python, "-m", "pip", "install", "-U", "yt-dlp[default]", "curl_cffi",
                     "--disable-pip-version-check"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    env=entorno(), creationflags=CREATE_NO_WINDOW,
                )
                self.cola.put(("log", (r.stdout or "")[-1200:]))
                self.cola.put(("estado", "yt-dlp actualizado." if r.returncode == 0 else "No se pudo actualizar."))
            except Exception as exc:  # noqa: BLE001
                self.cola.put(("log", f"ERROR al actualizar: {exc}"))

        threading.Thread(target=tarea, daemon=True).start()

    # ---------- cola de mensajes ----------
    def _procesar_cola(self) -> None:
        try:
            while True:
                tipo, valor = self.cola.get_nowait()
                if tipo == "log":
                    self._log(valor)
                elif tipo == "pct":
                    self.barra["value"] = valor
                elif tipo == "estado":
                    self.estado.set(valor)
                elif tipo == "fin":
                    self._terminar(int(valor))
        except queue.Empty:
            pass
        self.after(100, self._procesar_cola)

    def _terminar(self, codigo: int) -> None:
        self.btn_descargar.configure(state="normal")
        self.btn_cancelar.configure(state="disabled")
        if self.cancelado:
            self.estado.set("Descarga cancelada.")
        elif codigo == 0:
            self.barra["value"] = 100
            self.estado.set("Listo. Archivos en: " + str(Path(self.salida.get()).resolve()))
        else:
            self.estado.set(f"Termino con errores (codigo {codigo}). Revisa el registro.")

    def _log(self, texto: str) -> None:
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", texto + "\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _limpiar_log(self) -> None:
        self.txt_log.configure(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.configure(state="disabled")

    def _cerrar(self) -> None:
        self._guardar_config()
        if self.proceso and self.proceso.poll() is None:
            self.proceso.terminate()
        self.destroy()


def main() -> None:
    try:
        if os.name == "nt":
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    App().mainloop()


if __name__ == "__main__":
    main()
