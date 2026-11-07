"""T29-01 (tanda 29, ALTA): un cambio de parámetros del programa hecho justo
antes de iniciar debe regir en el ciclo que se inicia.

Integración de punta a punta del backend: rutas reales (PATCH /cycle/parameter,
/cycle/select, GET /programas), CycleManager real con copia de los programas,
base real (bitácora), ControlLoop real con su StateMachine y CicloState reales
(sin hilo ni módulo E/S). El paso PREPARADO → CICLO se hace como la máquina de
estados (on_state_entry(CICLO) bajo el lock), que toma la copia del programa
(T-17) con la que corren las fases. Cubre: guardar e iniciar sin salir de
Opciones, guardar y reseleccionar el programa, guardar con el resultado del
ciclo anterior pendiente (CICLO, ingeniero), seleccionar otro y volver, y la
persistencia en el JSON (recarga de programas tras un reinicio).

Y del lado de la UI (ParametrosCicloController), que el PATCH lleva el
cycle_id del programa abierto, que tras T29-06 es el seleccionado en Preciclo.
"""

import os
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers.cycle_manager import CycleManager
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.helpers.arranque_doble import evento_liberado

RAIZ = Path(__file__).resolve().parents[1]
PROGRAMA = "134_instrumental"           # número 2, sólido, con prevacío
OTRO = "instrumental_121"


def _cm(tmp_path) -> CycleManager:
    origen = RAIZ / "src" / "autoclave" / "cycles"
    for sub in ("factory", "user"):
        shutil.copytree(origen / sub, tmp_path / "cycles" / sub)
    m = CycleManager()
    m.raiz = str(tmp_path)
    m.load_all_cycles()
    m.set_default_cycle("bowe_dick")
    return m


def _loop(cm):
    from autoclave.core.runtime.status import EstadoAutoclave
    from autoclave.services.domain.loop.control_loop import ControlLoop
    estado = EstadoAutoclave()
    loop = ControlLoop(arranque_liberado=evento_liberado(), units=MagicMock(),
                       door_service=MagicMock(), doors=[], estado=estado, link=MagicMock(),
                       set_do=MagicMock(), alarm_manager=MagicMock(), cycle_manager=cm,
                       config_manager=MagicMock(), profile=None)
    estado.set_machine_state(GlobalState.PREPARADO)
    return loop


@pytest.fixture
def entorno(tmp_path):
    from fastapi.testclient import TestClient
    from tests.helpers.backend_doble import cabecera, cargar_servidor
    cm = _cm(tmp_path)
    loop = _loop(cm)
    ctx = MagicMock()
    ctx.cycle_manager = cm
    ctx.control_loop = loop
    ctx.estado = loop.estado
    ctx.sin_base_de_datos = False
    ctx.db = DbManager(tmp_path / "bd.db")
    ctx.cap.has_liquids = True
    ctx.cycle_logger.ciclo_id_pantalla = 7
    srv, _ = cargar_servidor(ctx)
    client = TestClient(srv.app, headers=cabecera(srv, "ingeniero"))
    return client, cm, loop, tmp_path


def _patch(client, clave, valor, cycle_id=PROGRAMA):
    r = client.patch("/cycle/parameter", json={"cycle_id": cycle_id, "fase": "prevacio",
                                               "path": [clave], "value": valor})
    assert r.status_code == 200, r.text
    return r.json()


def _select(client, cycle_id):
    r = client.post("/cycle/select", json={"cycle_id": cycle_id, "origen": "puerta_1"})
    assert r.status_code == 200, r.text


def _iniciar(loop):
    """PREPARADO → CICLO como StateMachine.update() (bajo el lock del loop)."""
    with loop.bloqueo_maquina():
        loop.estado.set_machine_state(GlobalState.CICLO)
        loop.state_machine.on_state_entry(GlobalState.CICLO)
        loop.state_machine.prev_state = GlobalState.CICLO


def _terminar(loop):
    with loop.bloqueo_maquina():
        loop.estado.set_machine_state(GlobalState.PREPARADO)
        loop.state_machine.prev_state = GlobalState.PREPARADO


def _valores_del_ciclo(loop) -> dict:
    """Lo que leen las fases del ciclo en curso (la copia de reset())."""
    ciclo = loop.state_machine.ciclo
    prevacio = ciclo._fases[1]
    assert prevacio.name == "PRE_VACIO"
    assert prevacio.cycle is ciclo.programa_en_curso is loop.programa_en_ejecucion()
    return {k: prevacio.cycle.get_param("prevacio", k)
            for k in ("conteo_pulso_b", "presion_baja_pulso_b", "presion_alta_pulso_b",
                      "tiempo_adicional_bajo_b")}


