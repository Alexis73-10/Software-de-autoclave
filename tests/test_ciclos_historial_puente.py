# tests/test_ciclos_historial_puente.py
#
# CiclosHistorial (ui_qml/bridge/ciclos_historial.py): listado de ciclos por
# periodo (GET /cycle/list) y curva del ciclo elegido
# (GET /cycle/history/{id}/graph) para las ventanas de Ciclos hoy e Historial
# del Menú Principal. Solo lectura, fuera del hilo de la GUI.

import os
import sys
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QSignalSpy

from autoclave.ui_qml.bridge.ciclos_historial import CiclosHistorial

_LISTA = {"periodo": "dia", "truncado": False, "ciclos": [
    {"id": 80, "numero_ciclo": 80, "fecha_inicio": "2026-10-02T08:05:00",
     "fecha_fin": "2026-10-02T08:40:00", "programa_id": "instrumental_134",
     "programa_nombre": "Instrumental 134", "programa_numero": 2,
     "resultado": "COMPLETADO", "operador": None}]}
_GRAFICA = {"ciclo_db_id": 80, "lecturas": [
    {"id": 1, "t_s": 0.0, "fase": "PRE_VACIO", "fase_ui": "vacio",
     "temp_camara": 40.0, "temp_ref": 35.0, "pres_camara": 101.3},
    {"id": 2, "t_s": 60.0, "fase": "CALENTAMIENTO", "fase_ui": "calentamiento",
     "temp_camara": 90.0, "temp_ref": 88.0, "pres_camara": 150.0}]}


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


def _historial(get):
    backend = MagicMock()
    backend.get.side_effect = get
    return CiclosHistorial(backend, ejecutar=lambda t: t()), backend


def _procesar():
    QCoreApplication.processEvents()


def test_estado_inicial():
    h, _ = _historial(lambda *a, **k: None)
    assert h.ciclos == [] and h.truncado is False and h.sinConexion is False
    assert h.graficaDisponible is False and h.datosGrafica["t_min"] == []


def test_consultar_lista_del_periodo():
    h, backend = _historial(lambda ruta, **k: _LISTA)
    espia = QSignalSpy(h.ciclosChanged)
    h.consultar("dia", True)
    _procesar()
    backend.get.assert_called_once_with("/cycle/list", params={"periodo": "dia", "terminados": "true"})
    assert [c["id"] for c in h.ciclos] == [80]
    assert h.ciclos[0]["numero"] == "80" and h.ciclos[0]["resultado"] == "COMPLETADO"
    assert h.periodo == "dia" and espia.count() == 1


def test_historial_por_inicio():
    h, backend = _historial(lambda ruta, **k: _LISTA)
    h.consultar("semana", False)
    _procesar()
    backend.get.assert_called_once_with("/cycle/list", params={"periodo": "semana", "terminados": "false"})
    assert h.periodo == "semana"


def test_periodo_invalido_no_consulta():
    h, backend = _historial(lambda ruta, **k: _LISTA)
    h.consultar("anio", False)
    _procesar()
    backend.get.assert_not_called()


def test_sin_respuesta_vacia_la_lista_y_avisa():
    respuestas = [_LISTA]

    def get(ruta, **k):
        if respuestas:
            return respuestas.pop()
        raise ConnectionError("sin backend")
    h, _ = _historial(get)
    h.consultar("dia", True); _procesar()
    h.consultar("dia", True); _procesar()
    assert h.sinConexion is True and h.ciclos == []


def test_cambiar_de_periodo_mientras_consulta_aplica_solo_el_ultimo():
    pendientes = []
    backend = MagicMock()
    backend.get.side_effect = lambda ruta, params=None: {**_LISTA, "periodo": params["periodo"]}
    h = CiclosHistorial(backend, ejecutar=pendientes.append)
    h.consultar("dia", False)
    h.consultar("mes", False)
    for tarea in pendientes:
        tarea()
    _procesar()
    assert h.periodo == "mes"


