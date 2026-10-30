"""U4 (tanda 2, 19-oct): módulo E/S desconectado vs. paro de emergencia.

Instrucción: docs/mis_plans/instruccion_claude_code_u4_tarjeta_desconectada.md.
- El flag combinado PARO_EMERGENCIA (paro real o sin datos, D-16/A-3) sigue
  bloqueando y apagando salidas como antes.
- PARO_REAL = enlace conectado + DI vigente + entrada en 0. SIS-01 y la
  exigencia de "Confirmar y llevar a estado seguro" dependen solo de él.
- Estado del módulo E/S: desconectada / sin_tramas_validas / ok (falla cerrada:
  sin dato = desconectada).
- COM-01 solo con el módulo E/S desconectado; TARJETA_SIN_TRAMA_VALIDA solo con
  el puerto presente; nunca las dos a la vez."""

from unittest.mock import MagicMock, patch

import pytest

from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.devices.paro_emergencia.paro_emergencia import EmergencyStop
from autoclave.protocols.enlace import EventoModuloEs
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import (
    CATALOGO, COM_01, COM_03, SIS_01, TARJETA_SIN_TRAMA_VALIDA,
)
from autoclave.state_machine.estado_seguro import ProtocoloEstadoSeguro
from tests.helpers.backend_doble import modulo_backend


# ---------------------------------------------------------------------------
# EmergencyStop: flag combinado y paro real
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("valor,combinado,real", [
    (None, True, False),      # sin datos: bloquea, pero no es paro real
    (0, True, True),
    (False, True, True),
    (1, False, False),
    (True, False, False),
])
def test_paro_real_solo_con_entrada_en_cero(valor, combinado, real):
    estado = EstadoAutoclave()
    paro = EmergencyStop(estado)
    paro.update(valor)
    assert estado.get_flag("PARO_EMERGENCIA") is combinado
    assert estado.get_flag("PARO_REAL") is real
    assert paro.real is real


def test_al_construir_bloquea_sin_paro_real():
    estado = EstadoAutoclave()
    EmergencyStop(estado)
    assert estado.get_flag("PARO_EMERGENCIA") is True
    assert estado.get_flag("PARO_REAL") is False


# ---------------------------------------------------------------------------
# ControlLoop: estado del módulo E/S, paro real y alarmas
# ---------------------------------------------------------------------------

def _loop(estado=None, alarm_manager=None):
    from autoclave.services.domain.loop.control_loop import ControlLoop
    estado = estado or EstadoAutoclave()
    cm = MagicMock()
    cm.get_selected_cycle.return_value = MagicMock()
    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(units=MagicMock(), door_service=MagicMock(), doors=[],
                           estado=estado, link=MagicMock(), set_do=MagicMock(),
                           alarm_manager=alarm_manager or MagicMock(), cycle_manager=cm,
                           config_manager=MagicMock())
    loop.units.get_all.return_value = {}
    loop.link.tomar_eventos.return_value = []
    loop.link.expansor_fuera_de_linea.return_value = False
    estado.sensores_di["paro_emergencia"] = 1
    estado.sensores_di["suministro_electrico"] = 1
    _enlace(loop, presente=False, conectado=False, edad=None)
    return loop, estado


def _enlace(loop, presente, conectado, edad):
    loop.link.puerto_presente.return_value = presente
    loop.link.is_connected.return_value = conectado
    loop.link.edad_ultima_di.return_value = edad


def _tick(loop, ahora):
    with patch("autoclave.services.domain.loop.control_loop.time.monotonic", return_value=ahora):
        loop._tick()


def test_estado_del_modulo_es_antes_del_primer_tick_es_desconectada():
    loop, _ = _loop()
    assert loop.estado_modulo_es == "desconectada"


@pytest.mark.parametrize("presente,conectado,edad,esperado", [
    (False, False, None, "desconectada"),            # puerto ausente
    (True, False, None, "sin_tramas_validas"),       # puerto abierto, sin handshake/tramas
    (True, True, 3.0, "sin_tramas_validas"),         # DI vencida con enlace
    (True, True, None, "sin_tramas_validas"),        # conectada sin primera DI
    (True, True, 0.1, "ok"),
])
def test_estado_del_modulo_es(presente, conectado, edad, esperado):
    loop, _ = _loop()
    _enlace(loop, presente, conectado, edad)
    _tick(loop, 100.0)
    assert loop.estado_modulo_es == esperado


