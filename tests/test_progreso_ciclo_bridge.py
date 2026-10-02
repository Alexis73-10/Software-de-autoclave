# tests/test_progreso_ciclo_bridge.py
#
# ProgresoCiclo (ui_qml/bridge/progreso_ciclo.py): sondeo de
# /cycle/current/progress y /cycle/current/graph para la pantalla de ciclo en
# curso. Cliente HTTP simulado; el "hilo" se inyecta.

import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication

from autoclave.ui_qml.bridge.progreso_ciclo import ProgresoCiclo


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


class _Ejecutor:
    def __init__(self):
        self.tareas = []

    def __call__(self, tarea):
        self.tareas.append(tarea)

    def correr(self):
        self.tareas.pop(0)()
        QCoreApplication.processEvents()


class _Backend:
    def __init__(self):
        self.progreso = {"activo": False}
        self.lecturas = []
        self.ciclo = None
        self.llamadas = []
        self.falla = False

    def get(self, path, params=None):
        self.llamadas.append((path, params))
        if self.falla:
            raise ConnectionError("sin backend")
        if path == "/cycle/current/progress":
            return self.progreso
        if path == "/cycle/current/graph":
            desde = (params or {}).get("desde_id") or 0
            return {"ciclo_db_id": self.ciclo,
                    "lecturas": [l for l in self.lecturas if l["id"] > desde]}
        raise AssertionError(path)


def _lectura(i, t_s, fase_ui="vacio"):
    return {"id": i, "t_s": t_s, "fase": "PRE_VACIO", "fase_ui": fase_ui,
            "temp_camara": 80.0, "temp_ref": 79.0, "pres_camara": 101.3}


def _progreso_activo(**extra):
    return {"activo": True, "ciclo_db_id": 7, "fase_ciclo": "PRE_VACIO",
            "fase_activa": "vacio", "transcurrido_s": 90.0, "restante_s": 600.0,
            "fases": [{"fase": "vacio", "estado": "activa", "duracion_s": 90.0},
                      {"fase": "calentamiento", "estado": "pendiente", "duracion_s": None}],
            **extra}


def _nuevo(backend):
    ejecutor = _Ejecutor()
    return ProgresoCiclo(backend, ejecutar=ejecutor, iniciar=False), ejecutor


def test_inactivo_no_consulta():
    backend = _Backend()
    p, ejecutor = _nuevo(backend)
    p.refrescar()
    assert ejecutor.tareas == []


def test_sin_ciclo_no_pide_grafica():
    backend = _Backend()
    p, ejecutor = _nuevo(backend)
    p.activo = True
    p.refrescar()
    ejecutor.correr()
    assert [c[0] for c in backend.llamadas] == ["/cycle/current/progress"]
    assert p.hayCiclo is False
    assert p.transcurridoS is None


def test_con_ciclo_publica_progreso_y_grafica():
    backend = _Backend()
    backend.progreso = _progreso_activo()
    backend.ciclo = 7
    backend.lecturas = [_lectura(1, 0.0), _lectura(2, 60.0)]
    p, ejecutor = _nuevo(backend)
    p.activo = True
    p.refrescar()
    ejecutor.correr()
    assert p.hayCiclo is True
    assert p.transcurridoS == 90.0 and p.restanteS == 600.0
    assert p.tiempoActualMin == 1.5
    assert [f["fase"] for f in p.fases] == ["vacio", "calentamiento"]
    assert p.datosGrafica["t_min"] == [0.0, 1.0]
    assert p.fasesGrafica == [{"clave": "vacio", "inicioMin": 0.0}]


def test_grafica_incremental_pide_desde_el_ultimo_id():
    backend = _Backend()
    backend.progreso = _progreso_activo()
    backend.ciclo = 7
    backend.lecturas = [_lectura(1, 0.0), _lectura(2, 1.0)]
    p, ejecutor = _nuevo(backend)
    p.activo = True
    p.refrescar(); ejecutor.correr()
    backend.lecturas.append(_lectura(3, 2.0, "calentamiento"))
    backend.progreso = _progreso_activo(transcurrido_s=2.0)
    p.refrescar(); ejecutor.correr()
    assert backend.llamadas[-1] == ("/cycle/current/graph", {"desde_id": 2})
    assert len(p.datosGrafica["t_min"]) == 3
    assert [f["clave"] for f in p.fasesGrafica] == ["vacio", "calentamiento"]


def test_no_lanza_otra_consulta_mientras_hay_una_en_curso():
    backend = _Backend()
    p, ejecutor = _nuevo(backend)
    p.activo = True
    p.refrescar()
    p.refrescar()
    assert len(ejecutor.tareas) == 1


def test_error_de_red_conserva_los_ultimos_datos():
    backend = _Backend()
    backend.progreso = _progreso_activo()
    backend.ciclo = 7
    backend.lecturas = [_lectura(1, 0.0)]
    p, ejecutor = _nuevo(backend)
    p.activo = True
    p.refrescar(); ejecutor.correr()
    backend.falla = True
    p.refrescar(); ejecutor.correr()
    assert p.hayCiclo is True
    assert p.transcurridoS == 90.0
    assert len(p.datosGrafica["t_min"]) == 1
    # y vuelve a consultar en el siguiente tick
    backend.falla = False
    p.refrescar()
    assert len(ejecutor.tareas) == 1


def test_al_terminar_el_ciclo_se_vacia():
    backend = _Backend()
    backend.progreso = _progreso_activo()
    backend.ciclo = 7
    backend.lecturas = [_lectura(1, 0.0)]
    p, ejecutor = _nuevo(backend)
    p.activo = True
    p.refrescar(); ejecutor.correr()
    backend.progreso = {"activo": False}
    p.refrescar(); ejecutor.correr()
    assert p.hayCiclo is False
    assert p.datosGrafica["t_min"] == []
    assert p.fases == []
