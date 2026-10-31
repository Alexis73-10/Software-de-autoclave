# tests/test_q1rev_no_esteril_igualdad_exacta.py
"""Revisión Q1 (SAF-05): la marca "CARGA NO ESTÉRIL" solo se omite con el
resultado exactamente "COMPLETADO" (el único valor real: CicloState fija
estado.fase_ciclo = "COMPLETADO" y CycleLogger cierra con ese texto). Un valor
que solo empiece por COMPLETADO es desconocido y lleva la marca."""

import pytest

from autoclave.services.domain.logging.ticket_formatter import Presentacion, format_footer


@pytest.mark.parametrize("resultado", ["COMPLETADO_PARCIAL", "COMPLETADOX",
                                       "COMPLETADO ", "completado"])
def test_variantes_de_completado_llevan_la_marca(resultado):
    pie = format_footer(resultado, "2026-10-22T08:00:00", p=Presentacion(idioma="es"))
    assert "*** CARGA NO ESTÉRIL ***" in pie


def test_completado_exacto_no_lleva_la_marca():
    pie = format_footer("COMPLETADO", "2026-10-22T08:00:00", p=Presentacion(idioma="es"))
    assert "NO ESTÉRIL" not in pie
