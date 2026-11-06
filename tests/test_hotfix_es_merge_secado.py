"""Unión del hotfix ES con la tanda 28 (6-nov-2026, decisiones D4 y D6 de
Cristian): el secado tras fallo (A13) corre solo en CICLO, en el
ProtocoloFallo de CicloState mientras espera la confirmación, y NUNCA deja la
cámara no segura indefinidamente: al salir de CICLO `estado.secado_tras_fallo`
queda en un estado final (hecho, omitido, sin_vacio, sin_ruptura o cortado),
nunca "pendiente"; tras un reinicio vale None.

Piezas reales: StateMachine, CicloState, ProtocoloFallo, camara_segura y
ControlLoop._seguir_secado_tras_fallo; salidas en el doble de A13.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime import camara_segura
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.services.domain.loop.control_loop import ControlLoop
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.state_machine.state_machine import StateMachine
from autoclave.state_machine.states.ciclo import CicloResultado
from tests.test_t28b_a13_secado_tras_fallo import ATM, VACIO, _Equipo, _perfil

FINALES = ("hecho", "omitido", "sin_vacio", "sin_ruptura", "cortado")


def _maquina(e, resultado=CicloResultado.FALLO):
    """StateMachine real en CICLO con el resultado pendiente de confirmación
    y el ProtocoloFallo del equipo ya disparado."""
    e.estado.set_machine_state(GlobalState.CICLO)
    sm = StateMachine(io=MagicMock(), estado=e.estado, set_do=e.salidas, cycle=e.programa,
                      config=e.config, alarm_manager=e.alarmas, profile=_perfil())
    sm.prev_state = GlobalState.CICLO
    sm.ciclo._protocolo = e.protocolo
    e.protocolo.ejecutar()
    sm.ciclo._resultado_pendiente = resultado
    return sm


def _confirmar(e, sm):
    e.estado.set_flag("CICLO_CONFIRMADO", True)
    sm.update(datos_vigentes=True)


def _no_abrir(e):
    return camara_segura.evaluar(e.estado, e.config, [e.programa])[0] is False


def _sin_vacio_encendido(e):
    return not any(e.salidas.on(s) for s in VACIO)


@pytest.mark.parametrize("resultado, destino", [(CicloResultado.FALLO, GlobalState.FALLA),
                                                (CicloResultado.CANCELADO, GlobalState.PREPARADO)])
def test_confirmar_durante_el_secado_lo_corta_y_queda_final(monkeypatch, resultado, destino):
    e = _Equipo(monkeypatch)
    sm = _maquina(e, resultado)
    sm.update(datos_vigentes=True)                     # llega a la banda: empieza en CICLO
    assert e.protocolo.secando and all(e.salidas.on(s) for s in VACIO)
    assert e.estado.secado_tras_fallo["estado"] == "pendiente" and _no_abrir(e)
    _confirmar(e, sm)
    assert e.estado.get_machine_state() == destino
    r = e.estado.secado_tras_fallo
    assert r["estado"] == "cortado" and r["estado"] in FINALES
    assert e.estado.secando_tras_fallo is False and not e.protocolo.secando
    assert _sin_vacio_encendido(e)
    # NO ABRIR no queda pegado por el secado: la cámara en la banda y fría es segura
    assert not _no_abrir(e)
    # nadie lo continúa fuera de CICLO
    n = len(e.salidas.historial)
    for _ in range(20):
        sm.update(datos_vigentes=True)
        e.reloj[0] += 0.25
    assert ("bomba_vacio", True) not in e.salidas.historial[n:]
    assert ("vacio_camara", True) not in e.salidas.historial[n:]
    assert e.estado.secado_tras_fallo["estado"] == "cortado"


def test_confirmar_con_el_secado_pendiente_lo_omite(monkeypatch):
    e = _Equipo(monkeypatch)
    e.pres(200.0)                                      # todavía no llega a la banda
    sm = _maquina(e)
    sm.update(datos_vigentes=True)
    assert e.estado.secado_tras_fallo["estado"] == "pendiente"
    _confirmar(e, sm)
    assert e.estado.get_machine_state() == GlobalState.FALLA
    assert e.estado.secado_tras_fallo == {"estado": "omitido", "motivo": "no_aplica",
                                          "segundos": None}
    # con la presión en la banda, el secado pendiente ya no es motivo de NO ABRIR
    e.pres(ATM)
    assert not _no_abrir(e)


def test_secado_terminado_en_ciclo_conserva_su_resultado_al_salir(monkeypatch):
    e = _Equipo(monkeypatch, segundos=2)
    e.config["secado_tras_fallo_vacio_s"] = 1
    sm = _maquina(e)
    sm.update(datos_vigentes=True)
    e.pres(20.0)
    for _ in range(200):
        if e.protocolo._secado_fase == "ruptura":
            e.pres(ATM)
        e.reloj[0] += 0.25
        sm.update(datos_vigentes=True)
        if not e.protocolo.secando:
            break
    assert e.estado.secado_tras_fallo["estado"] == "hecho"
    _confirmar(e, sm)
    assert e.estado.secado_tras_fallo["estado"] == "hecho"


def test_un_error_al_cortar_no_lo_deja_pendiente(monkeypatch):
    e = _Equipo(monkeypatch)
    sm = _maquina(e)
    sm.update(datos_vigentes=True)
    assert e.protocolo.secando
    monkeypatch.setattr(e.protocolo, "cortar_secado",
                        MagicMock(side_effect=RuntimeError("falla interna")))
    _confirmar(e, sm)                                  # la transición no se impide
    assert e.estado.get_machine_state() == GlobalState.FALLA
    assert e.estado.secado_tras_fallo["estado"] in FINALES
    assert e.estado.secando_tras_fallo is False
    assert _sin_vacio_encendido(e)


def test_completado_no_deja_secado_publicado(monkeypatch):
    e = _Equipo(monkeypatch)
    e.estado.set_machine_state(GlobalState.CICLO)
    sm = StateMachine(io=MagicMock(), estado=e.estado, set_do=e.salidas, cycle=e.programa,
                      config=e.config, alarm_manager=e.alarmas, profile=_perfil())
    sm.prev_state = GlobalState.CICLO
    sm.ciclo._protocolo = e.protocolo
    sm.ciclo._resultado_pendiente = CicloResultado.COMPLETADO
    _confirmar(e, sm)
    assert e.estado.get_machine_state() == GlobalState.PREPARADO
    assert e.estado.secado_tras_fallo is None


def test_tras_un_reinicio_vale_none():
    estado = EstadoAutoclave()
    assert estado.secado_tras_fallo is None and estado.secando_tras_fallo is False
    assert camara_segura.secado_pendiente(estado) is False


def test_el_control_loop_registra_inicio_y_fin_del_secado(monkeypatch):
    e = _Equipo(monkeypatch)
    sm = _maquina(e)
    eventos = []
    registro = SimpleNamespace(state_machine=sm, _secado_visto=None,
                               _evento_seguridad=lambda ev, det: eventos.append((ev, det)))
    sm.update(datos_vigentes=True)
    ControlLoop._seguir_secado_tras_fallo(registro)
    _confirmar(e, sm)
    ControlLoop._seguir_secado_tras_fallo(registro)
    assert [ev for ev, _ in eventos] == ["estado_seguro_secado_iniciado",
                                         "estado_seguro_secado_terminado"]
    assert eventos[-1][1]["resultado"] == "cortado"
