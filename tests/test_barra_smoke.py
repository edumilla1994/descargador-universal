import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
RUTA = RAIZ / "Barra.pyw"


def _cargar_barra():
    spec = importlib.util.spec_from_file_location("barra_test", RUTA)
    modulo = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


def test_barra_mini_y_completa(tmp_path, monkeypatch):
    modulo = _cargar_barra()
    monkeypatch.setattr(modulo, "version_local_ytdlp", lambda: "2026.10.26")
    monkeypatch.setattr(modulo, "CONFIG", tmp_path / "config.json")
    monkeypatch.setattr(modulo, "CONFIG_UPDATE", tmp_path / "actualizaciones.json")

    try:
        app = modulo.Barra()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Sin entorno grafico: {exc}")

    app.withdraw()
    try:
        app.update()
        assert (app.ancho, app.alto) == (480, 48)
        assert "yt-dlp" in app.menu.entrycget(0, "label")

        app.completo_var.set(True)
        app._cambiar_modo()
        app.update()
        assert (app.ancho, app.alto) == (620, 104)

        app.completo_var.set(False)
        app._cambiar_modo()
        app.update()
        assert (app.ancho, app.alto) == (480, 48)

        app._preguntar_update("9999.01.01")
        app.update()
        assert app._aviso_update is not None
        app._aviso_update.destroy()

        assert app.btn_audio.cget("text") == "A+"
        app._aviso = lambda _texto: None
        app._ciclar_ganancia()
        assert app.ganancia.get() == 1.5
        assert app.btn_audio.cget("fg") == modulo.AZUL
    finally:
        app.destroy()
