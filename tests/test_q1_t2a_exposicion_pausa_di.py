"""Q1 / T2-a (tanda 7, decisión 1.3 de Cristian; SAF-02 de T2): los segundos
de tolerancia por DI vencida NO cuentan como exposición en ESTERILIZACION.
El temporizador de exposición se pausa durante la tolerancia (time.monotonic)
y el ticket anota "Sin datos del módulo E/S: n s" (es/en, cp437)."""

import time
from unittest.mock import MagicMock

import pytest

from autoclave.state_machine.cycle_phases.esterilizacion import EsterilizacionFase
from autoclave.state_machine.states import ciclo as modulo_ciclo
from autoclave.state_machine.states.ciclo import CicloResultado
from autoclave.services.domain.logging.ticket_formatter import Presentacion, format_footer
from tests.test_t2_p3_di_vencida import _ciclo


@pytest.fixture
def reloj(monkeypatch):
    t = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    return t


def _en_esterilizacion(ciclo):
    idx = next(i for i, f in enumerate(ciclo._fases) if f.name == "ESTERILIZACION")
    ciclo._fase_idx = idx
    fase = ciclo._fases[idx]
    fase.update = MagicMock(return_value=None)
    fase.pausar_exposicion = MagicMock()
    return fase


def test_la_pausa_de_la_tolerancia_extiende_la_exposicion(reloj):
    flags = {"PARO_EMERGENCIA": True}
    ciclo, estado, _ = _ciclo(flags)
    estado.sin_datos_modulo_es_s = 0.0
    fase = _en_esterilizacion(ciclo)

    assert ciclo.run() == CicloResultado.EN_CURSO      # empieza la tolerancia
    reloj[0] += 1.5
    assert ciclo.run() == CicloResultado.EN_CURSO
    reloj[0] += 1.0
    fase.pausar_exposicion.assert_not_called()
    fase.update.assert_not_called()

    flags["PARO_EMERGENCIA"] = False                   # vuelven los datos
    ciclo.run()

    fase.pausar_exposicion.assert_called_once()
    assert fase.pausar_exposicion.call_args.args[0] == pytest.approx(2.5)
    assert estado.sin_datos_modulo_es_s == pytest.approx(2.5)
    fase.update.assert_called_once()


def test_varios_episodios_se_acumulan(reloj):
    flags = {"PARO_EMERGENCIA": True}
    ciclo, estado, _ = _ciclo(flags)
    estado.sin_datos_modulo_es_s = 0.0
    fase = _en_esterilizacion(ciclo)
    for dur in (1.0, 2.0):
        flags["PARO_EMERGENCIA"] = True
        ciclo.run()
        reloj[0] += dur
        flags["PARO_EMERGENCIA"] = False
        ciclo.run()
        reloj[0] += 0.5
    assert [c.args[0] for c in fase.pausar_exposicion.call_args_list] == [
        pytest.approx(1.0), pytest.approx(2.0)]
    assert estado.sin_datos_modulo_es_s == pytest.approx(3.0)


def test_tolerancia_vencida_anota_los_segundos_y_falla(reloj):
    flags = {"PARO_EMERGENCIA": True}
    ciclo, estado, _ = _ciclo(flags)
    estado.sin_datos_modulo_es_s = 0.0
    _en_esterilizacion(ciclo)
    ciclo.run()
    reloj[0] += modulo_ciclo._TOLERANCIA_DI_VENCIDA_SEG
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    assert estado.sin_datos_modulo_es_s == pytest.approx(modulo_ciclo._TOLERANCIA_DI_VENCIDA_SEG)


def test_cancelacion_al_volver_los_datos_igual_anota_los_segundos(reloj):
    flags = {"PARO_EMERGENCIA": True}
    ciclo, estado, _ = _ciclo(flags)
    estado.sin_datos_modulo_es_s = 0.0
    _en_esterilizacion(ciclo)
    ciclo.run()
    reloj[0] += 2.0
    flags.update({"PARO_EMERGENCIA": False, "CICLO_CANCELADO": True})
    ciclo.run()
    assert estado.fase_ciclo == "CANCELADO"
    assert estado.sin_datos_modulo_es_s == pytest.approx(2.0)


def test_reset_pone_el_contador_en_cero():
    ciclo, estado, _ = _ciclo({})
    estado.sin_datos_modulo_es_s = 7.0
    ciclo.reset()
    assert estado.sin_datos_modulo_es_s == 0.0


# ── EsterilizacionFase ──────────────────────────────────────────────────────

def _fase_ester(tiempo_min=1.0):
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": None}       # sin lectura: solo corre la inicialización
    estado.sensores_pres = {"pres_camara": None}
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda s, p, default=None: (
        tiempo_min if p == "tiempo_esterilizacion" else default)
    fase = EsterilizacionFase(estado, MagicMock(), cycle, MagicMock(), MagicMock(), None)
    fase.reset()
    return fase


def test_pausar_exposicion_corre_el_fin_de_la_fase(reloj):
    fase = _fase_ester()
    fase.update()
    fin = fase._timer_fin
    fase.pausar_exposicion(3.0)
    assert fase._timer_fin == pytest.approx(fin + 3.0)


def test_pausar_antes_de_iniciar_no_hace_nada(reloj):
    fase = _fase_ester()
    fase.pausar_exposicion(3.0)
    assert fase._timer_fin is None


@pytest.mark.parametrize("seg", [-1.0, float("nan"), None, "x"])
def test_pausa_invalida_se_ignora(reloj, seg):
    fase = _fase_ester()
    fase.update()
    fin = fase._timer_fin
    fase.pausar_exposicion(seg)
    assert fase._timer_fin == fin


# ── ticket ─────────────────────────────────────────────────────────────────

def test_pie_del_ticket_en_espanol_e_ingles_cp437():
    es = format_footer("COMPLETADO", "2026-10-22T08:00:00", sin_datos_s=3.4,
                       p=Presentacion(idioma="es"))
    en = format_footer("COMPLETADO", "2026-10-22T08:00:00", sin_datos_s=3.6,
                       p=Presentacion(idioma="en"))
    assert "Sin datos del módulo E/S: 3 s" in es
    assert "No I/O module data: 4 s" in en
    es.encode("cp437")
    en.encode("cp437")


@pytest.mark.parametrize("valor", [None, 0, 0.0])
def test_sin_episodios_no_hay_linea(valor):
    pie = format_footer("COMPLETADO", "2026-10-22T08:00:00", sin_datos_s=valor,
                        p=Presentacion(idioma="es"))
    assert "Sin datos del módulo E/S" not in pie


def test_cycle_logger_pasa_los_segundos_al_pie():
    from autoclave.state_machine.machine.enum_global import GlobalState
    from tests.test_cycle_logger_printer import FakePrinter, _build_logger
    printer = FakePrinter()
    cl = _build_logger(printer)
    cl.estado.sin_datos_modulo_es_s = 4.0
    cl.update()
    cl.update()
    cl.estado.machine_state = GlobalState.PREPARADO
    cl.update()
    assert "Sin datos del módulo E/S: 4 s" in printer.calls[-1]


def test_cycle_logger_sin_el_atributo_no_imprime_la_linea():
    from autoclave.state_machine.machine.enum_global import GlobalState
    from tests.test_cycle_logger_printer import FakePrinter, _build_logger
    printer = FakePrinter()
    cl = _build_logger(printer)
    cl.update()
    cl.update()
    cl.estado.machine_state = GlobalState.PREPARADO
    cl.update()
    assert "Sin datos del módulo E/S" not in printer.calls[-1]
