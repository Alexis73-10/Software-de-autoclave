"""R1 (tanda 6): hallazgos Bajos de revisores corregidos sin tocar lógica de seguridad."""
import os
import re
import threading
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]


# ── O1 SAF-05: server.py no itera cycle_manager.cycles sin copia ────────────
def test_server_itera_copia_de_cycles():
    texto = (RAIZ / "src/autoclave/backend/server.py").read_text(encoding="utf-8")
    sin_copia = [m.group(0) for m in re.finditer(r"(?<!list\()context\.cycle_manager\.cycles\.(values|items)\(\)", texto)]
    assert sin_copia == [], sin_copia


# ── I4 SAF-02/TMG-02: ConfigUnidades no relee el disco si no cambió ─────────
def test_config_unidades_cachea_lectura(tmp_path, monkeypatch):
    from autoclave.core.runtime.unidades import ConfigUnidades
    ruta = tmp_path / "unidades.json"
    ruta.write_text('{"temperatura": "F", "presion": "psi"}', encoding="utf-8")
    cfg = ConfigUnidades(ruta)
    assert cfg.leer() == {"temperatura": "F", "presion": "psi"}
    lecturas = []
    original = Path.read_text
    def contar(self, *a, **k):
        lecturas.append(self)
        return original(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", contar)
    for _ in range(5):
        assert cfg.leer() == {"temperatura": "F", "presion": "psi"}
    assert lecturas == []


def test_config_unidades_detecta_cambio_externo_y_guardado(tmp_path):
    from autoclave.core.runtime.unidades import ConfigUnidades, POR_DEFECTO
    ruta = tmp_path / "unidades.json"
    cfg = ConfigUnidades(ruta)
    assert cfg.leer() == dict(POR_DEFECTO)
    cfg.guardar("F", "psi")
    assert cfg.leer() == {"temperatura": "F", "presion": "psi"}
    ruta.write_text('{"temperatura": "C", "presion": "kPa"}  ', encoding="utf-8")
    st = ruta.stat()
    os.utime(ruta, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    assert cfg.leer() == {"temperatura": "C", "presion": "kPa"}
    ruta.unlink()
    assert cfg.leer() == dict(POR_DEFECTO)


def test_config_unidades_devuelve_copia(tmp_path):
    from autoclave.core.runtime.unidades import ConfigUnidades
    ruta = tmp_path / "unidades.json"
    ruta.write_text('{"temperatura": "F", "presion": "psi"}', encoding="utf-8")
    cfg = ConfigUnidades(ruta)
    cfg.leer()["temperatura"] = "X"
    assert cfg.leer()["temperatura"] == "F"


# ── I4 TMG-04: Motivo.valores no se puede mutar ─────────────────────────────
def test_motivo_valores_inmutable():
    import copy
    from autoclave.core.runtime.motivos import Motivo, valores_json
    m = Motivo("temp_alta", "Temperatura alta", temp=90.0)
    with pytest.raises(TypeError):
        m.valores["temp"] = 1.0
    assert valores_json(m) == {"temp": 90.0}
    c = copy.deepcopy(m)
    assert c == m and c.codigo == "temp_alta" and dict(c.valores) == {"temp": 90.0}


def test_motivo_valores_no_comparte_dict_externo():
    from autoclave.core.runtime.motivos import Motivo
    d = {"temp": 1.0}
    m = Motivo("temp_alta", "x", **d)
    d["temp"] = 2.0
    assert m.valores["temp"] == 1.0


# ── I4 TMG-03: la carga diferida de catálogos i18n ocurre una sola vez ──────
def test_i18n_carga_diferida_una_sola_vez(monkeypatch):
    from autoclave import i18n
    monkeypatch.setattr(i18n, "_catalogos", None)
    llamadas = []
    original = i18n.cargar
    def lenta():
        llamadas.append(1)
        time.sleep(0.05)
        original()
    monkeypatch.setattr(i18n, "cargar", lenta)
    hilos = [threading.Thread(target=i18n._todos) for _ in range(8)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert len(llamadas) == 1
    assert i18n._todos()
