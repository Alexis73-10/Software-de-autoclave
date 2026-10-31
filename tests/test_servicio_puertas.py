# ServicioPuertas (planeacion_backend_autenticacion.md §5.3; T-13 y T-18):
# condiciones físicas que fallan cerradas, configuración leída en vivo,
# cierre rechazado con estado DESCONOCIDO, presión del empaque solo en puertas
# con empaque (AdvancedDoor) y resultado real de la orden. Sin hardware: las
# puertas avanzadas se construyen con dobles; SimpleDoor es real.

import math
from unittest.mock import MagicMock

import pytest

from autoclave.devices.puertas.advanced_door import AdvancedDoor
from autoclave.devices.puertas.enum_doors import DoorState
from autoclave.devices.puertas.simple_door import SimpleDoor
from autoclave.services.domain.puertas.ser_puertas import ServicioPuertas

CONFIG = {"presion_admosferica": 75.0, "rango_presion_atm": 5.0, "temp_max_apertura": 120.0}


class Estado:
    def __init__(self):
        self.sensores_pres = {"pres_camara": 75.0, "pres_empaque_1": 75.0, "pres_empaque_2": 75.0}
        self.sensores_temp = {"temp_camara": 40.0}
        self.sensores_di = {}
        self.puertas = {}
        self.flags = {}

    def get_flag(self, nombre):
        return self.flags.get(nombre, False)

    def set_flag(self, nombre, valor):
        self.flags[nombre] = valor

    def get_door_state(self, nombre):
        return self.puertas.get(nombre, DoorState.DESCONOCIDO)

    def update_door_state(self, nombre, valor):
        self.puertas[nombre] = valor


def _avanzada(nombre, estado, di=None, empaque=True):
    """Como la fábrica: solo el tipo ADVANCED declara la presión del empaque."""
    ai = {"presion_empaque": f"pres_empaque_{nombre.split()[-1]}"} if empaque else {}
    return AdvancedDoor(nombre, di or {}, {}, ai, estado, MagicMock(), dict(CONFIG), MagicMock())


@pytest.fixture
def entorno():
    estado = Estado()
    config = dict(CONFIG)
    p1 = _avanzada("Puerta 1", estado, di={"bloqueo": "bloqueo_1"})
    p2 = _avanzada("Puerta 2", estado)
    estado.puertas = {"Puerta 1": DoorState.CERRADO, "Puerta 2": DoorState.CERRADO}
    servicio = ServicioPuertas([p1, p2], estado, MagicMock(), config)
    return servicio, estado, config


# ── Apertura (T-13) ───────────────────────────────────────────────────────────

def test_apertura_con_todo_en_orden(entorno):
    servicio, estado, _ = entorno
    assert servicio.request_open("Puerta 1") == (True, "")
    assert estado.puertas["Puerta 1"] == DoorState.ABRIENDO


@pytest.mark.parametrize("sensor,valor", [
    ("pres_camara", None), ("pres_camara", float("nan")), ("pres_camara", "x"),
    ("temp_camara", None), ("temp_camara", math.inf), ("temp_camara", True),
])
def test_apertura_sin_lectura_valida_se_rechaza(entorno, sensor, valor):
    servicio, estado, _ = entorno
    (estado.sensores_pres if sensor.startswith("pres") else estado.sensores_temp)[sensor] = valor
    ok, motivo = servicio.request_open("Puerta 1")
    assert not ok and "Sin lectura válida" in motivo
    assert estado.puertas["Puerta 1"] == DoorState.CERRADO      # no se envió la orden


@pytest.mark.parametrize("clave", ["presion_admosferica", "rango_presion_atm", "temp_max_apertura"])
def test_apertura_sin_configuracion_se_rechaza(entorno, clave):
    servicio, _, config = entorno
    del config[clave]
    ok, motivo = servicio.request_open("Puerta 1")
    assert not ok and clave in motivo


