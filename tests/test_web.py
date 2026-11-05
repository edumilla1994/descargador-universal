import base64

import pytest

import web


@pytest.fixture()
def cliente():
    web.app.config.update(TESTING=True)
    with web.app.test_client() as c:
        yield c


def test_inicio(cliente):
    r = cliente.get("/")
    assert r.status_code == 200
    assert "Descargador Universal" in r.get_data(as_text=True)


def test_info(cliente):
    r = cliente.get("/api/info")
    assert r.status_code == 200
    datos = r.get_json()
    assert datos["app"] == "descargador"
    assert "version" in datos


def test_descargar_sin_url(cliente):
    r = cliente.post("/api/descargar", json={"url": ""})
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_descargar_url_invalida(cliente):
    r = cliente.post("/api/descargar", json={"url": "ftp://archivo"})
    assert r.status_code == 400


def test_estado_inexistente(cliente):
    assert cliente.get("/api/estado/noexiste").status_code == 404
    assert cliente.get("/api/archivo/noexiste").status_code == 404


def test_qr(cliente, monkeypatch):
    monkeypatch.setitem(web.INFO, "lan", False)
    assert cliente.get("/api/qr").status_code == 404

    monkeypatch.setitem(web.INFO, "lan", True)
    monkeypatch.setitem(web.INFO, "ip", "192.168.1.10")
    monkeypatch.setitem(web.INFO, "puerto", 8080)
    r = cliente.get("/api/qr")
    assert r.status_code == 200
    assert r.mimetype == "image/svg+xml"


def test_acciones_locales_protegidas(cliente):
    assert cliente.post("/api/inicio").status_code == 403
    assert cliente.post("/api/detener").status_code == 403


def test_detras_de_tunel_no_es_local(cliente):
    r = cliente.get("/api/info", headers={"CF-Connecting-IP": "203.0.113.5"})
    assert r.status_code == 200
    assert r.get_json()["local"] is False

    headers = {"CF-Connecting-IP": "203.0.113.5", "X-Descargador": "1"}
    assert cliente.post("/api/inicio", headers=headers).status_code == 403
    assert cliente.post("/api/detener", headers=headers).status_code == 403


def test_clave_basica(cliente, monkeypatch):
    monkeypatch.setattr(web, "CLAVE", "secreta")
    assert cliente.get("/api/info").status_code == 401
    credencial = base64.b64encode(b"descargador:secreta").decode()
    r = cliente.get("/api/info", headers={"Authorization": f"Basic {credencial}"})
    assert r.status_code == 200