def test_cargar_grafica_de_un_ciclo():
    h, backend = _historial(lambda ruta, **k: _GRAFICA)
    espia = QSignalSpy(h.graficaChanged)
    h.cargarGrafica(80)
    _procesar()
    backend.get.assert_called_once_with("/cycle/history/80/graph")
    assert h.graficaDisponible is True and h.datosGrafica["t_min"] == [0.0, 1.0]
    assert [f["clave"] for f in h.fasesGrafica] == ["vacio", "calentamiento"]
    assert espia.count() == 1


def test_grafica_de_otro_ciclo_reemplaza_y_limpiar_la_vacia():
    h, _ = _historial(lambda ruta, **k: _GRAFICA)
    h.cargarGrafica(80); _procesar()
    h.limpiarGrafica()
    assert h.graficaDisponible is False and h.datosGrafica["t_min"] == []


def test_grafica_respuesta_tardia_de_un_ciclo_ya_no_elegido_se_ignora():
    pendientes = []
    backend = MagicMock()
    backend.get.side_effect = lambda ruta: {**_GRAFICA, "ciclo_db_id": int(ruta.split("/")[3])}
    h = CiclosHistorial(backend, ejecutar=pendientes.append)
    h.cargarGrafica(80)
    h.limpiarGrafica()          # se volvió a la lista antes de que llegara
    pendientes[0]()
    _procesar()
    assert h.graficaDisponible is False


def test_grafica_sin_respuesta():
    def get(ruta, **k):
        raise ConnectionError("sin backend")
    h, _ = _historial(get)
    h.cargarGrafica(80); _procesar()
    assert h.graficaDisponible is False


def test_id_invalido_no_consulta_grafica():
    h, backend = _historial(lambda ruta, **k: _GRAFICA)
    h.cargarGrafica(-1); _procesar()
    backend.get.assert_not_called()


# ── Historial: periodo de calendario elegido con las flechas ─────────────

from datetime import date

_HOY = date(2026, 10, 6)   # martes


def _historial_con_hoy(get=lambda ruta, **k: _LISTA):
    backend = MagicMock()
    backend.get.side_effect = get
    return CiclosHistorial(backend, ejecutar=lambda t: t(), hoy=lambda: _HOY), backend


def test_historial_consulta_el_periodo_actual_con_fecha():
    h, backend = _historial_con_hoy()
    h.consultarHistorial("mes")
    _procesar()
    backend.get.assert_called_once_with(
        "/cycle/list", params={"periodo": "mes", "terminados": "false", "fecha": "2026-10-06"})
    assert h.rotuloPeriodo == "Octubre 2026" and h.esPeriodoActual is True


def test_flecha_anterior_pide_el_mes_anterior():
    h, backend = _historial_con_hoy()
    h.consultarHistorial("mes")
    espia = QSignalSpy(h.periodoChanged)
    h.moverPeriodo(-1)
    _procesar()
    assert backend.get.call_args.kwargs["params"]["fecha"] == "2026-09-01"
    assert h.rotuloPeriodo == "Septiembre 2026" and h.esPeriodoActual is False
    assert espia.count() == 1


def test_flecha_siguiente_no_pasa_del_periodo_actual():
    h, backend = _historial_con_hoy()
    h.consultarHistorial("dia")
    h.moverPeriodo(-1)
    h.moverPeriodo(1)
    h.moverPeriodo(1)   # ya en hoy: no se mueve ni vuelve a pedir
    _procesar()
    assert backend.get.call_count == 3
    assert backend.get.call_args.kwargs["params"]["fecha"] == "2026-10-06"
    assert h.esPeriodoActual is True