def test_enlace_sin_puerto_presente_informado_se_deduce_de_la_conexion():
    # enlaces dobles viejos (MagicMock sin bool): sin conexión = desconectada
    loop, _ = _loop()
    loop.link.puerto_presente.return_value = MagicMock()
    loop.link.is_connected.return_value = False
    _tick(loop, 100.0)
    assert loop.estado_modulo_es == "desconectada"


def test_firmware_incompatible_es_sin_tramas_validas():
    loop, _ = _loop()
    _enlace(loop, presente=True, conectado=False, edad=None)
    loop.link.tomar_eventos.return_value = [
        EventoModuloEs("handshake", "TARJETA_VERSION_INCOMPATIBLE", "Firmware 0.9")]
    _tick(loop, 100.0)
    assert loop.estado_modulo_es == "sin_tramas_validas"
    loop.alarm_manager.activar.assert_any_call("TARJETA_VERSION_INCOMPATIBLE", motivo="Firmware 0.9")


@pytest.mark.parametrize("presente,conectado,edad", [
    (False, False, None), (True, False, None), (True, True, 3.0), (True, True, None),
])
def test_sin_datos_bloquea_sin_paro_real(presente, conectado, edad):
    loop, estado = _loop()
    _enlace(loop, presente, conectado, edad)
    _tick(loop, 100.0)
    assert estado.get_flag("PARO_EMERGENCIA") is True
    assert estado.get_flag("PARO_REAL") is False


def test_di_vigente_en_cero_es_paro_real():
    loop, estado = _loop()
    _enlace(loop, presente=True, conectado=True, edad=0.1)
    estado.sensores_di["paro_emergencia"] = 0
    _tick(loop, 100.0)
    _tick(loop, 100.5)
    assert estado.get_flag("PARO_REAL") is True


def test_cero_en_la_primera_di_vigente_de_la_conexion_no_es_paro_real():
    # TMG-04: el enlace fija la edad de la DI antes de notificar a Units; en
    # ese tick Units aún puede tener el 0 de _connect()
    loop, estado = _loop()
    estado.sensores_di["paro_emergencia"] = 0
    _enlace(loop, presente=True, conectado=True, edad=0.1)
    _tick(loop, 100.0)
    assert estado.get_flag("PARO_EMERGENCIA") is True
    assert estado.get_flag("PARO_REAL") is False
    _tick(loop, 100.5)                 # segundo tick vigente: ya es dato real
    assert estado.get_flag("PARO_REAL") is True
    # nueva conexión: vuelve a enmascararse la primera DI
    _enlace(loop, presente=True, conectado=False, edad=None)
    _tick(loop, 101.0)
    _enlace(loop, presente=True, conectado=True, edad=0.1)
    _tick(loop, 101.5)
    assert estado.get_flag("PARO_REAL") is False


def test_uno_en_la_primera_di_vigente_libera_el_paro():
    loop, estado = _loop()
    _enlace(loop, presente=True, conectado=True, edad=0.1)
    _tick(loop, 100.0)
    assert estado.get_flag("PARO_EMERGENCIA") is False


def test_di_inicial_en_cero_al_conectar_no_es_paro_real():
    # _connect() deja las DI en 0 hasta la primera trama (A-3)
    loop, estado = _loop()
    estado.sensores_di["paro_emergencia"] = 0
    _enlace(loop, presente=True, conectado=True, edad=None)
    _tick(loop, 100.0)
    _tick(loop, 101.0)
    _tick(loop, 103.0)        # vencida la ventana de la primera DI
    assert estado.get_flag("PARO_EMERGENCIA") is True
    assert estado.get_flag("PARO_REAL") is False


def test_paro_real_y_luego_desconexion_deja_de_ser_real():
    loop, estado = _loop()
    _enlace(loop, presente=True, conectado=True, edad=0.1)
    estado.sensores_di["paro_emergencia"] = 0
    _tick(loop, 100.0)
    _tick(loop, 100.5)
    assert estado.get_flag("PARO_REAL") is True
    _enlace(loop, presente=False, conectado=False, edad=None)
    _tick(loop, 101.0)
    assert estado.get_flag("PARO_EMERGENCIA") is True     # sigue bloqueando
    assert estado.get_flag("PARO_REAL") is False          # ya no se sabe


def _activadas(am):
    return [c.args[0] for c in am.activar.call_args_list]


def _resueltas(am):
    return [c.args[0] for c in am.resolver.call_args_list]