def test_la_configuracion_se_lee_en_vivo(entorno):
    """OPC-11: un cambio de configuración aplica sin recrear el servicio."""
    servicio, estado, config = entorno
    estado.sensores_temp["temp_camara"] = 100.0
    config["temp_max_apertura"] = 90.0
    ok, motivo = servicio.request_open("Puerta 1")
    assert not ok and "Temperatura demasiado alta" in motivo


@pytest.mark.parametrize("pres,fragmento", [(81.0, "Sobrepresión"), (69.0, "vacío")])
def test_apertura_fuera_de_la_banda_atmosferica(entorno, pres, fragmento):
    servicio, estado, _ = entorno
    estado.sensores_pres["pres_camara"] = pres
    ok, motivo = servicio.request_open("Puerta 1")
    assert not ok and fragmento in motivo


@pytest.mark.parametrize("otra", [DoorState.ABIERTO, DoorState.DESCONOCIDO])
def test_apertura_con_la_otra_puerta_no_cerrada(entorno, otra):
    servicio, estado, _ = entorno
    estado.puertas["Puerta 2"] = otra
    ok, motivo = servicio.request_open("Puerta 1")
    assert not ok and "Puerta 2 no está cerrada" in motivo


# ── Resultado real (T-18) ─────────────────────────────────────────────────────

def test_bloqueo_mecanico_es_un_rechazo_y_no_cambia_el_estado(entorno):
    servicio, estado, _ = entorno
    estado.sensores_di["bloqueo_1"] = True
    ok, motivo = servicio.request_open("Puerta 1")
    assert not ok and motivo == "Puerta bloqueada mecánicamente"
    assert estado.puertas["Puerta 1"] == DoorState.CERRADO


def test_cerrar_una_puerta_que_no_esta_abierta_es_un_rechazo(entorno):
    servicio, estado, _ = entorno
    estado.puertas["Puerta 1"] = DoorState.ABRIENDO
    ok, motivo = servicio.request_close("Puerta 1")
    assert not ok and "no está abierta" in motivo


def test_puerta_sin_actuador_acepta_e_indica_que_no_mueve_nada():
    estado = Estado()
    puerta = SimpleDoor("Puerta 1", {"cerrada": "puerta_1_cerrada"}, estado)
    estado.puertas = {"Puerta 1": DoorState.CERRADO}
    servicio = ServicioPuertas([puerta], estado, MagicMock(), dict(CONFIG))
    assert servicio.request_open("Puerta 1") == (True, "")
    assert servicio.tiene_actuador("Puerta 1") is False


# ── Cierre (T-13) ─────────────────────────────────────────────────────────────

def test_cierre_con_todo_en_orden(entorno):
    servicio, estado, _ = entorno
    estado.puertas["Puerta 1"] = DoorState.ABIERTO
    assert servicio.request_close("Puerta 1") == (True, "")
    assert estado.puertas["Puerta 1"] == DoorState.CERRANDO
    assert servicio.tiene_actuador("Puerta 1") is True


def test_cierre_con_estado_desconocido_se_rechaza(entorno):
    """Decisión 18: la posición segura es abierta."""
    servicio, estado, _ = entorno
    estado.puertas["Puerta 1"] = DoorState.DESCONOCIDO
    ok, motivo = servicio.request_close("Puerta 1")
    assert not ok and "desconocido" in motivo


@pytest.mark.parametrize("sensor", ["pres_camara", "pres_empaque_1"])
def test_cierre_sin_presion_que_interviene_se_rechaza(entorno, sensor):
    servicio, estado, _ = entorno
    estado.puertas["Puerta 1"] = DoorState.ABIERTO
    estado.sensores_pres[sensor] = None
    ok, motivo = servicio.request_close("Puerta 1")
    assert not ok and "Sin lectura válida" in motivo


