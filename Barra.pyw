# -*- coding: utf-8 -*-
"""
Barra mini para descargar: solo el enlace y el boton.

Incluye actualizacion automatica de yt-dlp (el motor que arregla los bloqueos
de YouTube, Facebook, X, TikTok, etc.) y funciona en Windows, Linux y macOS.
"""

from __future__ import annotations

import ctypes
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tempfile
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox

FROZEN = bool(getattr(sys, "frozen", False))
if FROZEN:
    BASE = Path(sys.executable).resolve().parent
else:
    BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from descargar import (  # noqa: E402
    GANANCIAS, SALIDA_DEFECTO, VERSION_APP, construir_comando, descargar_ytdlp, entorno,
    hay_actualizacion, procesar_archivo, texto_ganancia, version_local_ytdlp,
)

ES_WINDOWS = os.name == "nt"
ES_MAC = sys.platform == "darwin"

if FROZEN:
    if ES_WINDOWS:
        DIR_DATOS = Path(os.environ.get("APPDATA", Path.home())) / "Descargador"
    elif ES_MAC:
        DIR_DATOS = Path.home() / "Library" / "Application Support" / "Descargador"
    else:
        DIR_DATOS = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "descargador"
else:
    DIR_DATOS = BASE

CONFIG = DIR_DATOS / "config_gui.json"
CONFIG_UPDATE = DIR_DATOS / "actualizaciones.json"
TITULO = "Descargador rapido"
PLACEHOLDER = "Pega el enlace y pulsa Enter..."
CREATE_NO_WINDOW = 0x08000000 if ES_WINDOWS else 0

ANCHO_MINI, ALTO_MINI = 480, 48
ANCHO_COMP, ALTO_COMP = 620, 104


def _tema_claro() -> bool:
    """True si el sistema usa el tema claro (la barra de tareas tambien)."""
    try:
        if ES_WINDOWS:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as clave:
                return bool(winreg.QueryValueEx(clave, "SystemUsesLightTheme")[0])
        return os.environ.get("DESCARGADOR_TEMA", "").lower() != "oscuro"
    except Exception:
        return True


_CLARO = _tema_claro()

if _CLARO:
    FONDO = "#ffffff"
    CAMPO = "#f4f4f5"
    CAMPO_ERROR = "#fee2e2"
    BORDE = "#e4e4e7"
    TEXTO = "#18181b"
    GRIS = "#71717a"
    AZUL = "#2563eb"
    AZUL_OSCURO = "#1d4ed8"
    VERDE = "#16a34a"
    AMBAR = "#d97706"
    ROJO = "#dc2626"
else:
    FONDO = "#0f172a"
    CAMPO = "#1e293b"
    CAMPO_ERROR = "#3b1d1d"
    BORDE = "#334155"
    TEXTO = "#e5e7eb"
    GRIS = "#94a3b8"
    AZUL = "#3b82f6"
    AZUL_OSCURO = "#2563eb"
    VERDE = "#22c55e"
    AMBAR = "#f59e0b"
    ROJO = "#ef4444"

CALIDADES_UI = [
    ("Mejor calidad (video)", "mejor"),
    ("1080p", "1080"),
    ("720p", "720"),
    ("480p", "480"),
    ("Solo audio (MP3)", "audio"),
]
COOKIES_UI = [
    ("Sin cookies (recomendado para empezar)", "ninguno"),
    ("Chrome", "chrome"),
    ("Edge", "edge"),
    ("Firefox", "firefox"),
    ("Brave", "brave"),
    ("Opera", "opera"),
]


def _fuente(tam: int, negrita: bool = False) -> tuple:
    return ("Segoe UI", tam, "bold") if negrita else ("Segoe UI", tam)