NUEVOS = {"conteo_pulso_b": 2, "presion_baja_pulso_b": 25, "presion_alta_pulso_b": 150,
          "tiempo_adicional_bajo_b": 5}


def _guardar_nuevos(client):
    for clave, valor in NUEVOS.items():
        assert _patch(client, clave, valor)["aplica"] == "siguiente"


def test_guardar_e_iniciar_sin_salir_de_opciones(entorno):
    client, _cm_, loop, _ = entorno
    _select(client, PROGRAMA)
    _guardar_nuevos(client)
    _iniciar(loop)
    assert _valores_del_ciclo(loop) == NUEVOS


def test_guardar_y_reseleccionar_el_programa(entorno):
    client, _cm_, loop, _ = entorno
    _select(client, PROGRAMA)
    _guardar_nuevos(client)
    _select(client, PROGRAMA)
    _iniciar(loop)
    assert _valores_del_ciclo(loop) == NUEVOS


def test_guardar_otro_programa_y_seleccionarlo_despues(entorno):
    client, _cm_, loop, _ = entorno
    _select(client, OTRO)
    _guardar_nuevos(client)
    _select(client, PROGRAMA)
    _iniciar(loop)
    assert _valores_del_ciclo(loop) == NUEVOS


def test_guardar_con_el_resultado_del_ciclo_anterior_pendiente(entorno):
    """El ciclo anterior terminó y espera CONFIRMAR (sigue en CICLO): el
    ingeniero guarda; rige en el ciclo siguiente."""
    client, _cm_, loop, _ = entorno
    _select(client, PROGRAMA)
    _iniciar(loop)
    loop.state_machine.ciclo._fase_idx = len(loop.state_machine.ciclo._fases)   # todas corridas
    anterior = _valores_del_ciclo(loop)
    for clave, valor in NUEVOS.items():
        assert _patch(client, clave, valor)["aplica"] == "siguiente"
    assert _valores_del_ciclo(loop) == anterior          # el ciclo ya corrido no cambia
    _terminar(loop)
    _iniciar(loop)
    assert _valores_del_ciclo(loop) == NUEVOS


def test_lo_guardado_queda_en_el_json_y_rige_tras_recargar(entorno):
    client, _cm_, loop, tmp_path = entorno
    _select(client, PROGRAMA)
    _guardar_nuevos(client)
    recargado = CycleManager()
    recargado.raiz = str(tmp_path)
    recargado.load_all_cycles()
    programa = recargado.cycles[PROGRAMA]
    assert {k: programa.get_param("prevacio", k) for k in NUEVOS} == NUEVOS


def test_get_programas_marca_el_seleccionado(entorno):
    client, _cm_, loop, _ = entorno
    _select(client, PROGRAMA)
    programas = client.get("/programas").json()["programas"]
    marcados = [p["cycle_id"] for p in programas if p["seleccionado"]]
    assert marcados == [PROGRAMA]


# ── UI: el controlador abre en el seleccionado y su PATCH lleva ese cycle_id ──

class _SesionHttp:
    """Sesión síncrona del controlador sobre el TestClient del backend real."""

    def __init__(self, client):
        from autoclave.ui_qml.sesion_backend import Resultado
        self.client, self.Resultado, self.enviados = client, Resultado, []

    def enviar(self, metodo, ruta, cuerpo=None):
        self.enviados.append((metodo, ruta, cuerpo))
        r = self.client.request(metodo, ruta, json=cuerpo)
        datos = r.json() if r.content else None
        return self.Resultado("ok" if r.status_code < 400 else "rechazo", datos, r.status_code)


def test_controlador_guarda_en_el_programa_seleccionado_y_el_ciclo_lo_usa(entorno):
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.parametros_ciclo_controller import ParametrosCicloController
    client, cm, loop, _ = entorno
    _select(client, PROGRAMA)                         # elegido en Preciclo
    s = _SesionHttp(client)
    c = ParametrosCicloController(sesion=s)
    c.cargar()
    assert c.numero == cm.cycles[PROGRAMA].number     # T29-06: no abre en Bowie & Dick
    c.abrirSeccion("prevacio")
    assert c.guardar("conteo_pulso_b", 3)
    patch = [cuerpo for m, ruta, cuerpo in s.enviados if m == "PATCH"]
    assert patch and patch[-1]["cycle_id"] == PROGRAMA
    _iniciar(loop)
    assert _valores_del_ciclo(loop)["conteo_pulso_b"] == 3