def test_cierre_sin_configuracion_atmosferica_se_rechaza(entorno):
    servicio, estado, config = entorno
    estado.puertas["Puerta 1"] = DoorState.ABIERTO
    del config["rango_presion_atm"]
    ok, motivo = servicio.request_close("Puerta 1")
    assert not ok and "rango_presion_atm" in motivo


def test_cierre_no_mira_temperatura_ni_vacio(entorno):
    """Decisión 18: sin comprobación de vacío ni de temperatura al cerrar."""
    servicio, estado, _ = entorno
    estado.puertas["Puerta 1"] = DoorState.ABIERTO
    estado.sensores_temp["temp_camara"] = None
    estado.sensores_pres["pres_camara"] = 10.0
    assert servicio.request_close("Puerta 1") == (True, "")


def test_puerta_sin_empaque_no_exige_su_presion():
    estado = Estado()
    estado.sensores_pres = {"pres_camara": 75.0}
    puerta = SimpleDoor("Puerta 1", {"cerrada": "puerta_1_cerrada"}, estado)
    estado.puertas = {"Puerta 1": DoorState.ABIERTO}
    servicio = ServicioPuertas([puerta], estado, MagicMock(), dict(CONFIG))
    assert servicio.request_close("Puerta 1") == (True, "")


# ── Revisión de seguridad de la etapa 2 ───────────────────────────────────────

@pytest.mark.parametrize("estado_puerta", [DoorState.CERRANDO, DoorState.ABRIENDO,
                                           DoorState.ATRAPADA])
def test_no_se_abre_una_puerta_en_movimiento(entorno, estado_puerta):
    """TMG-01/SAF-01: abrir durante el cierre energizaba abrir y cerrar a la vez."""
    servicio, estado, _ = entorno
    estado.puertas["Puerta 1"] = estado_puerta
    ok, motivo = servicio.request_open("Puerta 1")
    assert not ok and "movimiento" in motivo
    assert estado.puertas["Puerta 1"] == estado_puerta


def test_abrir_una_puerta_abierta_se_rechaza(entorno):
    servicio, estado, _ = entorno
    estado.puertas["Puerta 1"] = DoorState.ABIERTO
    assert servicio.request_open("Puerta 1") == (False, "La puerta ya está abierta")


def test_abrir_desde_error_arranca_con_plazo_nuevo(entorno):
    servicio, estado, _ = entorno
    puerta = servicio.doors["Puerta 1"]
    estado.puertas["Puerta 1"] = DoorState.ERROR
    puerta.timer_start = 123.0            # plazo viejo de un movimiento fallido
    assert servicio.request_open("Puerta 1") == (True, "")
    assert puerta.timer_start is None     # _from_abriendo apagará cerrar/bloquear


@pytest.mark.parametrize("accion", ["abrir", "cerrar"])
def test_con_paro_de_emergencia_no_se_mueve_ninguna_puerta(entorno, accion):
    """TMG-02/SAF-05: también cubre la apertura automática, que usa request_open."""
    servicio, estado, _ = entorno
    estado.flags["PARO_EMERGENCIA"] = True
    if accion == "abrir":
        ok, motivo = servicio.request_open("Puerta 1")
    else:
        estado.puertas["Puerta 1"] = DoorState.ABIERTO
        ok, motivo = servicio.request_close("Puerta 1")
    assert not ok and motivo == "Paro de emergencia activado"


def test_puerta_avanzada_sin_empaque_no_exige_su_presion():
    """SAF-06: LOCKING/MOTORIZED usan AdvancedDoor pero no tienen empaque."""
    estado = Estado()
    estado.sensores_pres = {"pres_camara": 75.0}
    puerta = _avanzada("Puerta 1", estado, empaque=False)
    estado.puertas = {"Puerta 1": DoorState.ABIERTO}
    servicio = ServicioPuertas([puerta], estado, MagicMock(), dict(CONFIG))
    assert servicio.request_close("Puerta 1") == (True, "")
