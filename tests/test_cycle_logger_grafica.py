# tests/test_cycle_logger_grafica.py
#
# CycleLogger alimenta la pantalla de ciclo en curso
# (planeacion_pantalla_ciclo_en_curso.md §6 B2/B3): serie de la gráfica cada
# ~1 s y tramos de fase, ambos con reloj monotónico (C-01).

from types import SimpleNamespace

import pytest

from autoclave.services.domain.logging.cycle_logger import CycleLogger
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.state_machine.machine.enum_global import GlobalState


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Estado:
    def __init__(self):
        self.maquina = GlobalState.PREPARADO
        self.fase_ciclo = ""
        self.sub_estado_ciclo = ""
        self.motivo_fallo = ""
        self.f0_acumulado = 0.0
        self.sensores_temp = {"temp_camara": 80.0, "temp_ref": 79.0}
        self.sensores_pres = {"pres_camara": 101.3}

    def get_machine_state(self):
        return self.maquina


class Ciclo:
    id = "instrumental_134"
    name = "Instrumental 134"

    def get_param(self, *claves, default=None):
        return default


@pytest.fixture
def entorno(tmp_path):
    db = DbManager(tmp_path / "a.db")
    estado = Estado()
    reloj = Reloj()
    logger = CycleLogger(
        db=db, estado=estado,
        config=SimpleNamespace(get=lambda *a, **k: 99999),
        profile=SimpleNamespace(serial_number="S", model_id="M"),
        cycle_manager=SimpleNamespace(get_selected_cycle=lambda: Ciclo()),
        reloj_mono=reloj,
    )
    yield db, estado, reloj, logger
    db.close()


def _iniciar(estado, logger, fase="PRECALENTAMIENTO"):
    estado.maquina = GlobalState.CICLO
    estado.fase_ciclo = fase
    logger.update()


def _avanzar(reloj, logger, segundos, paso=0.5):
    n = int(round(segundos / paso))
    for _ in range(n):
        reloj.t += paso
        logger.update()


def test_sin_ciclo_no_hay_ciclo_de_pantalla(entorno):
    _, _, _, logger = entorno
    logger.update()
    assert logger.ciclo_id_pantalla is None
    assert logger.transcurrido_s() is None


def test_grafica_muestrea_cada_segundo_con_temp_ref(entorno):
    db, estado, reloj, logger = entorno
    _iniciar(estado, logger)
    _avanzar(reloj, logger, 3.0)
    filas = db.get_lecturas_grafica(logger.ciclo_id_pantalla)
    assert [f["t_s"] for f in filas] == [0.0, 1.0, 2.0, 3.0]
    assert filas[0]["temp_ref"] == 79.0
    assert filas[0]["fase"] == "PRECALENTAMIENTO"


def test_grafica_no_se_adelanta_con_ticks_irregulares(entorno):
    db, estado, reloj, logger = entorno
    _iniciar(estado, logger)
    reloj.t += 2.7   # tick atrasado: una sola muestra, sin ráfaga de recuperación
    logger.update()
    reloj.t += 0.5
    logger.update()
    assert [f["t_s"] for f in db.get_lecturas_grafica(logger.ciclo_id_pantalla)] == [0.0, 2.7]


def test_tramos_de_fase_con_duracion(entorno):
    db, estado, reloj, logger = entorno
    _iniciar(estado, logger)
    _avanzar(reloj, logger, 2.0)
    estado.fase_ciclo = "PRE_VACIO"
    logger.update()   # el cambio se observa en este instante (t = 2.0)
    _avanzar(reloj, logger, 10.0)
    estado.fase_ciclo = "CALENTAMIENTO"
    logger.update()
    filas = [(f["fase"], f["inicio_s"], f["fin_s"], f["duracion_s"])
             for f in db.get_fases_ciclo(logger.ciclo_id_pantalla)]
    assert filas == [
        ("PRECALENTAMIENTO", 0.0, 2.0, 2.0),
        ("PRE_VACIO", 2.0, 12.0, 10.0),
        ("CALENTAMIENTO", 12.0, None, None),
    ]


def test_descompresion_y_secado_tienen_tramos_propios(entorno):
    db, estado, reloj, logger = entorno
    _iniciar(estado, logger, "DESCOMPRESION")
    _avanzar(reloj, logger, 4.0)
    estado.fase_ciclo = "SECADO"
    _avanzar(reloj, logger, 4.0)
    fases = [f["fase"] for f in db.get_fases_ciclo(logger.ciclo_id_pantalla)]
    assert fases == ["DESCOMPRESION", "SECADO"]
    # la gráfica sigue muestreando en ambas (el ticket no lo hace)
    assert len(db.get_lecturas_grafica(logger.ciclo_id_pantalla)) == 9


def test_transcurrido_es_monotonico_y_se_congela_al_completar(entorno):
    db, estado, reloj, logger = entorno
    _iniciar(estado, logger, "SECADO")
    _avanzar(reloj, logger, 5.0)
    assert logger.transcurrido_s() == 5.0
    estado.fase_ciclo = "COMPLETADO"   # espera confirmación: sigue en CICLO
    logger.update()
    _avanzar(reloj, logger, 30.0)
    assert logger.transcurrido_s() == 5.0
    cid = logger.ciclo_id_pantalla
    assert db.get_fases_ciclo(cid)[-1]["fin_s"] == 5.0
    assert len(db.get_lecturas_grafica(cid)) == 6   # sin muestras tras completar


def test_cancelado_mantiene_ciclo_de_pantalla_hasta_salir_de_ciclo(entorno):
    db, estado, reloj, logger = entorno
    _iniciar(estado, logger, "PRE_VACIO")
    cid = logger.ciclo_id_pantalla
    _avanzar(reloj, logger, 3.0)
    estado.fase_ciclo = "CANCELADO"
    logger.update()
    _avanzar(reloj, logger, 10.0)
    # el ticket ya se cerró, pero la pantalla sigue viendo el ciclo
    assert logger.ciclo_id is None
    assert logger.ciclo_id_pantalla == cid
    assert logger.transcurrido_s() == 3.0
    assert db.get_fases_ciclo(cid)[-1]["fin_s"] == 3.0
    estado.maquina = GlobalState.PREPARACION
    logger.update()
    assert logger.ciclo_id_pantalla is None
    assert logger.transcurrido_s() is None


def test_error_de_bd_en_la_grafica_no_interrumpe_el_logger(entorno, monkeypatch):
    db, estado, reloj, logger = entorno

    def falla(*a, **k):
        raise RuntimeError("disco lleno")

    monkeypatch.setattr(db, "insertar_lectura_grafica", falla)
    monkeypatch.setattr(db, "abrir_fase", falla)
    _iniciar(estado, logger)
    _avanzar(reloj, logger, 2.0)
    assert logger.activo
