"""T9 (tanda 2026-10-14): asistente de instalación QML con el puente real
(ARR-02 / MIG-07; planeacion_menu_instalacion_ui.md §5)."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from autoclave.installation import storage
from autoclave.installation.equipment import EquipmentClass
from autoclave.installation.clock_guard import ClockTamperedError

pytest.importorskip("PySide6")
from autoclave.ui_qml.bridge import puente_instalacion as pi

AHORA = datetime(2026, 10, 16, 8, 0, 0)


def _datos(**cambios):
    d = {
        "serial_number": "ab-123", "model_id": "AC-500", "equipment_class": "piso",
        "door_count": 2, "door_type": "advanced", "door_id": 2, "cooling_level": 2,
        "vapor_source": "generator",
        "supply_inputs": {"agua_bomba": False},
        "temperature_probes": {"temp_camara": False, "temp_ref": False},
    }
    d.update(cambios)
    return d


def _ok(_s, _c):
    return True


@pytest.fixture
def perfil_tmp(monkeypatch, tmp_path):
    ruta = tmp_path / "installation_profile.json"
    monkeypatch.setattr(storage, "INSTALLATION_FILE", ruta)
    return ruta


def test_clases_del_contrato():
    clases = pi.clases_disponibles()
    assert [c["valor"] for c in clases] == [e.value for e in EquipmentClass]
    piso = next(c for c in clases if c["valor"] == "piso")
    assert piso == {"valor": "piso", "vacio": True, "chaqueta": True, "liquidos": False,
                    "puertasMax": 2, "enfriamientoMax": 4}


def test_construir_perfil():
    p = pi.construir_perfil(_datos(), "X", AHORA, validar_codigo=_ok)
    assert p.serial_number == "AB-123" and p.machine_id == "ACV-2026-AB-123"
    assert p.locked is True and p.door_id == 2 and p.vapor_source == "generator"
    assert p.temperature_probes["temp_camara"] is True          # obligatoria
    assert p.temperature_probes["temp_ref"] is False
    assert p.supply_inputs["agua_bomba"] is False and p.supply_inputs["aire_comprimido"] is True


@pytest.mark.parametrize("cambios, motivo", [
    ({"door_count": 2, "equipment_class": "mesa_b"}, "puertas"),
    ({"cooling_level": 5}, "enfriamiento"),
    ({"vapor_source": "interno"}, "vapor"),
    ({"door_type": "corrediza"}, "puerta"),
    ({"equipment_class": "otra"}, "equipo"),
    ({"model_id": "  "}, "Modelo"),
    ({"serial_number": ""}, "serie"),
    ({"door_count": True}, "door_count"),
])
def test_construir_perfil_rechaza(cambios, motivo):
    with pytest.raises(ValueError) as e:
        pi.construir_perfil(_datos(**cambios), "X", AHORA, validar_codigo=_ok)
    assert motivo.lower() in str(e.value).lower()


def test_codigo_invalido_se_revalida():
    with pytest.raises(ValueError, match="activación"):
        pi.construir_perfil(_datos(), "X", AHORA, validar_codigo=lambda s, c: False)


def test_una_puerta_fija_la_puerta_del_pc():
    p = pi.construir_perfil(_datos(equipment_class="mesa_b", door_count=1, door_id=2,
                                   cooling_level=0), "X", AHORA, validar_codigo=_ok)
    assert p.door_id == 1


def test_escribe_y_no_sobrescribe_un_perfil_valido(perfil_tmp):
    p = pi.construir_perfil(_datos(), "X", validar_codigo=_ok)
    pi.escribir_perfil(p)
    assert json.loads(perfil_tmp.read_text(encoding="utf-8"))["serial_number"] == "AB-123"
    assert pi.requiere_instalacion() is False
    with pytest.raises(RuntimeError):
        pi.escribir_perfil(pi.construir_perfil(_datos(serial_number="otro"), "X",
                                               validar_codigo=_ok))
    assert json.loads(perfil_tmp.read_text(encoding="utf-8"))["serial_number"] == "AB-123"


def test_perfil_invalido_se_aparta_no_se_borra(perfil_tmp):
    perfil_tmp.write_text("{no es json", encoding="utf-8")
    assert pi.requiere_instalacion() is True
    pi.escribir_perfil(pi.construir_perfil(_datos(), "X", validar_codigo=_ok), AHORA)
    apartado = perfil_tmp.with_name("installation_profile.json.invalido-20261016-080000")
    assert apartado.read_text(encoding="utf-8") == "{no es json"
    assert pi.requiere_instalacion() is False


def test_reloj_alterado_no_abre_el_asistente(monkeypatch):
    def alterado():
        raise ClockTamperedError("reloj")
    monkeypatch.setattr(pi, "get_installation_profile", alterado)
    assert pi.requiere_instalacion() is False


def test_puente_instala_con_el_codigo_validado(perfil_tmp, qtbot=None):
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    codigos = []
    puente = pi.PuenteInstalacion(validar_codigo=lambda s, c: codigos.append((s, c)) or c == "BUENO")
    assert puente.validarCodigo("ab-123", "MALO") is False
    assert puente.instalar(_datos())["ok"] is False      # sin código válido
    assert not perfil_tmp.exists()
    assert puente.validarCodigo("ab-123", "BUENO") is True
    instalados = []
    puente.instalado.connect(lambda: instalados.append(1))
    r = puente.instalar(_datos())
    assert r == {"ok": True, "error": ""} and instalados == [1]
    assert perfil_tmp.exists()
    assert puente.instalar(_datos())["ok"] is False      # ya instalado


_SCRIPT = r"""
import json, sys
sys.path.insert(0, "src")
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
import autoclave.ui_qml.bridge.i18n_qml
from autoclave.ui_qml.controllers import teclado_alfanumerico_controller, teclado_numerico_controller
from autoclave.ui_qml.bridge.puente_instalacion import PuenteInstalacion
qml_dir = sys.argv[1]
app = QGuiApplication([])
engine = QQmlEngine()
engine.addImportPath(qml_dir)
avisos = []
engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
puente = PuenteInstalacion(validar_codigo=lambda s, c: False)
comp = QQmlComponent(engine, QUrl.fromLocalFile(qml_dir + "/InstalacionVentana.qml"))
raiz = comp.createWithInitialProperties({"puenteInstalacion": puente})
assert raiz is not None, comp.errorString()
asistente = raiz.findChild(QObject, "asistenteInstalacion")
print(json.dumps({"asistente": asistente is not None,
                  "clases": len(puente.clases), "avisos": avisos}))