class Barra(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(TITULO)
        if ES_MAC:
            try:
                self.attributes("-type", "utility")
            except tk.TclError:
                pass
        else:
            self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=FONDO, highlightthickness=1, highlightbackground=BORDE)

        self.mini = True
        self.ancho, self.alto = ANCHO_MINI, ALTO_MINI
        self.cola: queue.Queue = queue.Queue()
        self.proceso: subprocess.Popen | None = None
        self.hilo: threading.Thread | None = None
        self.cancelado = False
        self.ultimo_log: list[str] = []
        self._ph_activo = False
        self._ph_texto = PLACEHOLDER
        self._arrastre = (0, 0)

        self.actualizando = False
        self.update_disponible: str | None = None
        self.update_pendiente: str | None = None
        self.ultima_busqueda = 0.0
        self.auto_actualizar = True
        self._hilo_update: threading.Thread | None = None
        self._aviso_update: tk.Toplevel | None = None

        self.salida = tk.StringVar(value=str(SALIDA_DEFECTO))
        self.calidad = tk.StringVar(value=CALIDADES_UI[0][0])
        self.cookies = tk.StringVar(value=COOKIES_UI[0][0])
        self.playlist = tk.BooleanVar(value=False)
        self.ganancia = tk.DoubleVar(value=1.0)
        self.completo_var = tk.BooleanVar(value=False)
        self.auto_var = tk.BooleanVar(value=True)
        self.inicio_var = tk.BooleanVar(value=False)
        self.version_var = tk.StringVar(value="yt-dlp ...")

        self._cargar_config()
        self._cargar_estado_update()
        self._construir()
        self._aplicar_estilo()
        self._posicionar_inicial()
        self._menu()
        self.after(120, self._procesar_cola)
        self.after(6000, self._chequeo_inicial)
        self.protocol("WM_DELETE_WINDOW", self._salir)

    # ---------------- interfaz ----------------
    def _construir(self) -> None:
        self.caja = tk.Frame(self, bg=FONDO)
        self.caja.pack(fill="both", expand=True)

        self.fila = tk.Frame(self.caja, bg=FONDO)
        self.fila.pack(fill="x", padx=8, pady=(6, 0))

        self.btn = tk.Button(
            self.fila, text="↓", command=self._accion_principal,
            bg=AZUL, fg="white", activebackground=AZUL_OSCURO, activeforeground="white",
            bd=0, relief="flat", font=("Segoe UI", 13, "bold"), width=3,
            cursor="hand2", takefocus=False,
        )
        self.btn.pack(side="left")

        self.entrada = tk.Entry(
            self.fila, bg=CAMPO, fg=TEXTO, insertbackground=TEXTO, relief="flat",
            font=_fuente(10), bd=6,
        )
        self.entrada.pack(side="left", fill="x", expand=True, padx=6, ipady=2)
        self.entrada.bind("<Return>", lambda _e: self._accion_principal())
        self.entrada.bind("<FocusIn>", self._quitar_placeholder)
        self.entrada.bind("<FocusOut>", self._poner_placeholder)

        self.btn_audio = tk.Label(self.fila, text="A+", bg=FONDO, fg=GRIS,
                                  font=_fuente(9, True), width=2, cursor="hand2")
        self.btn_audio.pack(side="left", padx=(0, 2))
        self.btn_audio.bind("<Button-1>", lambda _e: self._ciclar_ganancia())
        self.btn_audio.bind("<Enter>", lambda _e: self.btn_audio.config(fg=TEXTO))
        self.btn_audio.bind("<Leave>", lambda _e: self.btn_audio.config(fg=self._color_audio()))

        self.btn_config = tk.Label(self.fila, text="⚙", bg=FONDO, fg=GRIS,
                                   font=_fuente(12), width=3, cursor="hand2")
        self.btn_config.pack(side="left")
        self.btn_config.bind("<Button-1>", self._menu_en_boton)
        self.btn_config.bind("<Enter>", lambda _e: self.btn_config.config(fg=TEXTO))
        self.btn_config.bind("<Leave>", lambda _e: self.btn_config.config(fg=self._color_gear()))

        self.lienzo = tk.Canvas(self.caja, height=3, bg=FONDO, highlightthickness=0)
        self.lienzo.pack(fill="x", padx=8, pady=(6, 0))
        self._barra = self.lienzo.create_rectangle(0, 0, 0, 3, fill=AZUL, width=0)

        self.pie = tk.Frame(self.caja, bg=FONDO)
        self.estado = tk.Label(self.pie, text="Listo. Pega un enlace.", bg=FONDO, fg=GRIS,
                               font=_fuente(9), anchor="w")
        self.estado.pack(side="left", fill="x", expand=True)

        for widget in (self, self.caja, self.fila):
            widget.bind("<ButtonPress-1>", self._empezar_arrastre)
            widget.bind("<B1-Motion>", self._mover)
        self.lienzo.bind("<ButtonPress-1>", self._empezar_arrastre)
        self.lienzo.bind("<B1-Motion>", self._mover)

        self._poner_placeholder()
        self._pintar_audio()

    def _aplicar_estilo(self) -> None:
        if self.mini:
            self.entrada.config(font=_fuente(10), bd=6)
            self.entrada.pack_configure(ipady=2)
            self.btn.config(font=("Segoe UI", 13, "bold"))
            self.fila.pack_configure(pady=(3, 0), padx=8)
            self.lienzo.pack_configure(pady=(3, 0), padx=8)
            if self.pie.winfo_ismapped():
                self.pie.pack_forget()
            self.ancho, self.alto = ANCHO_MINI, ALTO_MINI
        else:
            self.entrada.config(font=_fuente(11), bd=8)
            self.entrada.pack_configure(ipady=4)
            self.btn.config(font=("Segoe UI", 15, "bold"))
            self.fila.pack_configure(pady=(10, 0), padx=10)
            self.lienzo.pack_configure(pady=(8, 0), padx=10)
            if not self.pie.winfo_ismapped():
                self.pie.pack(fill="x", padx=12, pady=(4, 8))
            self.ancho, self.alto = ANCHO_COMP, ALTO_COMP

    # ---------------- posicion / arrastre ----------------
    def _area_trabajo(self) -> tuple[int, int, int, int]:
        if ES_WINDOWS:
            try:
                from ctypes import wintypes

                class RECT(ctypes.Structure):
                    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

                r = RECT()
                ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)
                return r.left, r.top, r.right, r.bottom
            except Exception:
                pass
        return 0, 0, self.winfo_screenwidth(), self.winfo_screenheight()

    def _margen_inferior(self) -> int:
        if ES_WINDOWS:
            return 2
        return 80 if ES_MAC else 60

    def _posicionar_inicial(self) -> None:
        _, _, derecha, abajo = self._area_trabajo()
        x = derecha - self.ancho - 12
        y = abajo - self.alto - self._margen_inferior()
        self.geometry(f"{self.ancho}x{self.alto}+{x}+{y}")

    def _cambiar_modo(self) -> None:
        ancho_anterior, alto_anterior = self.ancho, self.alto
        self.mini = not bool(self.completo_var.get())
        self._aplicar_estilo()
        derecha = self.winfo_x() + ancho_anterior
        abajo = self.winfo_y() + alto_anterior
        x = derecha - self.ancho
        y = abajo - self.alto
        self.geometry(f"{self.ancho}x{self.alto}+{max(0, x)}+{max(0, y)}")
        self._guardar_config()

    def _empezar_arrastre(self, evento) -> None:
        self._arrastre = (evento.x_root - self.winfo_x(), evento.y_root - self.winfo_y())

    def _mover(self, evento) -> None:
        self.geometry(f"+{evento.x_root - self._arrastre[0]}+{evento.y_root - self._arrastre[1]}")

    # ---------------- config ----------------
    def _cargar_config(self) -> None:
        try:
            datos = json.loads(CONFIG.read_text(encoding="utf-8"))
        except Exception:
            return
        if datos.get("salida"):
            self.salida.set(datos["salida"])
        for etiqueta, valor in CALIDADES_UI:
            if datos.get("calidad") == valor:
                self.calidad.set(etiqueta)
        for etiqueta, valor in COOKIES_UI:
            if datos.get("cookies") == valor:
                self.cookies.set(etiqueta)
        if "mini" in datos:
            self.mini = bool(datos["mini"])
            self.completo_var.set(not self.mini)
        if "playlist" in datos:
            self.playlist.set(bool(datos["playlist"]))
        try:
            valor = float(datos.get("ganancia", 1.0))
            if valor in GANANCIAS:
                self.ganancia.set(valor)
        except (TypeError, ValueError):
            pass
        self.inicio_var.set(self._en_inicio())

    def _guardar_config(self) -> None:
        datos = {
            "salida": self.salida.get(),
            "calidad": dict(CALIDADES_UI).get(self.calidad.get(), "mejor"),
            "cookies": dict(COOKIES_UI).get(self.cookies.get(), "ninguno"),
            "mini": self.mini,
            "playlist": bool(self.playlist.get()),
            "ganancia": float(self.ganancia.get()),
        }
        try:
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            CONFIG.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _cargar_estado_update(self) -> None:
        try:
            datos = json.loads(CONFIG_UPDATE.read_text(encoding="utf-8"))
        except Exception:
            datos = {}
        self.auto_actualizar = bool(datos.get("auto", True))
        self.auto_var.set(self.auto_actualizar)
        try:
            self.ultima_busqueda = float(datos.get("ultima_busqueda", 0) or 0)
        except (TypeError, ValueError):
            self.ultima_busqueda = 0.0

    def _guardar_estado_update(self) -> None:
        datos = {
            "auto": bool(self.auto_actualizar),
            "ultima_busqueda": self.ultima_busqueda,
        }
        try:
            CONFIG_UPDATE.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_UPDATE.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ---------------- entrada ----------------
    def _poner_placeholder(self, _evento=None) -> None:
        if not self.entrada.get().strip():
            self._ph_activo = True
            self.entrada.delete(0, "end")
            self.entrada.insert(0, self._ph_texto)
            self.entrada.config(fg=GRIS)
        else:
            self._ph_activo = False

    def _quitar_placeholder(self, _evento=None) -> None:
        self.entrada.config(bg=CAMPO)
        if self._ph_activo:
            self._ph_activo = False
            self.entrada.delete(0, "end")
            self.entrada.config(fg=TEXTO)

    def _url(self) -> str:
        return "" if self._ph_activo else self.entrada.get().strip()

    def _reset_placeholder(self) -> None:
        self._ph_texto = PLACEHOLDER
        self.entrada.delete(0, "end")
        self._poner_placeholder()

    def _color_audio(self) -> str:
        try:
            return AZUL if float(self.ganancia.get()) > 1.001 else GRIS
        except (TypeError, ValueError):
            return GRIS

    def _pintar_audio(self) -> None:
        try:
            self.btn_audio.config(fg=self._color_audio())
        except tk.TclError:
            pass

    def _ciclar_ganancia(self) -> None:
        actual = float(self.ganancia.get())
        try:
            indice = (GANANCIAS.index(actual) + 1) % len(GANANCIAS)
        except ValueError:
            indice = 0
        self.ganancia.set(GANANCIAS[indice])
        self._al_cambiar_ganancia()
        self._aviso(f"Volumen {texto_ganancia(GANANCIAS[indice])}")

    def _al_cambiar_ganancia(self) -> None:
        self._guardar_config()
        self._pintar_audio()

    def _aviso(self, texto: str) -> None:
        anterior = getattr(self, "_aviso_win", None)
        if anterior is not None:
            try:
                anterior.destroy()
            except tk.TclError:
                pass
        ven = tk.Toplevel(self)
        ven.overrideredirect(True)
        ven.attributes("-topmost", True)
        tk.Label(ven, text=texto, bg=AZUL, fg="white", font=_fuente(9, True),
                 padx=10, pady=5).pack()
        x = max(0, self.btn_audio.winfo_rootx() - 30)
        y = max(0, self.winfo_rooty() - 34)
        ven.geometry(f"+{x}+{y}")
        self._aviso_win = ven
        ven.after(1600, ven.destroy)

    # ---------------- acciones ----------------
    def _elegir_carpeta(self) -> None:
        carpeta = filedialog.askdirectory(initialdir=self.salida.get() or str(BASE))
        if carpeta:
            self.salida.set(carpeta)
            self._guardar_config()
            if not self.mini:
                self.estado.config(text="Carpeta: " + carpeta, fg=GRIS)

    def _abrir_carpeta(self) -> None:
        ruta = Path(self.salida.get() or SALIDA_DEFECTO)
        ruta.mkdir(parents=True, exist_ok=True)
        try:
            if ES_WINDOWS:
                os.startfile(ruta)  # type: ignore[attr-defined]
            elif ES_MAC:
                subprocess.Popen(["open", str(ruta)])
            else:
                subprocess.Popen(["xdg-open", str(ruta)])
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(TITULO, f"No se pudo abrir la carpeta:\n{exc}")

    def _abrir_completa(self) -> None:
        if FROZEN or not (BASE / "Descargar.pyw").exists():
            self.completo_var.set(True)
            self._cambiar_modo()
            return
        python = sys.executable
        if python.lower().endswith("pythonw.exe"):
            exe = python
        else:
            exe = python[:-4] + "w.exe" if python.lower().endswith("python.exe") else python
        try:
            subprocess.Popen([exe, str(BASE / "Descargar.pyw")],
                             creationflags=CREATE_NO_WINDOW, cwd=str(BASE))
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(TITULO, f"No se pudo abrir la ventana completa:\n{exc}")

    def _pegar(self) -> None:
        try:
            texto = self.clipboard_get().strip()
        except tk.TclError:
            return
        if texto:
            self._quitar_placeholder()
            self.entrada.delete(0, "end")
            self.entrada.insert(0, texto.splitlines()[0])
            self.entrada.icursor("end")

    def _ver_log(self) -> None:
        ven = tk.Toplevel(self)
        ven.title("Registro")
        ven.geometry("760x420")
        ven.configure(bg=FONDO)
        texto = tk.Text(ven, bg=CAMPO, fg=TEXTO, insertbackground=TEXTO,
                        font=("Consolas", 9), relief="flat", wrap="word")
        scroll = tk.Scrollbar(ven, command=texto.yview)
        texto.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        texto.pack(fill="both", expand=True, padx=8, pady=8)
        texto.insert("1.0", "\n".join(self.ultimo_log[-300:]) or "Sin registro.")
        texto.configure(state="disabled")

    # ---------------- menu ----------------
    def _menu(self) -> None:
        self.menu = tk.Menu(self, tearoff=0, bg=FONDO, fg=TEXTO,
                            activebackground=AZUL, activeforeground="white", font=_fuente(9))

        self.menu.add_command(label="yt-dlp ...", state="disabled")
        self.menu.add_separator()
        self.menu.add_command(label="Buscar actualizaciones", command=lambda: self._buscar_updates(True))
        self.menu.add_checkbutton(label="Actualizar yt-dlp automaticamente",
                                  variable=self.auto_var, command=self._cambiar_auto)
        self.menu.add_separator()

        cal = tk.Menu(self.menu, tearoff=0, bg=FONDO, fg=TEXTO,
                      activebackground=AZUL, activeforeground="white", font=_fuente(9))
        for etiqueta, _valor in CALIDADES_UI:
            cal.add_radiobutton(label=etiqueta, variable=self.calidad, value=etiqueta,
                                command=self._guardar_config)
        self.menu.add_cascade(label="Calidad", menu=cal)

        cook = tk.Menu(self.menu, tearoff=0, bg=FONDO, fg=TEXTO,
                       activebackground=AZUL, activeforeground="white", font=_fuente(9))
        for etiqueta, _valor in COOKIES_UI:
            cook.add_radiobutton(label=etiqueta, variable=self.cookies, value=etiqueta,
                                 command=self._guardar_config)
        self.menu.add_cascade(label="Cookies", menu=cook)

        vol = tk.Menu(self.menu, tearoff=0, bg=FONDO, fg=TEXTO,
                      activebackground=AZUL, activeforeground="white", font=_fuente(9))
        for valor, etiqueta in (
            (1.0, "Normal (sin cambios)"),
            (1.5, "+50%"),
            (2.0, "+100% (doble)"),
            (3.0, "+200%"),
        ):
            vol.add_radiobutton(label=etiqueta, variable=self.ganancia, value=valor,
                                command=self._al_cambiar_ganancia)
        self.menu.add_cascade(label="Volumen del audio", menu=vol)

        self.menu.add_command(label="Carpeta de descargas...", command=self._elegir_carpeta)
        self.menu.add_checkbutton(label="Descargar playlist completa", variable=self.playlist,
                                  command=self._guardar_config)
        self.menu.add_separator()
        self.menu.add_checkbutton(label="Modo completo (con estado)", variable=self.completo_var,
                                  command=self._cambiar_modo)
        if not FROZEN:
            self.menu.add_command(label="Abrir ventana completa", command=self._abrir_completa)
        self.menu.add_command(label="Abrir carpeta de descargas", command=self._abrir_carpeta)
        self.menu.add_command(label="Ver registro", command=self._ver_log)
        self.menu.add_separator()
        etiqueta_inicio = "Iniciar con Windows" if ES_WINDOWS else "Iniciar al encender"
        self.menu.add_checkbutton(label=etiqueta_inicio, variable=self.inicio_var,
                                  command=self._alternar_inicio)
        self.menu.add_separator()
        self.menu.add_command(label="Pegar del portapapeles", command=self._pegar)
        self.menu.add_command(label="Salir", command=self._salir)

        for widget in (self, self.caja, self.fila, self.lienzo, self.entrada, self.estado, self.btn_audio):
            widget.bind("<Button-3>", self._mostrar_menu)
        if ES_MAC:
            for widget in (self, self.caja, self.fila, self.lienzo, self.entrada, self.estado, self.btn_audio):
                widget.bind("<Button-2>", self._mostrar_menu)

        self._actualizar_etiqueta_version(version_local_ytdlp())

    def _actualizar_etiqueta_version(self, version: str | None) -> None:
        if version:
            self.version_var.set(f"yt-dlp {version}")
        try:
            self.menu.entryconfig(0, label=self.version_var.get())
        except tk.TclError:
            pass

    def _menu_en_boton(self, _evento=None) -> None:
        x = self.btn_config.winfo_rootx()
        y = self.btn_config.winfo_rooty() + self.btn_config.winfo_height()
        try:
            self.menu.tk_popup(x, y)
        except tk.TclError:
            pass

    def _mostrar_menu(self, evento) -> None:
        try:
            self.menu.tk_popup(evento.x_root, evento.y_root)
        finally:
            try:
                self.menu.grab_release()
            except tk.TclError:
                pass

    # ---------------- inicio con el sistema ----------------
    def _ruta_inicio(self) -> Path:
        if ES_WINDOWS:
            return Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "Descargador rapido.vbs"
        if ES_MAC:
            return Path.home() / "Library" / "LaunchAgents" / "com.descargador.barra.plist"
        return Path.home() / ".config" / "autostart" / "descargador.desktop"

    def _en_inicio(self) -> bool:
        return self._ruta_inicio().exists()

    def _comando_inicio(self) -> tuple[str, list[str]]:
        if FROZEN:
            return str(sys.executable), []
        exe = sys.executable
        if ES_WINDOWS and exe.lower().endswith("python.exe"):
            exe = exe[:-4] + "w.exe"
        return exe, [str(BASE / "Barra.pyw")]

    def _alternar_inicio(self) -> None:
        ruta = self._ruta_inicio()
        try:
            if ruta.exists():
                ruta.unlink()
                return
            ruta.parent.mkdir(parents=True, exist_ok=True)
            exe, args = self._comando_inicio()
            if ES_WINDOWS:
                contenido = (
                    'Set sh = CreateObject("WScript.Shell")\r\n'
                    f'sh.Run """{exe}"" ""{args[0] if args else ""}""", 0, False\r\n'
                ) if args else (
                    'Set sh = CreateObject("WScript.Shell")\r\n'
                    f'sh.Run """{exe}""", 0, False\r\n'
                )
            elif ES_MAC:
                argumentos = "".join(f"<string>{parte}</string>" for parte in [exe, *args])
                contenido = (
                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                    '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                    '<plist version="1.0"><dict>\n'
                    '<key>Label</key><string>com.descargador.barra</string>\n'
                    f'<key>ProgramArguments</key><array>{argumentos}</array>\n'
                    '<key>RunAtLoad</key><true/>\n'
                    '</dict></plist>\n'
                )
            else:
                comando = " ".join([f'"{exe}"', *[f'"{a}"' for a in args]])
                contenido = (
                    "[Desktop Entry]\n"
                    "Type=Application\n"
                    "Name=Descargador\n"
                    f"Exec={comando}\n"
                    "Terminal=false\n"
                    "X-GNOME-Autostart-enabled=true\n"
                )
            ruta.write_text(contenido, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(TITULO, f"No se pudo cambiar el inicio automatico:\n{exc}")

    # ---------------- actualizaciones ----------------
    def _color_gear(self) -> str:
        if self.actualizando:
            return AZUL
        if self.update_disponible:
            return AMBAR
        return GRIS

    def _pintar_gear(self) -> None:
        self.btn_config.config(fg=self._color_gear())

    def _chequeo_inicial(self) -> None:
        ahora = time.time()
        if self.ultima_busqueda and ahora - self.ultima_busqueda < 86400:
            return
        self._buscar_updates(False)

    def _cambiar_auto(self) -> None:
        self.auto_actualizar = bool(self.auto_var.get())
        self._guardar_estado_update()
        if self.auto_actualizar and self.update_disponible:
            self._instalar_update(self.update_disponible)

    def _buscar_updates(self, manual: bool) -> None:
        if self._hilo_update and self._hilo_update.is_alive():
            return
        if manual:
            self.estado.config(text="Buscando actualizaciones...", fg=GRIS)
        self._hilo_update = threading.Thread(target=self._trabajo_buscar, args=(manual,), daemon=True)
        self._hilo_update.start()

    def _trabajo_buscar(self, manual: bool) -> None:
        try:
            hay, local, remota = hay_actualizacion()
            self.cola.put(("update_check", (hay, local, remota, manual)))
        except Exception as exc:  # noqa: BLE001
            self.cola.put(("update_error", (str(exc), manual)))

    def _resultado_busqueda(self, hay: bool, local: str | None, remota: str | None, manual: bool) -> None:
        self.ultima_busqueda = time.time()
        self._guardar_estado_update()
        self._actualizar_etiqueta_version(local)
        if not remota:
            if manual:
                messagebox.showwarning(TITULO, "No se pudo comprobar la ultima version.\nRevisa tu conexion a Internet.")
            self.estado.config(text="Sin conexion para comprobar actualizaciones.", fg=GRIS)
            return
        if not hay:
            self.update_disponible = None
            self._pintar_gear()
            self.estado.config(text=f"yt-dlp esta al dia ({local or remota}).", fg=VERDE)
            if manual:
                messagebox.showinfo(TITULO, f"Ya tienes la ultima version de yt-dlp.\n\nVersion: {local or remota}")
            return

        self.update_disponible = remota
        self._pintar_gear()
        self.estado.config(text=f"Nueva version de yt-dlp: {remota}", fg=AMBAR)
        self._registrar(f"Actualizacion disponible: {local or '?'} -> {remota}")
        if self.auto_actualizar:
            self._instalar_update(remota)
        else:
            self._preguntar_update(remota)

    def _instalar_update(self, version: str) -> None:
        if self.actualizando:
            return
        if self.proceso and self.proceso.poll() is None:
            self.update_pendiente = version
            self._registrar("Actualizacion en espera: hay una descarga en curso.")
            return
        self.actualizando = True
        self.update_pendiente = None
        self._pintar_gear()
        self.estado.config(text=f"Actualizando yt-dlp a {version}...", fg=GRIS)
        threading.Thread(target=self._trabajo_instalar, daemon=True).start()

    def _trabajo_instalar(self) -> None:
        def progreso(leido: int, total: int) -> None:
            self.cola.put(("update_pct", (leido, total)))

        try:
            nueva = descargar_ytdlp(progreso=progreso)
            self.cola.put(("update_ok", nueva))
        except Exception as exc:  # noqa: BLE001
            self.cola.put(("update_fallo", str(exc)))

    def _update_ok(self, version: str) -> None:
        self.actualizando = False
        self.update_disponible = None
        self._actualizar_etiqueta_version(version)
        self._registrar(f"yt-dlp actualizado a {version}.")
        self.estado.config(text=f"yt-dlp actualizado a {version}.", fg=VERDE)
        self.btn_config.config(fg=VERDE)
        self.after(3000, self._pintar_gear)

    def _update_fallo(self, error: str) -> None:
        self.actualizando = False
        self._pintar_gear()
        self._registrar(f"Fallo al actualizar yt-dlp: {error}")
        self.estado.config(text="No se pudo actualizar yt-dlp. Revisa el registro.", fg=ROJO)

    def _preguntar_update(self, version: str) -> None:
        if self._aviso_update and self._aviso_update.winfo_exists():
            return
        ven = tk.Toplevel(self)
        self._aviso_update = ven
        ven.title("Actualizacion disponible")
        ven.configure(bg=FONDO)
        ven.attributes("-topmost", True)
        ven.resizable(False, False)
        ancho, alto = 420, 132
        x = self.winfo_rootx()
        y = max(0, self.winfo_rooty() - alto - 10)
        ven.geometry(f"{ancho}x{alto}+{x}+{y}")

        tk.Label(ven, text=f"Hay una version nueva de yt-dlp ({version}).",
                 bg=FONDO, fg=TEXTO, font=_fuente(10, True), anchor="w").pack(
            fill="x", padx=16, pady=(16, 2))
        tk.Label(ven, text="Actualizar arregla los bloqueos de las redes.",
                 bg=FONDO, fg=GRIS, font=_fuente(9), anchor="w").pack(fill="x", padx=16)

        botones = tk.Frame(ven, bg=FONDO)
        botones.pack(fill="x", padx=16, pady=(14, 12))

        def ahora() -> None:
            ven.destroy()
            self._instalar_update(version)

        tk.Button(botones, text="Actualizar ahora", command=ahora, bg=AZUL, fg="white",
                  activebackground=AZUL_OSCURO, activeforeground="white", bd=0,
                  relief="flat", font=_fuente(9, True), padx=12, pady=5,
                  cursor="hand2").pack(side="left")
        tk.Button(botones, text="Despues", command=ven.destroy, bg=CAMPO, fg=TEXTO,
                  activebackground=BORDE, activeforeground=TEXTO, bd=0, relief="flat",
                  font=_fuente(9), padx=12, pady=5, cursor="hand2").pack(side="left", padx=8)

        ven.after(30000, lambda: ven.destroy() if ven.winfo_exists() else None)

    # ---------------- descarga ----------------
    def _accion_principal(self) -> None:
        if self.proceso and self.proceso.poll() is None:
            self._cancelar()
        else:
            self._iniciar()

    def _iniciar(self) -> None:
        if self.hilo and self.hilo.is_alive():
            return
        if self.actualizando:
            self._marcar_error("Espera: actualizando yt-dlp.")
            return
        texto = self._url()
        if not texto:
            self._marcar_error("Pega un enlace primero.")
            return

        urls = [p for p in texto.split() if p.lower().startswith(("http://", "https://"))]
        if not urls:
            urls = ["https://" + texto.split()[0]]

        salida = self.salida.get().strip() or str(SALIDA_DEFECTO)
        calidad = dict(CALIDADES_UI).get(self.calidad.get(), "mejor")
        cookies = dict(COOKIES_UI).get(self.cookies.get(), "ninguno")
        self._guardar_config()
        Path(salida).mkdir(parents=True, exist_ok=True)

        ganancia = float(self.ganancia.get())
        registro = Path(tempfile.gettempdir()) / f"descargador_{os.getpid()}_{int(time.time() * 1000)}.txt"
        registro.unlink(missing_ok=True)
        cmd = construir_comando(urls, salida, calidad, cookies, self.playlist.get(), False,
                                registro=registro)
        self.ultimo_log = []
        self.cancelado = False
        self._progreso(0)
        self.entrada.config(bg=CAMPO)
        self.estado.config(text="Iniciando...", fg=GRIS)
        self.btn.config(text="×", bg=ROJO, activebackground="#dc2626")
        self.entrada.config(state="disabled")

        self.hilo = threading.Thread(target=self._trabajar, args=(cmd, ganancia, registro), daemon=True)
        self.hilo.start()

    def _ajustar_registro(self, registro: Path, ganancia: float) -> None:
        if not registro.exists():
            return
        vistos: list[str] = []
        for linea in registro.read_text(encoding="utf-8", errors="replace").splitlines():
            ruta = linea.strip()
            if ruta and ruta not in vistos:
                vistos.append(ruta)
        for ruta in vistos:
            self.cola.put(("estado", f"Ajustando audio ({texto_ganancia(ganancia)})..."))
            final, mensaje = procesar_archivo(ruta, ganancia)
            self.cola.put(("log", f"{Path(final).name}: {mensaje}"))

    def _trabajar(self, cmd: list[str], ganancia: float, registro: Path) -> None:
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
                self.cola.put(("log", linea))
                m = re.search(r"\[download\]\s+(\d+(?:\.\d+)?)%", linea)
                if m:
                    self.cola.put(("pct", float(m.group(1))))
                    vel = re.search(r"at\s+([\d.]+\s*[KMG]iB/s)", linea)
                    texto = f"Descargando... {float(m.group(1)):.0f}%"
                    if vel:
                        texto += f" · {vel.group(1)}"
                    self.cola.put(("estado", texto))
            codigo = self.proceso.wait()
            if codigo == 0:
                try:
                    self._ajustar_registro(registro, ganancia)
                except Exception as exc:  # noqa: BLE001
                    self.cola.put(("log", f"ERROR al ajustar el audio: {exc}"))
        except Exception as exc:  # noqa: BLE001
            self.cola.put(("log", f"ERROR: {exc}"))
            codigo = 1
        finally:
            self.proceso = None
            registro.unlink(missing_ok=True)
        self.cola.put(("fin", codigo))

    def _cancelar(self) -> None:
        if self.proceso and self.proceso.poll() is None:
            self.cancelado = True
            self.estado.config(text="Cancelando...", fg=GRIS)
            try:
                self.proceso.terminate()
            except Exception:
                pass

    def _progreso(self, pct: float) -> None:
        ancho = self.lienzo.winfo_width() or (self.ancho - 16)
        self.lienzo.coords(self._barra, 0, 0, ancho * max(0.0, min(pct, 100.0)) / 100.0, 3)

    def _registrar(self, texto: str) -> None:
        self.ultimo_log.append(texto)

    def _marcar_error(self, mensaje: str) -> None:
        self.estado.config(text=mensaje, fg=ROJO)
        self.entrada.config(bg=CAMPO_ERROR)
        if self.mini:
            self.entrada.delete(0, "end")
            self._ph_texto = mensaje
            self._poner_placeholder()
            self.entrada.config(fg=ROJO)

        def restaurar() -> None:
            if self.entrada.cget("state") == "normal":
                self.entrada.config(bg=CAMPO)
            if self._ph_activo and self._ph_texto == mensaje:
                self._ph_texto = PLACEHOLDER
                self.entrada.delete(0, "end")
                self.entrada.insert(0, PLACEHOLDER)
                self.entrada.config(fg=GRIS)

        self.after(6000, restaurar)

    def _procesar_cola(self) -> None:
        try:
            while True:
                tipo, valor = self.cola.get_nowait()
                if tipo == "log":
                    self.ultimo_log.append(valor)
                    if len(self.ultimo_log) > 400:
                        self.ultimo_log = self.ultimo_log[-400:]
                elif tipo == "pct":
                    self._progreso(valor)
                elif tipo == "estado":
                    self.estado.config(text=valor, fg=GRIS)
                elif tipo == "fin":
                    self._terminar(int(valor))
                elif tipo == "update_check":
                    self._resultado_busqueda(*valor)
                elif tipo == "update_error":
                    error, manual = valor
                    self._registrar(f"Error al comprobar actualizaciones: {error}")
                    self.estado.config(text="No se pudo comprobar la actualizacion.", fg=ROJO)
                    if manual:
                        messagebox.showwarning(TITULO, f"No se pudo comprobar:\n{error}")
                elif tipo == "update_pct":
                    leido, total = valor
                    if total and not self.mini:
                        self.estado.config(text=f"Actualizando yt-dlp... {leido * 100 // total}%", fg=GRIS)
                elif tipo == "update_ok":
                    self._update_ok(str(valor))
                elif tipo == "update_fallo":
                    self._update_fallo(str(valor))
        except queue.Empty:
            pass
        self.after(120, self._procesar_cola)

    def _terminar(self, codigo: int) -> None:
        self.btn.config(text="↓", bg=AZUL, activebackground=AZUL_OSCURO)
        self.entrada.config(state="normal")
        if self.cancelado:
            self.estado.config(text="Descarga cancelada.", fg=GRIS)
            self._progreso(0)
        elif codigo == 0:
            self._progreso(100)
            self.estado.config(text="Listo. Guardado en " + Path(self.salida.get()).name, fg=VERDE)
            self._reset_placeholder()
            self._destello(VERDE)
        else:
            self._progreso(0)
            self.estado.config(text="Error. Revisa el enlace o el registro.", fg=ROJO)
            self._marcar_error("Error. Revisa el enlace o el registro.")
        if self.update_pendiente:
            version = self.update_pendiente
            self.update_pendiente = None
            self.after(800, lambda: self._instalar_update(version))

    def _destello(self, color: str) -> None:
        self.btn.config(bg=color, activebackground=color)
        self.after(1200, lambda: self.btn.config(bg=AZUL, activebackground=AZUL_OSCURO))

    def _salir(self) -> None:
        self._guardar_config()
        self._guardar_estado_update()
        if self.proceso and self.proceso.poll() is None:
            try:
                self.proceso.terminate()
            except Exception:
                pass
        self.destroy()


def _instancia_unica() -> bool:
    if ES_WINDOWS:
        kernel = ctypes.windll.kernel32
        _ = kernel.CreateMutexW(None, False, "Global\\DescargadorBarraYTD")
        if kernel.GetLastError() == 183:
            hwnd = ctypes.windll.user32.FindWindowW(None, TITULO)
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 9)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            return True
        return False

    try:
        import fcntl
        import tempfile

        archivo = open(Path(tempfile.gettempdir()) / "descargador-barra.lock", "w")  # noqa: SIM115
        fcntl.flock(archivo, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _instancia_unica._lock = archivo  # type: ignore[attr-defined]
    except Exception:
        return True
    return False


def _diagnostico() -> None:
    from descargar import diagnostico

    texto = diagnostico()
    try:
        DIR_DATOS.mkdir(parents=True, exist_ok=True)
        (DIR_DATOS / "diagnostico.txt").write_text(texto, encoding="utf-8")
    except Exception:
        pass
    try:
        print(texto)
    except Exception:
        pass


def _autotest() -> None:
    """Descarga de prueba sin abrir la interfaz. Escribe autotest.txt."""
    from descargar import construir_comando, entorno, procesar_registro

    indice = sys.argv.index("--autotest")
    url = sys.argv[indice + 1] if len(sys.argv) > indice + 1 else "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    ganancia = 1.0
    if len(sys.argv) > indice + 2:
        try:
            ganancia = float(sys.argv[indice + 2])
        except ValueError:
            ganancia = 1.0

    salida = Path(tempfile.gettempdir()) / "DescargadorTest"
    salida.mkdir(parents=True, exist_ok=True)
    for archivo in salida.iterdir():
        if archivo.is_file():
            archivo.unlink()

    registro = Path(tempfile.gettempdir()) / f"autotest_{os.getpid()}.txt"
    registro.unlink(missing_ok=True)
    comando = construir_comando([url], salida, registro=registro)
    try:
        r = subprocess.run(
            comando, capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=entorno(), creationflags=CREATE_NO_WINDOW, timeout=600,
        )
        procesado = []
        if r.returncode == 0:
            for final, mensaje in procesar_registro(registro, ganancia):
                procesado.append(f"{Path(final).name}: {mensaje}")
        archivos = sorted(f.name for f in salida.iterdir() if f.is_file())
        texto = (
            f"rc={r.returncode}\n"
            f"url={url}\n"
            f"ganancia={ganancia}\n"
            f"archivos={archivos}\n"
            f"procesado={procesado}\n\n"
            f"STDOUT:\n{r.stdout[-4000:]}\n\n"
            f"STDERR:\n{r.stderr[-2000:]}\n"
        )
    except Exception as exc:  # noqa: BLE001
        texto = f"ERROR: {exc}\n"
    finally:
        registro.unlink(missing_ok=True)
    try:
        DIR_DATOS.mkdir(parents=True, exist_ok=True)
        (DIR_DATOS / "autotest.txt").write_text(texto, encoding="utf-8")
    except Exception:
        pass


def main() -> None:
    if "--diagnostico" in sys.argv:
        _diagnostico()
        return
    if "--autotest" in sys.argv:
        _autotest()
        return
    if "--actualizar" in sys.argv:
        try:
            version = descargar_ytdlp()
            mensaje = f"yt-dlp actualizado a {version}\n"
        except Exception as exc:  # noqa: BLE001
            mensaje = f"Error: {exc}\n"
        try:
            DIR_DATOS.mkdir(parents=True, exist_ok=True)
            (DIR_DATOS / "actualizacion.log").write_text(mensaje, encoding="utf-8")
        except Exception:
            pass
        return

    if _instancia_unica():
        return
    try:
        if ES_WINDOWS:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    Barra().mainloop()


if __name__ == "__main__":
    main()