@pytest.mark.parametrize("periodo, pasos, rotulo", [
    ("dia", 0, "Martes 6 oct 2026"),
    ("dia", -2, "Domingo 4 oct 2026"),
    ("semana", 0, "5 oct – 11 oct 2026"),
    ("semana", -1, "28 sep – 4 oct 2026"),
    ("semana", -40, "29 dic 2025 – 4 ene 2026"),
])
def test_rotulo_del_periodo(periodo, pasos, rotulo):
    h, _ = _historial_con_hoy()
    h.consultarHistorial(periodo)
    if pasos:
        h.moverPeriodo(pasos)
    assert h.rotuloPeriodo == rotulo


def test_mover_sin_historial_abierto_no_consulta():
    h, backend = _historial_con_hoy()
    h.moverPeriodo(-1)
    backend.get.assert_not_called()


# ── selección de ciclos para imprimir o enviar ───────────────────────────

_LISTA_3 = {"periodo": "mes", "truncado": False, "ciclos": [
    dict(_LISTA["ciclos"][0], id=i, numero_ciclo=i) for i in (82, 81, 80)]}


def test_marcar_y_desmarcar_ciclos():
    h, _ = _historial_con_hoy(lambda ruta, **k: _LISTA_3)
    h.consultarHistorial("mes")
    _procesar()
    espia = QSignalSpy(h.seleccionChanged)
    h.alternarSeleccion(81)
    h.alternarSeleccion(80)
    assert h.seleccionados == [81, 80] and h.todosSeleccionados is False
    h.alternarSeleccion(81)
    assert h.seleccionados == [80]
    assert espia.count() == 3


def test_seleccionar_todos_en_el_orden_del_listado():
    h, _ = _historial_con_hoy(lambda ruta, **k: _LISTA_3)
    h.consultarHistorial("mes")
    _procesar()
    h.alternarSeleccion(80)
    h.seleccionarTodos(True)
    assert h.seleccionados == [82, 81, 80] and h.todosSeleccionados is True
    h.seleccionarTodos(False)
    assert h.seleccionados == []


def test_cambiar_de_periodo_limpia_la_seleccion():
    h, _ = _historial_con_hoy(lambda ruta, **k: _LISTA_3)
    h.consultarHistorial("mes")
    _procesar()
    h.alternarSeleccion(80)
    h.moverPeriodo(-1)
    assert h.seleccionados == []


def test_no_marca_ciclos_que_no_estan_en_el_listado():
    h, _ = _historial_con_hoy(lambda ruta, **k: _LISTA_3)
    h.consultarHistorial("mes")
    _procesar()
    h.alternarSeleccion(999)
    assert h.seleccionados == []


# ── cambiar de Día / Semana / Mes conserva la fecha que se está viendo ──

def test_cambiar_de_periodo_conserva_la_fecha_vista():
    h, backend = _historial_con_hoy()
    h.consultarHistorial("mes")          # al abrir: el periodo actual
    h.moverPeriodo(-3)                   # julio 2026
    h.cambiarPeriodo("semana")           # la semana del 1 de julio
    assert h.rotuloPeriodo == "29 jun – 5 jul 2026"
    h.moverPeriodo(1)
    h.cambiarPeriodo("dia")              # el lunes de esa semana
    assert h.rotuloPeriodo == "Lunes 6 jul 2026"
    assert backend.get.call_args.kwargs["params"]["fecha"] == "2026-07-06"
    h.cambiarPeriodo("mes")
    assert h.rotuloPeriodo == "Julio 2026" and h.esPeriodoActual is False


def test_cambiar_de_periodo_sin_haber_abierto_usa_hoy():
    h, _ = _historial_con_hoy()
    h.cambiarPeriodo("semana")
    assert h.rotuloPeriodo == "5 oct – 11 oct 2026"


def test_abrir_otra_vez_vuelve_al_periodo_actual():
    h, _ = _historial_con_hoy()
    h.consultarHistorial("mes")
    h.moverPeriodo(-2)
    h.consultarHistorial("dia")
    assert h.rotuloPeriodo == "Martes 6 oct 2026"