"""


def test_ventana_de_instalacion_carga_sin_avisos():
    raiz = Path(__file__).resolve().parents[1]
    qml = raiz / "src" / "autoclave" / "ui_qml" / "qml"
    r = subprocess.run([sys.executable, "-c", _SCRIPT, str(qml)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=raiz, timeout=60,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr
    s = json.loads(r.stdout.strip().splitlines()[-1])
    assert s == {"asistente": True, "clases": 5, "avisos": []}


@pytest.mark.parametrize("door, requiere, abre", [(1, True, True), (2, True, False),
                                                   (1, False, False)])
def test_app_abre_el_asistente_solo_en_la_puerta_1_sin_perfil(monkeypatch, door, requiere, abre):
    from unittest.mock import MagicMock
    from autoclave.ui_qml import app as app_mod
    monkeypatch.setattr(app_mod, "QGuiApplication", MagicMock())
    monkeypatch.setattr(app_mod, "_cargar_fuentes", lambda: None)
    monkeypatch.setattr(app_mod, "requiere_instalacion", lambda: requiere)
    abiertos = []
    monkeypatch.setattr(app_mod, "_abrir_instalacion", lambda a, args: abiertos.append(1) or 7)

    class _Corte(Exception):
        pass

    def cortar(*_a, **_k):
        raise _Corte

    monkeypatch.setattr(app_mod, "SimuladorProgresoArranque", cortar)   # flujo normal
    if abre:
        assert app_mod.main(["--door", str(door)]) == 7
    else:
        with pytest.raises(_Corte):
            app_mod.main(["--door", str(door)])
    assert abiertos == ([1] if abre else [])


def test_tmg01_created_at_en_hora_local(perfil_tmp, monkeypatch):
    """clock_guard compara la fecha local: el perfil se sella en hora local."""
    import autoclave.installation.clock_guard as cg
    p = pi.construir_perfil(_datos(), "X", validar_codigo=_ok)
    assert abs((p.created_at - datetime.now()).total_seconds()) < 5
    pi.escribir_perfil(p)
    monkeypatch.setattr(cg, "_today", lambda: p.created_at.date())
    assert pi.requiere_instalacion() is False


def test_tmg03_perfil_atomico_sin_temporal(perfil_tmp):
    pi.escribir_perfil(pi.construir_perfil(_datos(), "X", validar_codigo=_ok))
    assert not perfil_tmp.with_name(perfil_tmp.name + ".tmp").exists()


def test_tmg02_el_asistente_terminado_no_se_relanza():
    from unittest.mock import MagicMock
    from autoclave.ui_qml import doble_pantalla as dp
    lanzados = []
    p = MagicMock()
    p.poll.return_value = dp.CODIGO_INSTALACION_TERMINADA
    t = [0.0]

    def dormir(s):
        t[0] += s

    dp.vigilar_pantallas([["py", "-m", "app"]], lambda c: lanzados.append(c) or p,
                         reloj=lambda: t[0], dormir=dormir)
    assert len(lanzados) == 1


def test_saf06_perfil_ilegible_abre_el_asistente(perfil_tmp):
    perfil_tmp.write_text("[1, 2]", encoding="utf-8")       # raíz que no es objeto
    assert pi.requiere_instalacion() is True
