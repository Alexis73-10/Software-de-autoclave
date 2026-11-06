"""Hotfix ES, revisión de seguridad (6-nov-2026): correcciones ALTA y MEDIA.

1. ALTA: tras soltar un paro real y antes de «Confirmar» ninguna puerta se
   abre ni se cierra (ServicioPuertas) y SetOutput no enciende nada salvo el
   buzzer, así que AdvancedDoor.update() ya no re-afirma cerrar_on /
   bloquear_on entre dos ALL_OFF. El modo prueba conserva su control manual.
2. MEDIA: FALLA y PREPARACION tratan la presión con la trama AI vencida
   (posiblemente congelada) como sin dato: no abren aire ni venteo.
3. MEDIA: al pasar de COMPLETADO a PREPARADO se cierran las válvulas de
   descompresión que dejó la válvula de reposo del modo.
"""

from unittest.mock import MagicMock, patch

import pytest

from tests.helpers.arranque_doble import evento_liberado
from autoclave.core.managers.cycle_manager import Cycle
from autoclave.core.runtime import motivos
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.devices.io.set_io import SetOutput
from autoclave.devices.puertas.advanced_door import AdvancedDoor
from autoclave.devices.puertas.enum_doors import DoorState
from autoclave.services.domain.puertas.ser_puertas import ServicioPuertas
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.state_machine.state_machine import StateMachine

_VALORES = {"presion_admosferica": 101.3, "rango_presion_atm": 10.0, "temp_max_apertura": 80.0,
            "temp_segura_drenaje": 60.0, "rango_temp_drenaje": 5.0}
BUZZER = EstadoAutoclave.map_do["buzer_alarma"] + 1


class _Config(dict):
    def get(self, k, d=None):
        return super().get(k, d)


class _Io:
    """Doble del enlace: registra las órdenes por canal y acepta el ALL_OFF."""

    def __init__(self):
        self.ordenes = []

    def set_output(self, canal, valor):
        self.ordenes.append((canal, bool(valor)))
        return True

    def all_off(self, timeout=1.0):
        self.ordenes.append(("ALL_OFF", None))
        return True


def _canal(nombre):
    return EstadoAutoclave.map_do[nombre] + 1


def _programa(tipo="solido", modo=1):
    return Cycle("p", "Prog", {"globals": {"tipo_carga": {"value": tipo},
                                           "presion_chaqueta": {"value": 200.0},
                                           "rango_presion_chaqueta": {"value": 20.0}},
                               "descompresion": {"modo": {"value": modo}}}, number=1)


# ── 1. ALTA: paro soltado sin confirmar ────────────────────────────────────

def _planta_paro():
    """PREPARADO con una AdvancedDoor real cerrada (empaque bajo: re-afirma
    cerrar_on y bloquear_on en cada tick), SetOutput real y la StateMachine
    real con su ConfirmacionParo, cableados como en el ControlLoop."""
    estado = EstadoAutoclave()
    estado.set_machine_state(GlobalState.PREPARADO)
    estado.set_flag("PARO_EMERGENCIA", False)
    estado.set_flag("PARO_REAL", False)
    estado.sensores_pres["pres_camara"] = 101.3
    estado.sensores_temp["temp_camara"] = 40.0
    estado.update_door_state("Puerta 1", DoorState.CERRADO)
    estado.sensores_di["puerta_1_abierta"] = 0
    estado.sensores_di["puerta_1_cerrada"] = 1
    estado.sensores_pres["pres_empaque_1"] = 100.0
    io = _Io()
    set_do = SetOutput(io, estado, profile=None)
    puerta = AdvancedDoor(
        name="Puerta 1",
        di={"abierta": "puerta_1_abierta", "cerrada": "puerta_1_cerrada"},
        do={"cerrar": _canal("cerrar_puerta_1"), "bloquear": _canal("bloqueo_puerta_1")},
        ai={"presion_empaque": "pres_empaque_1"},
        estado=estado, setdo=set_do,
        config={"presion_empaque": 300, "timeout_puerta": 60, "vacio_empaque": 30,
                "presion_admosferica": 101.3, "rango_presion_atm": 10},
        alarm_manager=None)
    programa = _programa()
    sm = StateMachine(io=MagicMock(), estado=estado, set_do=set_do, cycle=programa,
                      config=_Config(_VALORES), programas_seguridad=lambda: [programa])
    set_do.paro_sin_confirmar = sm.estado_seguro.esperando_confirmacion
    return estado, io, set_do, puerta, sm