def test_arranque_sin_modulo_es_da_com01_una_vez_y_nunca_sin_trama():
    loop, _ = _loop()
    for t in (100.0, 102.0, 104.9):
        _tick(loop, t)
    assert COM_01 not in _activadas(loop.alarm_manager)       # tolerancia de arranque
    for t in (105.0, 110.0, 120.0):
        _tick(loop, t)
    assert _activadas(loop.alarm_manager).count(COM_01) == 1
    assert TARJETA_SIN_TRAMA_VALIDA not in _activadas(loop.alarm_manager)


def test_puerto_presente_sin_tramas_nunca_da_com01():
    loop, _ = _loop()
    _enlace(loop, presente=True, conectado=False, edad=None)
    for t in (100.0, 106.0, 130.0):
        _tick(loop, t)
    assert COM_01 not in _activadas(loop.alarm_manager)


def test_com01_y_sin_trama_son_excluyentes():
    loop, _ = _loop()
    am = loop.alarm_manager
    # conectada y sana
    _enlace(loop, presente=True, conectado=True, edad=0.1)
    _tick(loop, 100.0)
    # se desconecta el cable: COM-01 en el flanco
    _enlace(loop, presente=False, conectado=False, edad=None)
    _tick(loop, 101.0)
    assert _activadas(am).count(COM_01) == 1
    # vuelve el puerto pero el módulo E/S no habla: se resuelve COM-01 y el
    # handshake reporta la falta de tramas
    _enlace(loop, presente=True, conectado=False, edad=None)
    loop.link.tomar_eventos.return_value = [
        EventoModuloEs("handshake", TARJETA_SIN_TRAMA_VALIDA, "No llegó ninguna trama válida.")]
    _tick(loop, 120.0)
    loop.link.tomar_eventos.return_value = []
    assert COM_01 in _resueltas(am)
    assert TARJETA_SIN_TRAMA_VALIDA in _activadas(am)
    # se vuelve a quitar el cable: COM-01 otra vez y se resuelve la de tramas
    _enlace(loop, presente=False, conectado=False, edad=None)
    _tick(loop, 130.0)
    assert TARJETA_SIN_TRAMA_VALIDA in _resueltas(am)
    assert _activadas(am).count(COM_01) == 2
    assert TARJETA_SIN_TRAMA_VALIDA not in loop._alarmas_modulo_es


def test_com01_y_sin_trama_nunca_activas_a_la_vez_con_alarm_manager_real():
    am = AlarmManager()
    loop, _ = _loop(alarm_manager=am)
    secuencia = [
        (True, True, 0.1, []),
        (False, False, None, []),
        (True, False, None, [EventoModuloEs("handshake", TARJETA_SIN_TRAMA_VALIDA, "x")]),
        (True, False, None, []),
        (False, False, None, []),
        (True, True, 0.1, [EventoModuloEs("conectada", None, "ok")]),
    ]
    for i, (presente, conectado, edad, eventos) in enumerate(secuencia):
        _enlace(loop, presente, conectado, edad)
        loop.link.tomar_eventos.return_value = eventos
        _tick(loop, 100.0 + 10 * i)
        activas = {inst.codigo for inst in am.activas() if inst.estado.name == "ACTIVA"}
        assert not {COM_01, TARJETA_SIN_TRAMA_VALIDA} <= activas, (i, activas)
    activas = {inst.codigo for inst in am.activas() if inst.estado.name == "ACTIVA"}
    assert COM_01 not in activas and TARJETA_SIN_TRAMA_VALIDA not in activas


def test_di_vencida_con_enlace_da_sin_trama_y_se_resuelve_al_volver():
    loop, _ = _loop()
    am = loop.alarm_manager
    _enlace(loop, presente=True, conectado=True, edad=0.1)
    _tick(loop, 100.0)
    _enlace(loop, presente=True, conectado=True, edad=3.0)
    _tick(loop, 101.0)
    _tick(loop, 101.5)
    assert TARJETA_SIN_TRAMA_VALIDA not in _activadas(am)            # debounce (TMG-03)
    _tick(loop, 102.0)
    assert _activadas(am).count(TARJETA_SIN_TRAMA_VALIDA) == 1
    assert COM_01 not in _activadas(am)
    _tick(loop, 102.5)
    assert _activadas(am).count(TARJETA_SIN_TRAMA_VALIDA) == 1       # sin repetir
    _enlace(loop, presente=True, conectado=True, edad=0.1)
    _tick(loop, 103.0)
    assert TARJETA_SIN_TRAMA_VALIDA in _resueltas(am)


