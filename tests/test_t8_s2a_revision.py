"""Tanda 8 / S2a: correcciones de la revisión de seguridad y temporización
(SAF-05, TMG-01, TMG-02, TMG-04). Las del sellado de líquidos (SAF-01/02/03,
TMG-03/08) están en test_t8_s2a_210_liquidos_sellado.py y TMG-05 en
test_t8_s2a_29_tramas_di_distintas.py."""

import time
from unittest.mock import MagicMock

import pytest

from autoclave.state_machine.alarms.catalogo import CIC_11
from autoclave.state_machine.cycle_phases.esterilizacion import EsterilizacionFase
from autoclave.state_machine.states import ciclo as modulo_ciclo
from autoclave.state_machine.states.ciclo import CicloResultado
from tests.test_t2_p3_di_vencida import _ciclo


@pytest.fixture
def reloj(monkeypatch):
    t = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    return t


def _en_esterilizacion(ciclo, pausa_total=0.0, maximo=30.0):
    idx = next(i for i, f in enumerate(ciclo._fases) if f.name == "ESTERILIZACION")
    ciclo._fase_idx = idx
    fase = ciclo._fases[idx]
    fase.update = MagicMock(return_value=None)
    fase.pausa_total_s = pausa_total
    fase._pausa_max_s = lambda: maximo
    fase._timer_fin = 2000.0
    return fase


# ── SAF-05: enlace que va y viene, sin run(): CIC-11 desde el tramo abierto ─

def test_tramo_abierto_que_supera_el_tope_falla_con_cic_11(reloj):
    ciclo, estado, am = _ciclo({})
    estado.sin_datos_tarjeta_s = 0.0
    fase = _en_esterilizacion(ciclo, pausa_total=20.0, maximo=30.0)
    ciclo.marcar_sin_datos_tarjeta()
    reloj[0] += 9.5
    ciclo.marcar_sin_datos_tarjeta()
    assert ciclo._resultado_pendiente is None             # 29,5 s: todavía no
    reloj[0] += 1.0
    ciclo.marcar_sin_datos_tarjeta()                      # 30,5 s > 30
    assert ciclo._resultado_pendiente == CicloResultado.FALLO
    assert estado.fase_ciclo == "FALLO_ESTERILIZACION"
    assert CIC_11 in [i.codigo for i in am.activas()]
    assert fase.pausa_total_s == pytest.approx(30.5)
    ciclo._protocolo.ejecutar.assert_called()


def test_fuera_de_esterilizacion_el_tramo_abierto_no_falla(reloj):
    ciclo, _, _ = _ciclo({})
    ciclo.marcar_sin_datos_tarjeta()
    reloj[0] += 600.0
    ciclo.marcar_sin_datos_tarjeta()
    assert ciclo._resultado_pendiente is None


# ── TMG-01: el tramo empieza en la última DI válida ────────────────────────

def test_el_tramo_de_desconexion_empieza_en_la_ultima_di_valida(reloj):
    ciclo, estado, _ = _ciclo({})
    estado.sin_datos_tarjeta_s = 0.0
    fase = _en_esterilizacion(ciclo)
    fase.pausar_exposicion = MagicMock()
    estado.ultima_di_valida_mono = reloj[0] - 1.5
    ciclo.marcar_sin_datos_tarjeta()
    reloj[0] += 2.0
    ciclo.run()
    assert fase.pausar_exposicion.call_args.args[0] == pytest.approx(3.5)


def test_el_retroceso_tiene_tope(reloj):
    ciclo, estado, _ = _ciclo({})
    estado.sin_datos_tarjeta_s = 0.0
    fase = _en_esterilizacion(ciclo)
    fase.pausar_exposicion = MagicMock()
    estado.ultima_di_valida_mono = reloj[0] - 60.0         # dato viejo: no se cree
    ciclo.marcar_sin_datos_tarjeta()
    reloj[0] += 1.0
    ciclo.run()
    assert fase.pausar_exposicion.call_args.args[0] == pytest.approx(
        1.0 + modulo_ciclo._RETROCESO_MAX_TRAMO_SEG)


def test_la_tolerancia_di_tambien_cuenta_desde_la_ultima_di(reloj):
    flags = {"PARO_EMERGENCIA": True}
    ciclo, estado, _ = _ciclo(flags)
    estado.ultima_di_valida_mono = reloj[0] - 1.5
    assert ciclo.run() == CicloResultado.EN_CURSO
    reloj[0] += modulo_ciclo._TOLERANCIA_DI_VENCIDA_SEG - 1.5
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION


def test_control_loop_descuenta_el_f0_acreditado_tras_la_ultima_di():
    from tests.test_control_loop_f0 import _make_loop
    loop, estado, _ = _make_loop()
    loop.interval = 0.5
    ciclo = loop.state_machine.ciclo
    ciclo.tolerancia_di_activa = False
    ciclo.exposicion_en_pausa = False
    ciclo.pausa_sin_datos_desde = None
    for t in (1000.0, 1000.5, 1001.0, 1001.5, 1002.0):
        loop._acumular_f0(now=t)
    total = estado.f0_acumulado
    assert total > 0
    por_tick = total / 4
    # se abre un tramo con inicio en 1001.0: se descuentan los de 1001.5 y 1002.0
    ciclo.exposicion_en_pausa = True
    ciclo.pausa_sin_datos_desde = 1001.0
    loop._acumular_f0(now=1002.5)
    assert estado.f0_acumulado == pytest.approx(total - 2 * por_tick)
    loop._acumular_f0(now=1003.0)                          # una sola vez por tramo
    assert estado.f0_acumulado == pytest.approx(total - 2 * por_tick)


# ── TMG-02: tramas contadas antes de la caída no suman ─────────────────────

def test_desconexion_reinicia_las_tramas_contadas_de_la_tolerancia(reloj):
    flags = {"PARO_EMERGENCIA": True}
    ciclo, estado, _ = _ciclo(flags)
    ciclo.run()                                            # abre la tolerancia
    flags["PARO_EMERGENCIA"] = False
    estado.trama_di_nueva = True
    ciclo.run(); ciclo.run()                               # 2 tramas nuevas
    ciclo.marcar_sin_datos_tarjeta()                       # cae el enlace
    ciclo.run()                                            # 1 trama nueva más
    assert ciclo._di_vencida_desde is not None             # no se reinició con 2+1


# ── TMG-04: el aborto por desconexión va bajo _sm_lock ─────────────────────

def test_aborto_por_desconexion_bajo_el_lock():
    from autoclave.state_machine.machine.enum_global import GlobalState
    from tests.test_control_loop_test_mode import _make_control_loop
    loop, sm, estado = _make_control_loop()
    estado.set_machine_state(GlobalState.CICLO)
    loop.link.expansor_fuera_de_linea.return_value = False
    loop.link.tomar_eventos.return_value = []
    loop.link.is_connected.return_value = False
    loop.link_was_connected = False
    loop._desconectado_desde = -1e9
    visto = []
    sm.ciclo.abortar_por_desconexion.side_effect = (
        lambda **_: visto.append(loop._sm_lock.locked()
                                 if hasattr(loop._sm_lock, "locked") else True))
    loop._tick()
    assert visto and all(visto)