def _tick(puerta, sm):
    # orden de ControlLoop._tick: puertas (paso 3) → máquina de estados (paso 5)
    puerta.update()
    sm.update()


def test_tras_soltar_el_paro_la_puerta_no_reenciende_salidas_hasta_confirmar():
    estado, io, set_do, puerta, sm = _planta_paro()
    _tick(puerta, sm)
    assert (_canal("cerrar_puerta_1"), True) in io.ordenes     # antes del paro, sí
    estado.set_flag("PARO_EMERGENCIA", True)
    estado.set_flag("PARO_REAL", True)
    _tick(puerta, sm)
    estado.set_flag("PARO_EMERGENCIA", False)
    estado.set_flag("PARO_REAL", False)
    io.ordenes.clear()
    for _ in range(6):
        _tick(puerta, sm)
    assert sm.estado_seguro.esperando_confirmacion() is True
    encendidos = [c for c, v in io.ordenes if v is True and c != BUZZER]
    assert encendidos == [], io.ordenes
    # cerrar/bloquear se reafirman apagadas: sin conmutar en cada tick
    assert (_canal("cerrar_puerta_1"), False) in io.ordenes
    # «Confirmar»: la puerta vuelve a sostener su cierre
    assert sm.confirmar_paro() is True
    io.ordenes.clear()
    puerta.update()
    assert (_canal("cerrar_puerta_1"), True) in io.ordenes
    assert (_canal("bloqueo_puerta_1"), True) in io.ordenes


def test_sin_confirmar_el_buzzer_si_conmuta_y_apagar_pasa():
    estado = EstadoAutoclave()
    io = _Io()
    s = SetOutput(io, estado, profile=None)
    s.paro_sin_confirmar = lambda: True
    s.buzer_on()
    s.vapor_chaqueta_on()
    s.vapor_chaqueta_off()
    assert io.ordenes == [(BUZZER, True), (_canal("vapor_chaqueta"), False),
                          (_canal("vapor_chaqueta"), False)]


def test_consulta_de_la_confirmacion_que_falla_no_enciende():
    estado = EstadoAutoclave()
    io = _Io()
    s = SetOutput(io, estado, profile=None)

    def roto():
        raise RuntimeError("x")
    s.paro_sin_confirmar = roto
    s.vapor_camara_on()
    assert io.ordenes == [(_canal("vapor_camara"), False)]


def test_sin_espera_de_confirmacion_setoutput_no_cambia():
    io = _Io()
    s = SetOutput(io, EstadoAutoclave(), profile=None)
    s.paro_sin_confirmar = lambda: False
    s.vapor_camara_on()
    assert io.ordenes == [(_canal("vapor_camara"), True)]


def _loop_real_setdo():
    from autoclave.services.domain.loop.control_loop import ControlLoop
    estado = EstadoAutoclave()
    io = _Io()
    set_do = SetOutput(io, estado, profile=None)
    cm = MagicMock()
    cm.get_selected_cycle.return_value = None
    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(arranque_liberado=evento_liberado(), units=MagicMock(),
                           door_service=MagicMock(), doors=[], estado=estado,
                           link=MagicMock(), set_do=set_do, alarm_manager=MagicMock(),
                           cycle_manager=cm, config_manager=MagicMock())
    # el ControlLoop arranca con PARO_EMERGENCIA (sin datos del módulo E/S)
    estado.set_flag("PARO_EMERGENCIA", False)
    estado.set_flag("PARO_REAL", False)
    return loop, estado, io, set_do


