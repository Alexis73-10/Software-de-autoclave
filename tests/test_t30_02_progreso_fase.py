# tests/test_t30_02_progreso_fase.py
#
# T30-02: progreso de la fase activa en lugar del tiempo restante.
# Backend (dato crudo: progreso_ciclo.detalle_fase), dominio (texto en las
# unidades vigentes, ciclo_en_curso.texto_progreso) y pantalla QML.

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from autoclave.core.runtime import progreso_ciclo as pc
from autoclave.ui_qml.domain import ciclo_en_curso as ce


class _Ciclo:
    def __init__(self, params):
        self._p = params

    def get_param(self, *ruta, default=None):
        v = self._p
        for k in ruta:
            if not isinstance(v, dict) or k not in v:
                return default
            v = v[k]
        return v


def _estado(**kw):
    base = dict(sensores_pres={"pres_camara": 180.0, "pres_chaqueta": 250.0},
                sensores_temp={"temp_camara": 128.0},
                prevacio_progreso="", sub_estado_ciclo="", fase_en_sostenimiento=False,
                estabilizacion_s=None, estabilizacion_total_s=None,
                exposicion_total_s=None, exposicion_restante_s=None, f0_acumulado=0.0,
                descompresion_enfriando=False, secado_transcurrido_s=None, secado_total_s=None)
    base.update(kw)
    return SimpleNamespace(**base)


_PARAMS = {
    "precalentamiento": {"presion_precalentamiento": 328},
    "prevacio": {"conteo_pulso_a": 3, "conteo_pulso_b": 2, "conteo_pulso_c": 0, "conteo_pulso_d": 3},
    "calentamiento": {"temperatura_calentamiento": 134.0},
    "globals": {"F0": True, "F0_objetivo": 12},
    "descompresion": {"modo": 1, "presion_fin_descompresion": 10,
                      "modo_4": {"temperatura_enfriamiento": 80.0}},
}
_CAP = SimpleNamespace(has_liquid_sensor=True)
_CFG = {"presion_admosferica": 75.0, "rango_presion_atm": 20.0}


def _det(fase, estado=None, params=None, cap=_CAP):
    return pc.detalle_fase(fase, estado or _estado(), _Ciclo(params or _PARAMS), cap, _CFG)


def test_precalentamiento_chaqueta_y_consigna():
    assert _det("precalentamiento") == {"tipo": "presion", "actual": 250.0, "objetivo": 328.0}


@pytest.mark.parametrize("progreso,paso,esperado", [
    ("A  1/3", "DECOMPRESION", (1, "bajo")),
    ("B  2/2", "VAPOR_ALTO", (5, "alto")),
    ("D  3/3", "HOLD_BAJO", (8, "bajo")),
    ("A  2/3", "HOLD_ALTO", (2, "alto")),
])
def test_prevacio_pulso_global_y_nivel(progreso, paso, esperado):
    d = _det("vacio", _estado(prevacio_progreso=progreso, sub_estado_ciclo=paso))
    assert (d["pulso"], d["nivel"]) == esperado and d["total"] == 8


def test_prevacio_sin_dato():
    d = _det("vacio")
    assert d["pulso"] is None and d["nivel"] is None


def test_calentamiento_temperatura_y_estabilizacion():
    assert _det("calentamiento") == {"tipo": "temperatura", "actual": 128.0, "objetivo": 134.0}
    d = _det("calentamiento", _estado(fase_en_sostenimiento=True, estabilizacion_s=45.0,
                                      estabilizacion_total_s=60.0))
    assert d == {"tipo": "estabilizando", "transcurrido_s": 45.0, "total_s": 60.0}


def test_esterilizacion_con_y_sin_f0():
    est = _estado(exposicion_total_s=300.0, exposicion_restante_s=170.0, f0_acumulado=4.2)
    d = _det("esterilizacion", est)
    assert d["transcurrido_s"] == 130.0 and d["total_s"] == 300.0
    assert d["f0"] == 4.2 and d["f0_objetivo"] == 12
    sin_f0 = {**_PARAMS, "globals": {"F0": False, "F0_objetivo": 12}}
    d = _det("esterilizacion", est, sin_f0)
    assert d["f0"] is None and d["f0_objetivo"] is None
    # F0 sin sensor de líquido en el equipo: no se muestra (como la fase)
    assert _det("esterilizacion", est, cap=SimpleNamespace(has_liquid_sensor=False))["f0"] is None