def test_di_que_oscila_no_activa_la_alarma():
    # TMG-03: vigencia que cruza 1,5 s en ticks alternos
    loop, _ = _loop()
    for i, edad in enumerate([0.1, 1.6, 0.1, 1.6, 0.1, 1.6, 0.1]):
        _enlace(loop, presente=True, conectado=True, edad=edad)
        _tick(loop, 100.0 + 0.5 * i)
    assert TARJETA_SIN_TRAMA_VALIDA not in _activadas(loop.alarm_manager)


def test_cierre_por_timeout_de_datos_no_resuelve_la_alarma_propia():
    # TMG-01: el enlace cierra el puerto a los 3 s y reintenta; la causa sigue
    loop, _ = _loop()
    am = loop.alarm_manager
    _enlace(loop, presente=True, conectado=True, edad=0.1)
    _tick(loop, 100.0)
    _enlace(loop, presente=True, conectado=True, edad=3.0)
    for t in (101.0, 101.5, 102.0):
        _tick(loop, t)
    assert TARJETA_SIN_TRAMA_VALIDA in _activadas(am)
    _enlace(loop, presente=True, conectado=False, edad=None)
    _tick(loop, 103.0)
    assert TARJETA_SIN_TRAMA_VALIDA not in _resueltas(am)
    assert loop.estado_modulo_es == "sin_tramas_validas"


def test_handshake_cortado_por_desconexion_no_da_segunda_alarma():
    # TMG-02: con el cable quitado, el handshake reporta el paso en que iba
    loop, _ = _loop()
    _enlace(loop, presente=False, conectado=False, edad=None)
    loop.link.tomar_eventos.return_value = [
        EventoModuloEs("handshake", "TARJETA_VERSION_INCOMPATIBLE", "No respondió a VER.")]
    _tick(loop, 100.0)
    assert "TARJETA_VERSION_INCOMPATIBLE" not in _activadas(loop.alarm_manager)
    assert "TARJETA_VERSION_INCOMPATIBLE" not in loop._alarmas_modulo_es


def test_primera_di_pendiente_no_da_sin_trama():
    loop, _ = _loop()
    _enlace(loop, presente=True, conectado=True, edad=None)
    _tick(loop, 100.0)
    _tick(loop, 101.0)        # dentro de la ventana de la primera DI
    assert TARJETA_SIN_TRAMA_VALIDA not in _activadas(loop.alarm_manager)


# ---------------------------------------------------------------------------
# Estados: SIS-01 solo con paro real; las salidas se apagan igual
# ---------------------------------------------------------------------------

def _estado_flags(combinado, real):
    e = MagicMock()
    e.get_flag.side_effect = lambda f: {"PARO_EMERGENCIA": combinado, "PARO_REAL": real}.get(f, False)
    e.sensores_di = {}
    return e


def _estados():
    from autoclave.state_machine.states.falla import FallaState
    from autoclave.state_machine.states.preparacion import preparacion_state
    from autoclave.state_machine.states.preparado import preparado_state

    def _prep(am, e, s):
        p = preparacion_state(am, e, s, MagicMock(), MagicMock())
        p.supervisor = MagicMock(return_value=False)
        p._salidas_seguras_supervisor = MagicMock()
        return p.run()

    return {
        "preparacion": _prep,
        "preparado": lambda am, e, s: preparado_state(am, e, s, MagicMock(), MagicMock()).run(),
        "falla": lambda am, e, s: FallaState(e, s, am).run(),
    }


@pytest.mark.parametrize("nombre", ["preparacion", "preparado", "falla"])
def test_sin_datos_apaga_salidas_sin_sis01(nombre):
    am, set_do = AlarmManager(), MagicMock()
    _estados()[nombre](am, _estado_flags(combinado=True, real=False), set_do)
    set_do.apagar_por_paro.assert_called()
    assert SIS_01 not in {i.codigo for i in am.activas()}


@pytest.mark.parametrize("nombre", ["preparacion", "preparado", "falla"])
def test_paro_real_apaga_salidas_con_sis01(nombre):
    am, set_do = AlarmManager(), MagicMock()
    _estados()[nombre](am, _estado_flags(combinado=True, real=True), set_do)
    set_do.apagar_por_paro.assert_called()
    assert SIS_01 in {i.codigo for i in am.activas()}


