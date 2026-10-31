"""M1 (tanda 3): cálculo del próximo mantenimiento (lógica pura)."""

from datetime import date, datetime

import pytest

from autoclave.core.runtime import mantenimiento as m

INST = datetime(2026, 10, 26, 9, 0)
HOY = date(2026, 10, 27)


def test_primer_mantenimiento_es_instalacion_mas_intervalo():
    e = m.calcular(INST, 180, 0, None, 0, HOY)
    assert e.estado == m.OK
    assert e.proximo_fecha == date(2027, 4, 24)
    assert e.dias_restantes == 179 and e.ciclos_restantes is None


def test_vencido_por_fecha():
    e = m.calcular(INST, 180, 0, None, 5, date(2027, 4, 25))
    assert e.vencido and e.vencido_por == "fecha"
    assert e.dias_restantes == -1


def test_el_dia_del_vencimiento_aun_no_esta_vencido():
    e = m.calcular(INST, 180, 0, None, 0, date(2027, 4, 24))
    assert e.estado == m.PROXIMO and not e.vencido


def test_proximo_dentro_de_14_dias():
    e = m.calcular(INST, 180, 0, None, 0, date(2027, 4, 10))
    assert e.estado == m.PROXIMO


def test_tras_registrar_un_mantenimiento_la_base_es_esa_fecha():
    ultimo = {"fecha": "2027-04-30", "ciclos": 120, "tipo": "preventivo"}
    e = m.calcular(INST, 180, 0, ultimo, 130, date(2027, 5, 1))
    assert e.proximo_fecha == date(2027, 10, 27)
    assert e.ultimo_fecha == date(2027, 4, 30) and e.ultimo_tipo == "preventivo"
    assert e.estado == m.OK


def test_por_ciclos_vence_lo_que_ocurra_primero():
    ultimo = {"fecha": "2026-10-26", "ciclos": 100, "tipo": "preventivo"}
    e = m.calcular(INST, 180, 500, ultimo, 450, HOY)
    assert e.ciclos_restantes == 150 and e.estado == m.OK
    e = m.calcular(INST, 180, 500, ultimo, 600, HOY)
    assert e.vencido and e.vencido_por == "ciclos" and e.ciclos_restantes == 0
    # la fecha vence antes que los ciclos
    e = m.calcular(INST, 30, 500, ultimo, 110, date(2026, 12, 1))
    assert e.vencido and e.vencido_por == "fecha"


def test_ciclos_sin_contador_no_inventa_valor():
    e = m.calcular(INST, 180, 500, None, None, HOY)
    assert e.ciclos_restantes is None and e.estado == m.OK


def test_reloj_anterior_a_la_instalacion_no_muestra_valor_falso():
    e = m.calcular(INST, 180, 0, None, 0, date(2026, 10, 1))
    assert e.estado == m.SIN_DATO and e.proximo_fecha is None and e.dias_restantes is None


def test_reloj_anterior_al_ultimo_mantenimiento_es_sin_dato():
    ultimo = {"fecha": "2027-04-30", "ciclos": 0, "tipo": "x"}
    e = m.calcular(INST, 180, 0, ultimo, 0, date(2027, 3, 1))
    assert e.estado == m.SIN_DATO


def test_sin_fecha_de_instalacion_es_sin_dato():
    assert m.calcular(None, 180, 0, None, 0, HOY).estado == m.SIN_DATO


def test_intervalos_en_cero_no_aplica():
    assert m.calcular(INST, 0, 0, None, 0, HOY).estado == m.NO_APLICA


@pytest.mark.parametrize("dias, ciclos, ok", [(180, 0, True), (0, 0, True), (3650, 1000000, True),
                                              (-1, 0, False), (3651, 0, False), (180, -5, False),
                                              (1.5, 0, False), ("180", 0, False), (True, 0, False)])
def test_validacion_de_intervalos(dias, ciclos, ok):
    assert (m.validar_intervalos(dias, ciclos) == []) is ok


def test_a_dict_serializable():
    d = m.calcular(INST, 180, 0, None, 0, HOY).a_dict()
    assert d["proximo_fecha"] == "2027-04-24" and d["vencido"] is False
