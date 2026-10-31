# tests/test_t21_alarmas_con_ciclo.py
#
# FC-03 (tanda 21): toda alarma que aparece en CICLO queda en alarmas_historial
# con su ciclo_id, también (1) en el primer tick de CICLO, antes de que el
# CycleLogger abra el registro, (2) mientras la tarea asíncrona que crea el
# ciclo en la base no ha fijado el id y (3) después del cierre, mientras la
# máquina sigue en CICLO esperando la confirmación. Fuera de CICLO, sin ciclo.

import threading
from types import SimpleNamespace

import pytest

from autoclave.services.domain.logging.cycle_logger import CycleLogger
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.services.domain.logging.historial_alarmas import HistorialAlarmas
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import COM_01, PRE_06, SEN_11
from autoclave.state_machine.machine.enum_global import GlobalState

pytestmark = pytest.mark.req("FC-03")


class Estado:
    def __init__(self):
        self.maquina = GlobalState.PREPARADO
        self.fase_ciclo = ""
        self.sub_estado_ciclo = ""
        self.motivo_fallo = ""
        self.f0_acumulado = 0.0
        self.sensores_temp = {"temp_camara": 80.0}
        self.sensores_pres = {"pres_camara": 101.3}

    def get_machine_state(self):
        return self.maquina


class Ciclo:
    id = "instrumental_134"
    name = "Instrumental 134"

    def get_param(self, *claves, default=None):
        return default


class EjecutorRetenido:
    """Ejecutor de la base que retiene las tareas hasta `soltar()` (simula la
    tarea asíncrona de EscritorBD que aún no ha creado el ciclo)."""

    def __init__(self):
        self.tareas = []
        self.retener = False

    def __call__(self, tarea):
        if self.retener:
            self.tareas.append(tarea)
        else:
            tarea()

    def soltar(self):
        self.retener = False
        while self.tareas:
            self.tareas.pop(0)()


@pytest.fixture
def entorno(tmp_path):
    db = DbManager(tmp_path / "a.db")
    estado = Estado()
    ejecutor = EjecutorRetenido()
    logger = CycleLogger(
        db=db, estado=estado,
        config=SimpleNamespace(get=lambda *a, **k: 99999),
        profile=SimpleNamespace(serial_number="S", model_id="M"),
        cycle_manager=SimpleNamespace(get_selected_cycle=lambda: Ciclo()),
        ejecutar_bd=ejecutor,
    )
    am = AlarmManager()
    hist = HistorialAlarmas(db, am, ciclo_actual=logger.ciclo_para_alarma,
                            espera_ciclo_s=3.0)
    yield db, estado, logger, am, hist, ejecutor
    hist.detener()
    db.close()


def _filas(db, hist):
    assert hist.vaciar()
    return {f["codigo"]: f["ciclo_id"] for f in db.get_alarmas_historial()}


def _iniciar(estado, logger):
    estado.maquina, estado.fase_ciclo = GlobalState.CICLO, "PRECALENTAMIENTO"
    logger.update()


def test_fuera_de_ciclo_la_alarma_no_tiene_ciclo(entorno):
    db, _, _, am, hist, _ = entorno
    am.activar(COM_01)
    assert _filas(db, hist)["COM-01"] is None


def test_alarma_con_ciclo_en_curso(entorno):
    db, estado, logger, am, hist, _ = entorno
    _iniciar(estado, logger)
    assert logger.ciclo_id is not None
    am.activar(COM_01)
    assert _filas(db, hist)["COM-01"] == logger.ciclo_id


def test_alarma_antes_de_que_la_base_fije_el_id(entorno):
    db, estado, logger, am, hist, ejecutor = entorno
    ejecutor.retener = True
    _iniciar(estado, logger)
    assert logger.ciclo_id is None          # la creación sigue en la cola
    am.activar(COM_01)                      # el hilo que activa no espera
    temporizador = threading.Timer(0.2, ejecutor.soltar)
    temporizador.start()
    filas = _filas(db, hist)
    temporizador.join()
    assert logger.ciclo_id is not None
    assert filas["COM-01"] == logger.ciclo_id


def test_alarma_en_el_primer_tick_de_ciclo_antes_del_registro(entorno):
    db, estado, logger, am, hist, _ = entorno
    # paso 5 del tick: la máquina ya está en CICLO; el CycleLogger (paso 6) aún no
    estado.maquina, estado.fase_ciclo = GlobalState.CICLO, "PRECALENTAMIENTO"
    am.activar(COM_01)
    logger.update()
    ciclo = logger.ciclo_id
    assert ciclo is not None
    assert _filas(db, hist)["COM-01"] == ciclo


def test_alarma_tras_el_cierre_esperando_confirmacion(entorno):
    db, estado, logger, am, hist, _ = entorno
    _iniciar(estado, logger)
    ciclo = logger.ciclo_id
    estado.fase_ciclo, estado.motivo_fallo = "CANCELADO", "Cancelado"
    logger.update()
    assert logger.ciclo_id is None and logger.ciclo_id_pantalla == ciclo
    am.activar(PRE_06, temp=70.0, maximo=65.0)
    am.activar(SEN_11, sensor="temp_ref", fase="ESTERILIZACION")
    filas = _filas(db, hist)
    assert filas["PRE-06"] == ciclo
    assert filas["SEN-11"] == ciclo
    # confirmado: la máquina sale de CICLO y las alarmas ya no son del ciclo
    estado.maquina = GlobalState.PREPARADO
    logger.update()
    am.activar(COM_01)
    assert _filas(db, hist)["COM-01"] is None


def test_sin_base_no_espera(entorno):
    _, estado, logger, _, _, _ = entorno
    logger.sin_base_de_datos = True
    _iniciar(estado, logger)
    assert logger.ciclo_para_alarma() is None