# Revisión SAF-03 de U4: perder los datos no resuelve un SIS-01 ya activo (el
# botón puede seguir pulsado); solo no se activa sin paro real.
@pytest.mark.parametrize("nombre", ["preparacion", "preparado", "falla"])
def test_sis01_no_se_resuelve_por_perder_los_datos(nombre):
    am = AlarmManager()
    _estados()[nombre](am, _estado_flags(combinado=True, real=True), MagicMock())
    _estados()[nombre](am, _estado_flags(combinado=True, real=False), MagicMock())
    activas = [i for i in am.activas() if i.codigo == SIS_01 and i.estado.name == "ACTIVA"]
    assert len(activas) == 1


def test_sis01_ya_no_dice_sin_datos():
    d = CATALOGO[SIS_01]
    assert "sin datos" not in d.descripcion.lower()


def test_com01_texto_de_modulo_es_desconectado():
    d = CATALOGO[COM_01]
    assert d.titulo == "Módulo E/S desconectado"
    assert d.descripcion == "No se detecta el módulo E/S."
    # T20-03 (DECISIÓN SIN CONFIRMAR): «cable USB» -> «cable de red» (Modbus TCP)
    assert d.accion == "Conecte el módulo E/S (cable de red) y verifique su alimentación."


# ---------------------------------------------------------------------------
# Ciclo: sin datos en ciclo no se registra como paro (protocolo intacto)
# ---------------------------------------------------------------------------

def _ciclo(combinado, real):
    from autoclave.state_machine.states.ciclo import CicloState
    cycle = MagicMock()
    cycle.copia.return_value = cycle
    cycle.get_param.return_value = None
    config = MagicMock()
    config.get.return_value = None
    estado = _estado_flags(combinado, real)
    estado.sensores_pres = {}
    estado.sensores_temp = {}
    am = AlarmManager()
    ciclo = CicloState(estado, MagicMock(), cycle, config, am)
    ciclo.reset()
    ciclo._protocolo = MagicMock()
    ciclo.run()
    return ciclo, am


def test_ciclo_sin_datos_registra_com03_con_el_mismo_protocolo(monkeypatch):
    # P-3 (tanda 6): pasada la tolerancia de la DI vencida (aquí 0 s)
    from autoclave.state_machine.states import ciclo as modulo_ciclo
    monkeypatch.setattr(modulo_ciclo, "_TOLERANCIA_DI_VENCIDA_SEG", 0.0)
    ciclo, am = _ciclo(combinado=True, real=False)
    codigos = {i.codigo for i in am.activas()}
    assert SIS_01 not in codigos and COM_03 in codigos
    ciclo._protocolo.ejecutar.assert_called_once_with(abrir_valvulas=False)
    assert ciclo._paro_en_espera is True      # se mantiene la confirmación de hoy


def test_ciclo_paro_real_registra_sis01():
    ciclo, am = _ciclo(combinado=True, real=True)
    assert SIS_01 in {i.codigo for i in am.activas()}
    ciclo._protocolo.ejecutar.assert_called_once_with(abrir_valvulas=False)


# ---------------------------------------------------------------------------
# Estado seguro: solo un paro real exige confirmación
# ---------------------------------------------------------------------------

def _protocolo_es():
    estado = EstadoAutoclave()
    es = ProtocoloEstadoSeguro(estado, MagicMock(), programas_seguridad=lambda: [])
    es.iniciar(MagicMock(ejecutado=True))
    return es, estado


def test_estado_seguro_sin_datos_no_pide_confirmacion():
    es, estado = _protocolo_es()
    estado.set_flag("PARO_EMERGENCIA", True)          # sin datos (desconexión)
    es.update(datos_vigentes=False)
    assert es.requiere_confirmacion is False
    es._protocolo.update.assert_not_called()          # pausado mientras tanto
    # reconexión sin paro real: sigue solo, sin confirmación
    estado.set_flag("PARO_EMERGENCIA", False)
    es.update(datos_vigentes=True)
    assert es.requiere_confirmacion is False
    es._protocolo.update.assert_called_once()


def test_estado_seguro_paro_real_pide_confirmacion():
    es, estado = _protocolo_es()
    estado.set_flag("PARO_EMERGENCIA", True)
    estado.set_flag("PARO_REAL", True)
    es.update(datos_vigentes=True)
    assert es.requiere_confirmacion is True
    estado.set_flag("PARO_EMERGENCIA", False)
    estado.set_flag("PARO_REAL", False)
    es.update(datos_vigentes=True)
    assert es.requiere_confirmacion is True           # hace falta confirmar
    es._protocolo.update.assert_not_called()
    assert es.confirmar() is True


