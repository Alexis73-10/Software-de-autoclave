"""Tanda 28b (A13, revisión de seguridad): correcciones que no requerían
decisión de Cristian sobre el secado tras fallo.

- M1: un error en ProtocoloFallo.update() o en el estado seguro con el secado
  en curso no deja bomba y vacío con la última orden ON (MOD-08 no apaga: el
  lazo sigue): se corta con motivo "error".
- M2: sin presión atmosférica de referencia configurada la RUPTURA no abre el
  aire (el vacío no se rompería): el secado no empieza ("sin_referencia_atm")
  y, si la referencia se pierde a mitad, se corta.
- B1: un paro, el modo prueba o un error ANTES de que empiece el secado lo
  dejan OMITIDO con ese motivo (antes quedaba pendiente y podía arrancar).
- B2: con el ALL_OFF del disparo sin confirmar no empieza ni sigue (la bomba
  conmutaba cada tick: reset_all_outputs y luego bomba_vacio_on).
- B4: CicloState real con el resultado pendiente y paro; paso del secado de
  CicloState al estado seguro al confirmar; arranque tras ciclo interrumpido;
  trama AI vencida vista por el propio protocolo.

M3 (verificar el vacío), M4 (NO ABRIR durante el secado) y M5 (tipo de carga
en el ciclo interrumpido) esperan la decisión de Cristian.

Unión con el hotfix ES (6-nov, D1/D4/D5/D6): sin ProtocoloEstadoSeguro. Se
retiraron las pruebas del estado seguro (error atrapado por la máquina en el
estado seguro, pausa por modo prueba, datos no vigentes del estado seguro,
paso del secado al estado seguro y secado en el arranque tras un ciclo
interrumpido); el paso al salir de CICLO lo prueba
tests/test_hotfix_es_merge_secado.py (D6).
"""

from unittest.mock import MagicMock

import pytest

from autoclave.state_machine.states.ciclo import CicloResultado, CicloState
from tests.test_t28b_a13_secado_tras_fallo import ATM, VACIO, _Equipo, _en_secado, _perfil


def _vacio_apagado(e):
    return not any(e.salidas.on(s) for s in VACIO)


# ── M1: excepción con el secado en curso ───────────────────────────────────

def test_m1_excepcion_dentro_del_update_del_protocolo_corta_el_secado(monkeypatch):
    e = _en_secado(monkeypatch)
    monkeypatch.setattr(e.protocolo, "_seguir_presion_perdida",
                        MagicMock(side_effect=RuntimeError("falla interna")))
    with pytest.raises(RuntimeError):
        e.protocolo.update()
    assert _vacio_apagado(e) and not e.protocolo.secando
    assert e.protocolo.secado_resultado["estado"] == "cortado"
    assert e.protocolo.secado_resultado["motivo"] == "error"


def test_m1_excepcion_en_el_tick_del_secado_corta_el_secado(monkeypatch):
    e = _en_secado(monkeypatch)
    monkeypatch.setattr(e.protocolo, "_tick_secado",
                        MagicMock(side_effect=RuntimeError("falla interna")))
    with pytest.raises(RuntimeError):
        e.protocolo.update()
    assert _vacio_apagado(e) and e.protocolo.secado_resultado["motivo"] == "error"


def test_m1_error_antes_de_empezar_lo_omite(monkeypatch):
    e = _Equipo(monkeypatch)
    e.pres(200.0)
    e.disparar()
    e.protocolo.cortar_secado("error")
    assert e.protocolo.secado_resultado == {"estado": "omitido", "motivo": "error",
                                             "segundos": None}


# ── M2: referencia atmosférica ─────────────────────────────────────────────

@pytest.mark.parametrize("clave", ["presion_admosferica", "rango_presion_atm"])
def test_m2_sin_referencia_atmosferica_no_empieza(monkeypatch, clave):
    e = _Equipo(monkeypatch)
    del e.config[clave]
    e.disparar()
    for _ in range(10):
        e.tick()
        assert _vacio_apagado(e) and not e.protocolo.secando
    assert e.protocolo.secado_resultado["estado"] == "omitido"
    assert e.protocolo.secado_resultado["motivo"] == "sin_referencia_atm"