def test_descompresion_presion_de_fin_y_enfriamiento():
    assert _det("descompresion") == {"tipo": "presion", "actual": 180.0, "objetivo": 85.0}
    # modo 0 y parámetro inválido: rango_presion_atm
    modo0 = {**_PARAMS, "descompresion": {"modo": 0}}
    assert _det("descompresion", params=modo0)["objetivo"] == 95.0
    malo = {**_PARAMS, "descompresion": {"modo": 2, "presion_fin_descompresion": -1}}
    assert _det("descompresion", params=malo)["objetivo"] == 95.0
    # modos 4/5 enfriando: temperatura
    m4 = {**_PARAMS, "descompresion": {"modo": 4, "modo_4": {"temperatura_enfriamiento": 80.0}}}
    d = _det("descompresion", _estado(descompresion_enfriando=True), m4)
    assert d == {"tipo": "temperatura", "actual": 128.0, "objetivo": 80.0}
    assert _det("descompresion", _estado(descompresion_enfriando=False), m4)["tipo"] == "presion"


def test_secado_tiempo():
    d = _det("secado", _estado(secado_transcurrido_s=240.0, secado_total_s=900.0))
    assert d == {"tipo": "tiempo", "transcurrido_s": 240.0, "total_s": 900.0}


def test_sin_fase_o_con_error_none():
    assert pc.detalle_fase(None, _estado(), _Ciclo(_PARAMS)) is None
    assert pc.detalle_fase("secado", None, None) is None
    # un estado sin los atributos nuevos no falla: todo None
    assert _det("secado", SimpleNamespace())["transcurrido_s"] is None


def test_armar_progreso_conserva_restante_y_llenado():
    # el llenado LLF y el contrato anterior no cambian
    r = pc.armar_progreso(["calentamiento"], [], "CALENTAMIENTO", 10.0, {"calentamiento": 100.0})
    assert "restante_s" in r and r["fases"][0]["estado"] == "activa"


# ── dominio ──────────────────────────────────────────────────────────────

def _t(det, idioma="es"):
    return ce.texto_progreso(det, idioma)


def test_texto_presion_y_temperatura():
    assert _t({"tipo": "presion", "actual": 250.0, "objetivo": 328.0}) == "250.0 / 328.0 kPa"
    assert _t({"tipo": "temperatura", "actual": 128.0, "objetivo": 134.0}) == "128.0 / 134.0 °C"


def test_texto_prevacio_es_en():
    d = {"tipo": "prevacio", "pulso": 3, "total": 8, "nivel": "bajo"}
    assert _t(d) == "3/8 Bajo"
    assert _t({**d, "nivel": "alto"}, "en") == "3/8 High"


def test_texto_estabilizando_exposicion_secado():
    assert _t({"tipo": "estabilizando", "transcurrido_s": 45, "total_s": 60}) == "Estabilizando 0:45 / 1:00"
    assert _t({"tipo": "estabilizando", "transcurrido_s": 45, "total_s": 60}, "en") == "Stabilizing 0:45 / 1:00"
    d = {"tipo": "exposicion", "transcurrido_s": 130, "total_s": 300, "f0": None, "f0_objetivo": None}
    assert _t(d) == "2:10 / 5:00 min"
    assert _t({**d, "f0": 4.2, "f0_objetivo": 12.0}) == "2:10 / 5:00 min  F0 4.2 / 12.0 min"
    assert _t({"tipo": "tiempo", "transcurrido_s": 240, "total_s": 900}) == "4:00 / 15:00 min"


