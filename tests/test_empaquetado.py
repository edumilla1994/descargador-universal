import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
EXE = RAIZ / "dist" / "Descargador" / "Descargador.exe"


@pytest.mark.skipif(sys.platform != "win32", reason="Solo Windows")
@pytest.mark.skipif(not EXE.exists(), reason="Sin build de Windows")
def test_exe_diagnostico():
    diagnostico = Path(os.environ["APPDATA"]) / "Descargador" / "diagnostico.txt"
    diagnostico.unlink(missing_ok=True)
    subprocess.run([str(EXE), "--diagnostico"], check=True, timeout=120)
    assert diagnostico.exists()
    texto = diagnostico.read_text(encoding="utf-8")
    assert "Empaquetado: True" in texto
    assert "yt-dlp:" in texto
    assert "ffmpeg:" in texto
