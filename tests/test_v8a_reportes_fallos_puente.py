# tests/test_v8a_reportes_fallos_puente.py
#
# D8-5.6 (tanda 8): ReporteResumen despliega los ciclos de un tipo de fallo del
# resumen (GET /report/failures), paginados, en el periodo que se está viendo.

import os
import sys
from datetime import date
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from autoclave.ui_qml.bridge.reporte_resumen import ReporteResumen

_HOY = date(2026, 10, 6)
_RESUMEN = {"totales": {"total": 1, "completados": 0, "fallos": 1, "cancelados": 0, "sin_cierre": 0},
            "por_programa": [], "causas_fallo": [{"causa": "FALLO_SECADO", "cantidad": 1}]}


def _pagina(pagina=1, paginas=3, total=45):
    return {"periodo": "mes", "causa": "FALLO_SECADO", "total": total, "pagina": pagina,
            "paginas": paginas, "por_pagina": 20,
            "ciclos": [{"id": 7, "numero_ciclo": 41, "fecha_inicio": "2026-10-03T08:05:00",
                        "fecha_fin": "2026-10-03T08:45:00", "programa_id": "instrumental_134",
                        "programa_nombre": "Instrumental 134", "programa_numero": 2,
                        "resultado": "FALLO_SECADO", "operador": "Ana Pérez"}]}


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QApplication(sys.argv)


def _reporte(fallos=None):
    def get(ruta, params=None, **k):
        if ruta == "/report/failures":
            if fallos is None:
                return _pagina(pagina=params["pagina"])
            return fallos(params)
        return _RESUMEN
    backend = MagicMock()
    backend.get.side_effect = get
    r = ReporteResumen(backend, ejecutar=lambda t: t(), hoy=lambda: _HOY)
    r.consultar("mes")
    QCoreApplication.processEvents()
    return r, backend


def test_abrir_un_fallo_pide_sus_ciclos_del_periodo_visto():
    r, backend = _reporte()
    assert r.causaFallo == "" and r.ciclosFallo == []
    r.abrirFallo("FALLO_SECADO")
    QCoreApplication.processEvents()
    backend.get.assert_called_with("/report/failures", params={
        "periodo": "mes", "fecha": "2026-10-06", "causa": "FALLO_SECADO", "pagina": 1})
    assert r.causaFallo == "FALLO_SECADO"
    assert (r.paginaFallo, r.paginasFallo, r.totalFallo) == (1, 3, 45)
    fila = r.ciclosFallo[0]
    assert fila["id"] == 7 and fila["numero"] == "41" and fila["operador"] == "Ana Pérez"
    assert fila["fecha"] == "03/10/2026" and fila["hora"] == "08:05"
    assert fila["programa"] == "02" and fila["programa_nombre"] == "Instrumental 134"
    assert r.cargandoFallo is False and r.sinConexionFallo is False


def test_paginas_con_flechas_sin_salir_del_rango():
    r, backend = _reporte()
    r.abrirFallo("FALLO_SECADO")
    r.moverPaginaFallo(-1)              # ya en la primera: no pide
    assert backend.get.call_args.kwargs["params"]["pagina"] == 1
    llamadas = backend.get.call_count
    r.moverPaginaFallo(1)
    QCoreApplication.processEvents()
    assert backend.get.call_args.kwargs["params"]["pagina"] == 2 and r.paginaFallo == 2
    r.moverPaginaFallo(1)
    r.moverPaginaFallo(1)               # ya en la última (3): no pide
    assert backend.get.call_count == llamadas + 2


def test_cerrar_o_cambiar_de_periodo_cierra_el_listado():
    r, _ = _reporte()
    r.abrirFallo("FALLO_SECADO")
    QCoreApplication.processEvents()
    r.cerrarFallo()
    assert r.causaFallo == "" and r.ciclosFallo == []
    r.abrirFallo("FALLO_SECADO")
    r.moverPeriodo(-1)
    QCoreApplication.processEvents()
    assert r.causaFallo == "" and r.ciclosFallo == []


def test_sin_conexion_al_pedir_los_ciclos():
    def falla(params):
        raise ConnectionError()
    r, _ = _reporte(falla)
    r.abrirFallo("FALLO_SECADO")
    QCoreApplication.processEvents()
    assert r.causaFallo == "FALLO_SECADO" and r.ciclosFallo == []
    assert r.sinConexionFallo is True and r.cargandoFallo is False


def test_respuesta_tardia_se_descarta():
    pendientes = []
    backend = MagicMock()
    backend.get.side_effect = lambda ruta, params=None, **k: (
        _pagina(pagina=params["pagina"]) if ruta == "/report/failures" else _RESUMEN)
    r = ReporteResumen(backend, ejecutar=pendientes.append, hoy=lambda: _HOY)
    r.consultar("mes")
    pendientes.pop(0)()
    QCoreApplication.processEvents()
    r.abrirFallo("FALLO_SECADO")
    r.cerrarFallo()
    pendientes.pop(0)()               # llega después de cerrar: se descarta
    QCoreApplication.processEvents()
    assert r.causaFallo == "" and r.ciclosFallo == []


def test_causa_vacia_no_pide():
    r, backend = _reporte()
    llamadas = backend.get.call_count
    r.abrirFallo("")
    assert backend.get.call_count == llamadas and r.causaFallo == ""
