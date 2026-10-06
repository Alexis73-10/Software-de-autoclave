# tests/test_resumen_sistema_puente.py
#
# ResumenSistema (ui_qml/bridge/resumen_sistema.py): consulta GET /cycle/summary
# fuera del hilo de la GUI y expone el Resumen del Sistema ya formateado.

import os
import sys
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QSignalSpy

from autoclave.ui_qml.bridge.resumen_sistema import ResumenSistema

SD = "—"

_RESPUESTA = {
    "ciclos_totales": 128, "ciclos_hoy": 3,
    "ultimo_ciclo": {"id": 42, "numero_ciclo": 128, "fecha_inicio": "2026-10-02T14:25:10",
                     "fecha_fin": "2026-10-02T15:02:00", "programa_id": "instrumental_134",
                     "programa_nombre": "Instrumental 134", "programa_numero": 2,
                     "resultado": "COMPLETADO"},
}


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


def _resumen(backend):
    return ResumenSistema(backend, ejecutar=lambda t: t())


def _consultar(r):
    r.consultar()
    QCoreApplication.processEvents()


def _textos(r):
    return (r.ciclosTotales, r.ciclosHoy, r.ultimoFecha, r.ultimoHora,
            r.ultimoPrograma, r.ultimoResultado)


def test_antes_de_consultar_todo_sin_dato_y_sin_aviso():
    r = _resumen(MagicMock())
    assert _textos(r) == (SD, SD, SD, SD, SD, "")
    assert r.sinConexion is False   # aún no se sabe: no se avisa sin conexión


def test_consulta_y_publica_los_datos():
    backend = MagicMock()
    backend.get.return_value = _RESPUESTA
    r = _resumen(backend)
    espia = QSignalSpy(r.datosChanged)
    _consultar(r)
    backend.get.assert_called_once_with("/cycle/summary")
    assert _textos(r) == ("128", "3", "02/10/2026", "14:25", "02", "COMPLETADO")
    assert r.ultimoProgramaNombre == "Instrumental 134"
    assert r.sinConexion is False
    assert espia.count() == 1


def test_sin_cambios_no_vuelve_a_emitir():
    backend = MagicMock()
    backend.get.return_value = _RESPUESTA
    r = _resumen(backend)
    _consultar(r)
    espia = QSignalSpy(r.datosChanged)
    _consultar(r)
    assert espia.count() == 0


def test_backend_sin_respuesta_avisa_y_muestra_sin_dato():
    backend = MagicMock()
    backend.get.return_value = _RESPUESTA
    r = _resumen(backend)
    _consultar(r)
    backend.get.side_effect = ConnectionError("sin backend")
    espia = QSignalSpy(r.sinConexionChanged)
    _consultar(r)
    assert r.sinConexion is True and espia.count() == 1
    # D-16: sin conexión los datos pasan a "—" (no un valor viejo sin marcar)
    assert _textos(r) == (SD, SD, SD, SD, SD, "")


def test_al_volver_la_conexion_se_recupera():
    backend = MagicMock()
    backend.get.side_effect = ConnectionError("sin backend")
    r = _resumen(backend)
    _consultar(r)
    assert r.sinConexion is True
    backend.get.side_effect = None
    backend.get.return_value = _RESPUESTA
    _consultar(r)
    assert r.sinConexion is False and r.ciclosHoy == "3"


def test_respuesta_mal_formada_cuenta_como_sin_respuesta():
    backend = MagicMock()
    backend.get.return_value = ["no", "es", "un", "resumen"]
    r = _resumen(backend)
    _consultar(r)
    assert r.sinConexion is True and r.ciclosTotales == SD


def test_no_lanza_una_segunda_consulta_mientras_hay_una_en_curso():
    backend = MagicMock()
    pendientes = []
    r = ResumenSistema(backend, ejecutar=pendientes.append)
    r.consultar()
    r.consultar()
    assert len(pendientes) == 1


def test_iniciar_consulta_ya_y_arma_el_sondeo_de_10_s():
    backend = MagicMock()
    backend.get.return_value = _RESPUESTA
    r = _resumen(backend)
    assert r.intervaloMs == 10000
    r.iniciar()
    QCoreApplication.processEvents()
    assert backend.get.call_count == 1 and r.sondeando is True
    r.detener()
    assert r.sondeando is False


def test_mantenimiento_y_secado_sin_fuente():
    r = _resumen(MagicMock())
    assert r.proximoMantenimiento == SD   # MP-06b / B-03: no existe fuente
    assert r.tiempoSecado == SD           # TODO(MP-11)


# ── curva del último ciclo (ventana flotante, D-21) ─────────────────────

_GRAFICA = {"ciclo_db_id": 42, "lecturas": [
    {"id": 1, "t_s": 0.0, "fase": "PRE_VACIO", "fase_ui": "vacio",
     "temp_camara": 40.0, "temp_ref": 35.0, "pres_camara": 101.3},
    {"id": 2, "t_s": 120.0, "fase": "CALENTAMIENTO", "fase_ui": "calentamiento",
     "temp_camara": 90.0, "temp_ref": None, "pres_camara": 150.0},
]}


def _con_resumen(grafica=None, error=None):
    backend = MagicMock()

    def get(ruta, **kw):
        if ruta == "/cycle/summary":
            return _RESPUESTA
        if error:
            raise error
        return grafica
    backend.get.side_effect = get
    r = _resumen(backend)
    _consultar(r)
    return r, backend


def test_sin_cargar_no_hay_grafica():
    r, _ = _con_resumen(_GRAFICA)
    assert r.graficaUltimoDisponible is False
    assert r.datosGraficaUltimo["t_min"] == []


def test_cargar_grafica_del_ultimo_ciclo():
    r, backend = _con_resumen(_GRAFICA)
    espia = QSignalSpy(r.graficaUltimoChanged)
    r.cargarGraficaUltimo()
    QCoreApplication.processEvents()
    backend.get.assert_called_with("/cycle/history/42/graph")
    assert r.graficaUltimoDisponible is True and espia.count() == 1
    d = r.datosGraficaUltimo
    assert d["t_min"] == [0.0, 2.0]
    assert d["temp_camara"] == [40.0, 90.0] and d["temp_ref"] == [35.0, None]
    assert [f["clave"] for f in r.fasesGraficaUltimo] == ["vacio", "calentamiento"]


def test_grafica_sin_respuesta_queda_no_disponible():
    r, _ = _con_resumen(error=ConnectionError("sin backend"))
    r.cargarGraficaUltimo()
    QCoreApplication.processEvents()
    assert r.graficaUltimoDisponible is False and r.datosGraficaUltimo["t_min"] == []


def test_sin_ultimo_ciclo_no_consulta_la_grafica():
    backend = MagicMock()
    backend.get.return_value = {"ciclos_totales": 0, "ciclos_hoy": 0, "ultimo_ciclo": None}
    r = _resumen(backend)
    _consultar(r)
    r.cargarGraficaUltimo()
    QCoreApplication.processEvents()
    assert backend.get.call_count == 1 and r.graficaUltimoDisponible is False


def test_operador_del_ultimo_ciclo():
    r, _ = _con_resumen(_GRAFICA)
    assert r.ultimoOperador == SD   # hoy no se guarda (Paso 1 b)