@pytest.mark.parametrize("det", [
    None, "x", {"tipo": "raro"}, {"tipo": "presion", "actual": None, "objetivo": 3.0},
    {"tipo": "presion", "actual": float("nan"), "objetivo": 3.0},
    {"tipo": "prevacio", "pulso": None, "total": 8, "nivel": "bajo"},
    {"tipo": "tiempo", "transcurrido_s": None, "total_s": 900},
    {"tipo": "tiempo", "transcurrido_s": True, "total_s": 900},
])
def test_texto_sin_dato_es_raya(det):
    assert _t(det) == "—"


def test_normalizar_progreso_trae_detalle():
    base = {"activo": True, "detalle_fase": {"tipo": "tiempo", "transcurrido_s": 1, "total_s": 2}}
    assert ce.normalizar_progreso(base)["detalle_fase"]["total_s"] == 2.0
    assert ce.normalizar_progreso({"activo": True})["detalle_fase"] is None
    assert ce.normalizar_progreso(None)["detalle_fase"] is None


def test_claves_i18n_en_ambos_idiomas():
    raiz = Path(ce.__file__).resolve().parents[2] / "i18n"
    es = json.loads((raiz / "es.json").read_text(encoding="utf-8"))["progreso_fase"]
    en = json.loads((raiz / "en.json").read_text(encoding="utf-8"))["progreso_fase"]
    assert set(es) == set(en) and es["rotulo"] and en["rotulo"]


# ── pantalla QML ─────────────────────────────────────────────────────────

RAIZ_QML = Path(ce.__file__).resolve().parents[1] / "qml"

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from PySide6.QtCore import QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from autoclave.ui_qml.bridge import i18n_qml  # noqa: F401
    from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave.ui_qml.bridge.progreso_ciclo import ProgresoCiclo

    qml_dir = sys.argv[1]
    app = QGuiApplication([])
    avisos = []
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    engine.addImportPath(qml_dir)
    engine.setInitialProperties({})
    engine.load(QUrl.fromLocalFile(qml_dir + "/Pruebas/PruebaCicloEnCurso.qml"))
    ventana = engine.rootObjects()[0]
    ventana.setWidth(600); ventana.setHeight(960)
    QTest.qWait(200)
    pantalla = [o for o in ventana.findChildren(QObject)
                if o.metaObject().className().startswith("PantallaCicloEnCurso_QML")][0]
    def texto():
        return [o for o in ventana.findChildren(QObject) if o.objectName() == "textoProgresoFase"][0]
    r = {"demo": texto().property("text")}

    puente = ProgresoCiclo(None, iniciar=False)
    pantalla.setProperty("progreso", puente)
    pantalla.setProperty("datosVigentes", True)
    puente._al_recibir({"activo": True, "ciclo_db_id": 1, "fase_ciclo": "ESTERILIZACION",
        "fase_activa": "esterilizacion", "fases": [], "transcurrido_s": 10,
        "detalle_fase": {"tipo": "exposicion", "transcurrido_s": 130, "total_s": 300,
                         "f0": None, "f0_objetivo": None}}, None)
    QTest.qWait(100)
    r["vivo"] = texto().property("text")
    puente._al_recibir({"activo": True, "ciclo_db_id": 1, "fase_ciclo": "SECADO",
        "fase_activa": "secado", "fases": [], "transcurrido_s": 11, "detalle_fase": None}, None)
    QTest.qWait(100)
    r["sin_dato"] = texto().property("text")
    r["avisos"] = avisos
    print(json.dumps(r))
""")


def test_pantalla_muestra_el_progreso_de_la_fase():
    r = subprocess.run([sys.executable, "-c", _SCRIPT, str(RAIZ_QML)],
                       capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, timeout=60)
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout.strip().splitlines()[-1])
    assert d["avisos"] == []
    assert d["demo"] == "—"
    assert d["vivo"] == "2:10 / 5:00 min"
    assert d["sin_dato"] == "—"


def test_pantalla_ya_no_muestra_tiempo_restante():
    fuente = (RAIZ_QML / "Pantallas" / "PantallaCicloEnCurso.qml").read_text(encoding="utf-8")
    assert "tiempo_restante" not in fuente and "formatoReloj(raiz.restanteS)" not in fuente
    assert "textoProgresoFase" in fuente
