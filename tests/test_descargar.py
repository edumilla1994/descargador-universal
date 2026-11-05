import descargar


def _cmd(**kwargs):
    return descargar.construir_comando(["https://ejemplo.com/video"], **kwargs)


def test_clave_version():
    assert descargar.clave_version("2026.10.26") > descargar.clave_version("2026.09.30")
    assert descargar.clave_version("v2026.10.26") == (2026, 10, 26)
    assert descargar.clave_version(None) == (0,)


def test_calidades():
    for calidad, esperado in (
        ("mejor", "bv*+ba/b"),
        ("1080", "res:1080"),
        ("720", "res:720"),
        ("480", "res:480"),
    ):
        cmd = _cmd(calidad=calidad)
        assert "-f" in cmd
        if esperado.startswith("res"):
            assert esperado in cmd
    audio = _cmd(calidad="audio")
    assert "--audio-format" in audio
    assert "mp3" in audio


def test_cookies_navegador():
    cmd = _cmd(cookies="firefox")
    assert "--cookies-from-browser" in cmd
    assert "firefox" in cmd


def test_cookies_archivo(tmp_path):
    archivo = tmp_path / "cookies.txt"
    archivo.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    cmd = _cmd(cookies=str(archivo))
    assert "--cookies" in cmd
    assert str(archivo) in cmd


def test_playlist():
    cmd = _cmd(playlist=True)
    assert "--yes-playlist" in cmd
    plantilla = cmd[cmd.index("-o") + 1]
    assert "playlist_index" in plantilla


def test_sin_playlist():
    assert "--no-playlist" in _cmd()


def test_salida(tmp_path):
    cmd = _cmd(salida=tmp_path)
    assert str(tmp_path) in cmd
    assert "-P" in cmd


def test_quickjs_sin_node(monkeypatch):
    monkeypatch.setattr(descargar.shutil, "which", lambda _nombre: None)
    cmd = descargar.construir_comando(["https://ejemplo.com/video"])
    assert "--js-runtimes" in cmd
    assert "quickjs" in cmd


def test_hay_actualizacion(monkeypatch):
    monkeypatch.setattr(descargar, "version_local_ytdlp", lambda: "2026.10.26")
    monkeypatch.setattr(descargar, "version_remota_ytdlp", lambda: "2026.11.01")
    hay, local, remota = descargar.hay_actualizacion()
    assert hay is True
    assert local == "2026.10.26"
    assert remota == "2026.11.01"


def test_no_hay_actualizacion(monkeypatch):
    monkeypatch.setattr(descargar, "version_local_ytdlp", lambda: "2026.10.26")
    monkeypatch.setattr(descargar, "version_remota_ytdlp", lambda: "2026.10.26")
    hay, _local, _remota = descargar.hay_actualizacion()
    assert hay is False


def test_sin_conexion(monkeypatch):
    monkeypatch.setattr(descargar, "version_local_ytdlp", lambda: "2026.10.26")
    monkeypatch.setattr(descargar, "version_remota_ytdlp", lambda: None)
    hay, local, remota = descargar.hay_actualizacion()
    assert hay is False
    assert local == "2026.10.26"
    assert remota is None


def test_archivo_release():
    assert descargar.archivo_release() in {"yt-dlp.exe", "yt-dlp_linux", "yt-dlp_macos"}