def test_control_loop_cablea_la_espera_y_el_modo_prueba_conserva_el_manual():
    loop, estado, io, set_do = _loop_real_setdo()
    assert set_do.paro_sin_confirmar is not None
    loop.estado_seguro.requiere_confirmacion = True       # paro real ya soltado
    set_do.set_output(_canal("cerrar_puerta_1"), True)
    assert io.ordenes[-1] == (_canal("cerrar_puerta_1"), False)
    loop._test_mode.set()                                  # salidas manuales
    set_do.set_output(_canal("cerrar_puerta_1"), True)
    assert io.ordenes[-1] == (_canal("cerrar_puerta_1"), True)
    loop._test_mode.clear()
    loop.estado_seguro.requiere_confirmacion = False       # confirmado
    set_do.set_output(_canal("bloqueo_puerta_1"), True)
    assert io.ordenes[-1] == (_canal("bloqueo_puerta_1"), True)


class _EstadoPuertas:
    def __init__(self):
        self.sensores_pres = {"pres_camara": 75.0, "pres_empaque_1": 75.0}
        self.sensores_temp = {"temp_camara": 40.0}
        self.sensores_di = {}
        self.puertas = {"Puerta 1": DoorState.CERRADO}
        self.flags = {}

    def get_flag(self, nombre):
        return self.flags.get(nombre, False)

    def get_door_state(self, nombre):
        return self.puertas.get(nombre, DoorState.DESCONOCIDO)

    def update_door_state(self, nombre, valor):
        self.puertas[nombre] = valor


def _servicio(paro_sin_confirmar):
    estado = _EstadoPuertas()
    config = {"presion_admosferica": 75.0, "rango_presion_atm": 5.0, "temp_max_apertura": 120.0}
    puerta = AdvancedDoor("Puerta 1", {}, {}, {"presion_empaque": "pres_empaque_1"}, estado,
                          MagicMock(), dict(config), MagicMock())
    return ServicioPuertas([puerta], estado, MagicMock(), config,
                           paro_sin_confirmar=paro_sin_confirmar), estado


def test_servicio_puertas_no_abre_ni_cierra_con_el_paro_sin_confirmar():
    servicio, estado = _servicio(lambda: True)
    ok, motivo = servicio.request_open("Puerta 1")
    assert ok is False and motivo.codigo == "paro_sin_confirmar"
    assert estado.puertas["Puerta 1"] == DoorState.CERRADO     # no se envió la orden
    estado.puertas["Puerta 1"] = DoorState.ABIERTO
    ok, motivo = servicio.request_close("Puerta 1")
    assert ok is False and motivo.codigo == "paro_sin_confirmar"
    assert estado.puertas["Puerta 1"] == DoorState.ABIERTO
    assert "Emergency stop" in motivos.texto(motivo, "en")


def test_servicio_puertas_consulta_que_falla_rechaza_y_confirmado_abre():
    def roto():
        raise RuntimeError("x")
    servicio, _ = _servicio(roto)
    assert servicio.request_open("Puerta 1")[0] is False
    servicio, estado = _servicio(lambda: False)
    assert servicio.request_open("Puerta 1") == (True, "")
    assert estado.puertas["Puerta 1"] == DoorState.ABRIENDO


# ── 2. MEDIA: FALLA y PREPARACION con la trama AI vencida ──────────────────