def test_estado_seguro_paro_real_y_desconexion_sigue_pidiendo_confirmacion():
    es, estado = _protocolo_es()
    estado.set_flag("PARO_EMERGENCIA", True)
    estado.set_flag("PARO_REAL", True)
    es.update(datos_vigentes=True)
    estado.set_flag("PARO_REAL", False)               # se pierde el módulo E/S
    es.update(datos_vigentes=False)
    estado.set_flag("PARO_EMERGENCIA", False)         # reconecta sin paro
    es.update(datos_vigentes=True)
    assert es.requiere_confirmacion is True


def test_estado_seguro_sin_datos_no_registra_paro_activado():
    eventos = []
    estado = EstadoAutoclave()
    es = ProtocoloEstadoSeguro(estado, MagicMock(), programas_seguridad=lambda: [],
                               al_evento=lambda ev, det: eventos.append(ev))
    es.iniciar(MagicMock(ejecutado=True))
    estado.set_flag("PARO_EMERGENCIA", True)
    es.update(datos_vigentes=False)
    assert "paro_activado" not in eventos


# ---------------------------------------------------------------------------
# Backend: /status y textos de rechazo
# ---------------------------------------------------------------------------

def _cliente(flags, estado_modulo_es="ok"):
    import threading
    from fastapi.testclient import TestClient
    from autoclave.state_machine.machine.enum_global import GlobalState
    from tests.helpers.backend_doble import cargar_servidor
    ctx = MagicMock()
    ctx.estado.get_flag.side_effect = lambda f: flags.get(f, False)
    ctx.estado.get_machine_state.return_value = GlobalState.FALLA
    ctx.control_loop.bloqueo_maquina.return_value = threading.Lock()
    ctx.control_loop.test_mode_active = False
    ctx.control_loop.estado_modulo_es = estado_modulo_es
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app), srv, ctx


def test_confirmar_sin_datos_dice_la_causa_real():
    client, _, ctx = _cliente({"PARO_EMERGENCIA": True})
    r = client.post("/safe-state/confirm")
    assert r.status_code == 409 and r.json()["codigo"] == "paro_emergencia"
    assert "módulo e/s" in r.json()["detail"].lower()
    ctx.control_loop.confirmar_estado_seguro.assert_not_called()


def test_confirmar_con_paro_real_dice_paro():
    client, _, _ = _cliente({"PARO_EMERGENCIA": True, "PARO_REAL": True})
    r = client.post("/safe-state/confirm")
    assert r.status_code == 409 and "Paro de emergencia" in r.json()["detail"]


@pytest.mark.parametrize("valor,esperado", [
    ("ok", "ok"), ("sin_tramas_validas", "sin_tramas_validas"),
    ("desconectada", "desconectada"), (None, "desconectada"), (MagicMock(), "desconectada"),
])
def test_status_publica_el_estado_del_modulo_es(valor, esperado):
    _, srv, _ = _cliente({}, estado_modulo_es=valor)
    assert modulo_backend("rutas.sistema")._estado_modulo_es() == esperado


def test_puerto_presente_sin_conexion_da_sin_trama_pasada_la_tolerancia():
    # revisión SAF-07: no esperar a que falle el handshake (15 s)
    loop, _ = _loop()
    _enlace(loop, presente=True, conectado=False, edad=None)
    _tick(loop, 100.0)
    _tick(loop, 104.0)
    assert TARJETA_SIN_TRAMA_VALIDA not in _activadas(loop.alarm_manager)
    _tick(loop, 105.0)
    assert _activadas(loop.alarm_manager).count(TARJETA_SIN_TRAMA_VALIDA) == 1
    assert COM_01 not in _activadas(loop.alarm_manager)
    # se conecta y la DI llega: se resuelve
    _enlace(loop, presente=True, conectado=True, edad=0.1)
    _tick(loop, 106.0)
    assert TARJETA_SIN_TRAMA_VALIDA in _resueltas(loop.alarm_manager)


def test_fallo_al_evaluar_el_modulo_es_no_impide_publicar_el_paro():
    # revisión SAF-05
    loop, estado = _loop()
    _enlace(loop, presente=True, conectado=True, edad=0.1)
    _tick(loop, 100.0)
    assert estado.get_flag("PARO_EMERGENCIA") is False
    loop.link.puerto_presente.side_effect = RuntimeError("roto")
    loop.link.is_connected.return_value = False
    _tick(loop, 101.0)
    assert estado.get_flag("PARO_EMERGENCIA") is True
    assert loop.estado_modulo_es == "desconectada"
