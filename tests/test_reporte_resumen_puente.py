# tests/test_reporte_resumen_puente.py
#
# ReporteResumen (ui_qml/bridge/reporte_resumen.py) y su formateo
# (ui_qml/domain/reporte_resumen.py): resumen de ciclos por periodo de la
# pantalla Reportes (GET /report/summary), con el periodo elegido por flechas.

import os
import sys
from datetime import date
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from autoclave.ui_qml.bridge.reporte_resumen import ReporteResumen
from autoclave.ui_qml.domain import reporte_resumen as dominio

_HOY = date(2026, 10, 6)
_RESUMEN = {
    "periodo": "mes", "desde": "2026-10-01", "hasta": "2026-10-31", "serie": "S", "modelo": "M",
    "totales": {"total": 3, "completados": 2, "fallos": 1, "cancelados": 0, "sin_cierre": 0},
    "por_programa": [{"programa_id": "instrumental_134", "programa_nombre": "Instrumental 134",
                      "programa_numero": 2, "total": 3, "completados": 2, "fallos": 1,
                      "cancelados": 0, "sin_cierre": 0}],
    "causas_fallo": [{"causa": "FALLO_SECADO", "cantidad": 1}],
}


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QApplication(sys.argv)


# ── formateo ─────────────────────────────────────────────────────────────

def test_presentable():
    p = dominio.presentable(_RESUMEN)
    assert p["total"] == "3"
    assert p["totales"] == [
        {"clave": "completados", "cantidad": "2", "porcentaje": "67%", "fraccion": 2 / 3},
        {"clave": "fallos", "cantidad": "1", "porcentaje": "33%", "fraccion": 1 / 3},
        {"clave": "cancelados", "cantidad": "0", "porcentaje": "0%", "fraccion": 0.0},
        {"clave": "sin_cierre", "cantidad": "0", "porcentaje": "0%", "fraccion": 0.0},
    ]
    assert p["por_programa"] == [{"programa": "02 · Instrumental 134", "total": "3", "completados": "2",
                                  "fallos": "1", "cancelados": "0", "sin_cierre": "0"}]
    assert p["causas"] == [{"causa": "FALLO_SECADO", "cantidad": "1"}]


def test_presentable_sin_respuesta_o_mal_formada():
    for r in (None, {}, {"totales": "x", "por_programa": [1], "causas_fallo": None}):
        p = dominio.presentable(r)
        assert p["total"] == "0" and p["por_programa"] == [] and p["causas"] == []
        assert all(t["cantidad"] == "0" for t in p["totales"])


# ── puente ───────────────────────────────────────────────────────────────

def _reporte(get=lambda ruta, **k: _RESUMEN):
    backend = MagicMock()
    backend.get.side_effect = get
    return ReporteResumen(backend, ejecutar=lambda t: t(), hoy=lambda: _HOY), backend


def test_consulta_el_periodo_actual():
    r, backend = _reporte()
    espia = QSignalSpy(r.datosChanged)
    r.consultar("mes")
    QCoreApplication.processEvents()
    backend.get.assert_called_once_with("/report/summary", params={"periodo": "mes", "fecha": "2026-10-06"})
    assert r.rotuloPeriodo == "Octubre 2026" and r.esPeriodoActual is True
    assert r.periodo == "mes" and r.fecha == "2026-10-06"
    assert r.datos["total"] == "3" and r.hayCiclos is True and espia.count() == 1


def test_flechas():
    r, backend = _reporte()
    r.consultar("mes")
    r.moverPeriodo(-1)
    QCoreApplication.processEvents()
    assert backend.get.call_args.kwargs["params"] == {"periodo": "mes", "fecha": "2026-09-01"}
    assert r.rotuloPeriodo == "Septiembre 2026" and r.esPeriodoActual is False
    r.moverPeriodo(1)
    r.moverPeriodo(1)   # ya en el actual: no vuelve a pedir
    assert backend.get.call_count == 3


def test_sin_conexion():
    def get(ruta, **k):
        raise ConnectionError()
    r, _ = _reporte(get)
    r.consultar("dia")
    QCoreApplication.processEvents()
    assert r.sinConexion is True and r.hayCiclos is False and r.cargando is False


def test_sin_ciclos():
    vacio = dict(_RESUMEN, totales={"total": 0, "completados": 0, "fallos": 0, "cancelados": 0,
                                    "sin_cierre": 0}, por_programa=[], causas_fallo=[])
    r, _ = _reporte(lambda ruta, **k: vacio)
    r.consultar("dia")
    QCoreApplication.processEvents()
    assert r.hayCiclos is False and r.sinConexion is False


def test_respuesta_tardia_se_descarta():
    pendientes = []
    backend = MagicMock()
    backend.get.side_effect = lambda ruta, params: dict(_RESUMEN, desde=params["fecha"])
    r = ReporteResumen(backend, ejecutar=pendientes.append, hoy=lambda: _HOY)
    r.consultar("mes")
    r.moverPeriodo(-1)
    pendientes[1]()
    pendientes[0]()   # la del mes actual llega después: se descarta
    QCoreApplication.processEvents()
    assert r.fecha == "2026-09-01" and r.cargando is False


def test_cambiar_de_periodo_conserva_la_fecha_vista():
    r, backend = _reporte()
    r.consultar("mes")
    r.moverPeriodo(-3)
    r.cambiarPeriodo("dia")
    assert r.rotuloPeriodo == "Miércoles 1 jul 2026"
    assert backend.get.call_args.kwargs["params"] == {"periodo": "dia", "fecha": "2026-07-01"}
    r.cambiarPeriodo("anio")              # desconocido: no hace nada
    assert r.periodo == "dia"