def _sm_presion(estado_maquina, pres, ai_vigente):
    estado = EstadoAutoclave()
    estado.set_flag("PARO_EMERGENCIA", False)
    estado.set_flag("PARO_REAL", False)
    estado.sensores_pres["pres_camara"] = pres
    # proveedor común del ControlLoop (core/runtime/vigencia_ai.py)
    estado.lectura_ai = lambda: (ai_vigente, 7)
    programa = _programa("liquido")
    set_do = MagicMock()
    sm = StateMachine(io=MagicMock(), estado=estado, set_do=set_do, cycle=programa,
                      config=_Config(_VALORES), programas_seguridad=lambda: [programa])
    estado.set_machine_state(estado_maquina)
    return sm, estado, set_do


def _abre_algo_de_camara(set_do):
    return (set_do.aire_admosferico_camara_on.called
            or set_do.descompresion_lenta_on.called
            or set_do.descompresion_rapida_on.called)



@pytest.mark.parametrize("estado_maquina", [GlobalState.FALLA, GlobalState.PREPARACION])
@pytest.mark.parametrize("pres", [40.0, 250.0], ids=["vacio", "sobrepresion"])
def test_presion_con_trama_ai_vencida_no_acciona_la_camara(estado_maquina, pres):
    sm, estado, set_do = _sm_presion(estado_maquina, pres, ai_vigente=False)
    sm.update()
    assert not _abre_algo_de_camara(set_do), set_do.method_calls


@pytest.mark.parametrize("estado_maquina", [GlobalState.FALLA, GlobalState.PREPARACION])
def test_presion_con_trama_ai_vigente_nivela_como_antes(estado_maquina):
    sm, estado, set_do = _sm_presion(estado_maquina, 40.0, ai_vigente=True)
    sm.update()
    set_do.aire_admosferico_camara_on.assert_called()


def test_proveedor_de_vigencia_que_falla_cuenta_como_vencida():
    sm, estado, set_do = _sm_presion(GlobalState.FALLA, 40.0, ai_vigente=True)

    def roto():
        raise RuntimeError("x")
    estado.lectura_ai = roto
    sm.update()
    assert not _abre_algo_de_camara(set_do)


# ── 3. MEDIA: COMPLETADO → PREPARADO cierra las válvulas de reposo ─────────

def _sm_completado(set_do, estado):
    cycle = MagicMock()
    cycle.copia.return_value = cycle
    cycle.sensores = None
    sm = StateMachine(io=MagicMock(), estado=estado, set_do=set_do, cycle=cycle,
                      config=_Config(_VALORES))
    estado.set_machine_state(GlobalState.CICLO)
    sm.prev_state = GlobalState.CICLO
    sm.ciclo.run = MagicMock(return_value="COMPLETADO")
    sm.ciclo._protocolo = MagicMock()
    return sm


def test_completado_a_preparado_cierra_las_valvulas_de_descompresion():
    # modo 4/5 sólido: la válvula de reposo dejaba abiertas la de chaqueta y
    # la rápida al entrar a PREPARADO, con vapor_chaqueta encendida
    estado = EstadoAutoclave()
    estado.set_flag("PARO_EMERGENCIA", False)
    estado.set_flag("PARO_REAL", False)
    io = _Io()
    set_do = SetOutput(io, estado, profile=None)
    set_do.descompresion_chaqueta_on()
    set_do.descompresion_rapida_on()
    sm = _sm_completado(set_do, estado)
    io.ordenes.clear()
    sm.update()
    assert estado.get_machine_state() == GlobalState.PREPARADO
    for nombre in ("descompresion_chaqueta", "descompresion_rapida", "descompresion_lenta"):
        assert (_canal(nombre), False) in io.ordenes, nombre
    # el protocolo de fallo no corre ni se finaliza en un COMPLETADO
    sm.ciclo._protocolo.ejecutar.assert_not_called()


def test_error_al_cerrar_las_valvulas_no_impide_pasar_a_preparado():
    estado = EstadoAutoclave()
    set_do = MagicMock()
    set_do.descompresion_rapida_off.side_effect = RuntimeError("x")
    sm = _sm_completado(set_do, estado)
    sm.update()
    assert estado.get_machine_state() == GlobalState.PREPARADO