def test_m2_referencia_perdida_a_mitad_corta_el_secado(monkeypatch):
    e = _en_secado(monkeypatch)
    e.config["presion_admosferica"] = 0                  # inválida: no positiva
    e.tick()
    assert _vacio_apagado(e) and not e.salidas.on("aire_atmosferico_camara")
    assert e.protocolo.secado_resultado["motivo"] == "sin_referencia_atm"


# ── B1: paro o modo prueba antes de empezar ────────────────────────────────

def _antes_de_la_banda(monkeypatch):
    e = _Equipo(monkeypatch)
    e.pres(200.0)                                        # todavía presurizada
    e.disparar()
    e.tick()
    assert e.protocolo.secado_resultado["estado"] == "pendiente"
    return e


def test_b1_paro_antes_de_empezar_lo_omite(monkeypatch):
    e = _antes_de_la_banda(monkeypatch)
    e.estado.set_flag("PARO_EMERGENCIA", True)
    e.tick()
    e.estado.set_flag("PARO_EMERGENCIA", False)
    e.pres(ATM)
    for _ in range(20):
        e.tick()
        assert _vacio_apagado(e)
    assert e.protocolo.secado_resultado["estado"] == "omitido"
    assert e.protocolo.secado_resultado["motivo"] == "paro"


def _ciclo_real(e):
    """CicloState real con el ProtocoloFallo del equipo y el resultado
    FALLO pendiente de confirmación."""
    ciclo = CicloState(e.estado, e.salidas, e.programa, e.config, e.alarmas, None, None,
                       _perfil())
    ciclo._protocolo = e.protocolo
    e.protocolo.ejecutar()
    ciclo._resultado_pendiente = CicloResultado.FALLO
    return ciclo


def test_b4_ciclo_real_paro_con_resultado_pendiente_lo_omite(monkeypatch):
    e = _Equipo(monkeypatch)
    e.pres(200.0)
    ciclo = _ciclo_real(e)
    e.estado.set_flag("PARO_EMERGENCIA", True)
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    assert e.protocolo.secado_resultado["estado"] == "omitido"
    assert e.protocolo.secado_resultado["motivo"] == "paro"


def test_b4_ciclo_real_paro_durante_el_secado_lo_corta(monkeypatch):
    e = _Equipo(monkeypatch)
    ciclo = _ciclo_real(e)
    ciclo.run()
    assert e.protocolo.secando
    e.estado.set_flag("PARO_EMERGENCIA", True)
    ciclo.run()
    assert _vacio_apagado(e) and e.protocolo.secado_resultado["motivo"] == "paro"


# ── B2: ALL_OFF sin confirmar ──────────────────────────────────────────────

def test_b2_all_off_sin_confirmar_no_empieza_y_la_bomba_no_conmuta(monkeypatch):
    e = _Equipo(monkeypatch)
    e.salidas.reset_all_outputs = lambda: (e.salidas.historial.append(("ALL_OFF", False))
                                           or False)
    e.disparar()
    for _ in range(20):
        e.tick()
    assert ("bomba_vacio", True) not in e.salidas.historial
    assert ("vacio_camara", True) not in e.salidas.historial
    assert e.protocolo.secado_resultado["motivo"] == "salidas_sin_confirmar"


def test_b2_all_off_que_deja_de_confirmarse_corta(monkeypatch):
    e = _en_secado(monkeypatch)
    e.protocolo._salidas_apagadas = False
    e.salidas.reset_all_outputs = lambda: False
    e.tick()
    assert _vacio_apagado(e)
    assert e.protocolo.secado_resultado["motivo"] == "salidas_sin_confirmar"


# ── B4: trama AI vencida vista por el propio protocolo ─────────────────────

def test_b4_ai_vencida_vista_por_el_protocolo_corta_el_secado(monkeypatch):
    e = _en_secado(monkeypatch)
    e.estado.lectura_ai = lambda: (False, 7)             # datos DI vigentes, AI vencida
    e.tick()
    assert _vacio_apagado(e)
    assert e.protocolo.secado_resultado["motivo"] == "datos_no_vigentes"
