"""Q1 / T2-c (tanda 7, decisión 1.3 de Cristian; SAF-06 de T2): la marca
"CARGA NO ESTÉRIL" va en TODO ciclo que no termine COMPLETADO: FALLO,
CANCELADO, paro de emergencia e INTERRUMPIDO (en vivo y en la reimpresión;
es/en, cp437). Un resultado desconocido o vacío también la lleva (falla
segura)."""

import pytest

from autoclave.services.domain.logging import ticket_formatter as tf
from autoclave.services.domain.logging.ticket_formatter import Presentacion, format_footer
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.test_t2_p9_reimprimir_interrumpido import _fila

# Resultados reales: CycleLogger cierra con estado.fase_ciclo
NO_COMPLETADOS = ["CANCELADO", "EMERGENCIA", "INTERRUMPIDO", "FALLO_CALENTAMIENTO",
                  "FALLO_ESTERILIZACION", "FALLO_CONEXION", "FALLO_IO", "FALLO_SUMINISTRO",
                  "FALLO_PUERTA_1_ABIERTA", "SENSOR_AUSENTE", "DESCONOCIDO", "", None]


@pytest.mark.parametrize("resultado", NO_COMPLETADOS)
def test_todo_lo_que_no_es_completado_lleva_la_marca(resultado):
    es = format_footer(resultado, "2026-10-22T08:00:00", p=Presentacion(idioma="es"))
    en = format_footer(resultado, "2026-10-22T08:00:00", p=Presentacion(idioma="en"))
    assert "*** CARGA NO ESTÉRIL ***" in es
    assert "*** LOAD NOT STERILE ***" in en
    es.encode("cp437")
    en.encode("cp437")


def test_completado_no_lleva_la_marca():
    for idioma in ("es", "en"):
        pie = format_footer("COMPLETADO", "2026-10-22T08:00:00", p=Presentacion(idioma=idioma))
        assert "ESTÉRIL" not in pie and "NOT STERILE" not in pie


@pytest.mark.parametrize("resultado", ["CANCELADO", "FALLO_CALENTAMIENTO", "EMERGENCIA"])
def test_reimpresion_lleva_la_marca(resultado):
    assert "CARGA NO ESTÉRIL" in tf.format_ticket(_fila(resultado), [])


def test_ticket_en_vivo_de_un_cancelado_lleva_la_marca():
    from tests.test_cycle_logger_printer import FakePrinter, _build_logger
    printer = FakePrinter()
    cl = _build_logger(printer)
    cl.update()
    cl.update()
    cl.estado.fase_ciclo = "CANCELADO"
    cl.estado.machine_state = GlobalState.PREPARADO
    cl.update()
    assert "CARGA NO ESTÉRIL" in printer.calls[-1]
