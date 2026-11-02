"""Servicio puro del dashboard de Reportes (etapa C): estado del día, indicadores,
duración media, serie, periodo anterior y agrupaciones. Sin base de datos."""
import json
from datetime import date

import pytest

from autoclave.services.domain.reportes import dashboard as d
from autoclave.services.domain.reportes import resumen_periodo

HOY = date(2026, 11, 2)
DIA = date(2026, 11, 1)

NO_CONFORME = json.dumps({"avisos": [{"clave": "ticket_ciclo.no_conforme_referencia"}]})


def c(id_, resultado="COMPLETADO", avisos=None, inicio="2026-11-01T08:00:00",
      fin="2026-11-01T09:00:00", **kw):
    return {"id": id_, "resultado": resultado, "avisos_ticket": avisos,
            "fecha_inicio": inicio, "fecha_fin": fin, **kw}


def estado(intentos, n=1, p1=True, activo=None, dia=DIA, hoy=HOY):
    return d.estado_dia(intentos, n, p1, activo, hoy, dia)


# ------------------------------------------------------------------ estado_dia

def test_futuro_tiene_prioridad_sobre_todo():
    assert estado([c(1)], dia=date(2026, 11, 3)) == "futuro"
    assert estado([], n=0, activo=5, dia=date(2026, 11, 3)) == "futuro"


def test_hoy_no_es_futuro():
    assert estado([c(1)], dia=HOY) == "exito"


def test_en_curso_si_el_unico_intento_es_el_activo():
    assert estado([c(9, resultado=None)], n=0, activo=9, dia=HOY) == "en_curso"


def test_en_curso_antes_que_sin_operacion():
    # n_dia = 0 (el activo no cuenta) pero el activo es el único intento
    assert estado([c(9, resultado=None)], n=0, activo=9) == "en_curso"


def test_activo_con_otros_intentos_se_excluye_de_los_fallidos():
    ints = [c(1, "FALLO_ESTERILIZACION"), c(9, resultado=None)]
    assert estado(ints, activo=9) == "sin_exito"
    ints = [c(1), c(9, resultado=None)]
    assert estado(ints, activo=9) == "exito"


def test_activo_distinto_no_hace_en_curso():
    assert estado([c(1, resultado=None)], activo=9) == "sin_exito"


def test_sin_operacion_dia_sin_ciclos():
    assert estado([], n=0) == "sin_operacion"
    assert estado([], n=0, p1=False) == "sin_operacion"


def test_exito_simple():
    assert estado([c(1)]) == "exito"


def test_exito_fallo_previo():
    assert estado([c(1, "FALLO_PREVACIO"), c(2)]) == "exito_fallo_previo"
    assert estado([c(1, "CANCELADO"), c(2)]) == "exito_fallo_previo"
    assert estado([c(1, None), c(2)]) == "exito_fallo_previo"


def test_fallo_posterior_a_todos_los_exitos_no_cambia_estado_DR_D12():
    assert estado([c(1), c(2, "FALLO_PREVACIO")]) == "exito"
    assert estado([c(1), c(2, "CANCELADO"), c(3, "FALLO_X")]) == "exito"


def test_fallo_entre_exitos_cuenta_como_previo_al_ultimo():
    assert estado([c(1), c(2, "FALLO_X"), c(3)]) == "exito_fallo_previo"


def test_dos_exitos_seguidos_sin_fallo_es_exito():
    assert estado([c(1), c(2)]) == "exito"


def test_sin_exito():
    assert estado([c(1, "FALLO_X")]) == "sin_exito"
    assert estado([c(1, "CANCELADO"), c(2, None)]) == "sin_exito"


def test_no_conforme_cuenta_como_sin_exito_DR_D13():
    assert estado([c(1, avisos=NO_CONFORME)]) == "sin_exito"
    assert estado([c(1, avisos=NO_CONFORME), c(2)]) == "exito_fallo_previo"
    assert estado([c(1), c(2, avisos=NO_CONFORME)]) == "exito"


def test_avisos_danados_o_observacion_no_son_no_conforme():
    obs = json.dumps({"avisos": [{"clave": "ticket_ciclo.observacion_referencia"}]})
    assert estado([c(1, avisos=obs)]) == "exito"
    assert estado([c(1, avisos="{no json")]) == "exito"


def test_falto_solo_programa_1():
    assert estado([], n=3, p1=True) == "falto"


def test_no_ejecutado_otros_programas():
    assert estado([], n=3, p1=False) == "no_ejecutado"


def test_intentos_none_equivale_a_vacio():
    assert estado(None, n=0) == "sin_operacion"


def test_sqlite_row_como_intento():
    import sqlite3
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    fila = con.execute("SELECT 1 AS id, 'COMPLETADO' AS resultado, NULL AS avisos_ticket").fetchone()
    assert estado([fila]) == "exito"


# -------------------------------------------------- numero_programa_efectivo

def test_numero_programa_propio():
    assert d.numero_programa_efectivo({"numero_programa": 3, "tipo_ciclo": "x"}, {"x": 7}) == 3


def test_numero_programa_null_usa_el_actual():
    assert d.numero_programa_efectivo({"numero_programa": None, "tipo_ciclo": "x"}, {"x": 7}) == 7


def test_numero_programa_null_sin_programa_actual():
    assert d.numero_programa_efectivo({"numero_programa": None, "tipo_ciclo": "z"}, {"x": 7}) is None
    assert d.numero_programa_efectivo({"tipo_ciclo": "z"}, {}) is None


# ------------------------------------------------------------- indicadores

def test_indicadores_coinciden_con_resumir():
    filas = [c(1), c(2), c(3, "FALLO_A"), c(4, "EMERGENCIA"), c(5, "CANCELADO"),
             c(6, None), c(7, "CALENTAMIENTO")]
    ind = d.indicadores(filas)
    assert ind == {"total": 7, "completados": 2, "fallos": 2, "cancelados": 1,
                   "sin_cierre": 2, "exito_pct": 29}
    agrupado = [{"tipo_ciclo": "t", "nombre_ciclo": "T", "resultado": f["resultado"], "cantidad": 1}
                for f in filas]
    tot = resumen_periodo.resumir(agrupado, {})["totales"]
    assert {k: ind[k] for k in tot} == tot


def test_indicadores_vacio():
    assert d.indicadores([])["exito_pct"] == 0
    assert d.indicadores([])["total"] == 0


def test_indicadores_exito_100():
    assert d.indicadores([c(1), c(2)])["exito_pct"] == 100


# ---------------------------------------------------------- duracion_media

def test_duracion_media_basica():
    filas = [c(1, inicio="2026-11-01T08:00:00", fin="2026-11-01T09:00:00"),
             c(2, inicio="2026-11-01T10:00:00", fin="2026-11-01T10:30:00")]
    assert d.duracion_media(filas) == (2700.0, 0)


def test_duracion_negativa_cero_y_mayor_24h_se_excluyen():
    filas = [c(1),
             c(2, inicio="2026-11-01T10:00:00", fin="2026-11-01T09:00:00"),
             c(3, inicio="2026-11-01T10:00:00", fin="2026-11-01T10:00:00"),
             c(4, inicio="2026-11-01T10:00:00", fin="2026-11-02T10:00:01")]
    assert d.duracion_media(filas) == (3600.0, 3)


def test_duracion_exactamente_24h_se_incluye():
    f = c(1, inicio="2026-11-01T10:00:00", fin="2026-11-02T10:00:00")
    assert d.duracion_media([f]) == (86400.0, 0)


def test_duracion_no_completados_no_cuentan_ni_se_excluyen():
    filas = [c(1, "FALLO_X"), c(2, "CANCELADO"), c(3, None, fin=None)]
    assert d.duracion_media(filas) == (None, 0)


def test_duracion_fin_ausente_o_ilegible_se_excluye():
    filas = [c(1, fin=None), c(2, fin="basura"), c(3, inicio=None)]
    assert d.duracion_media(filas) == (None, 3)


def test_duracion_sin_filas():
    assert d.duracion_media([]) == (None, 0)


# ------------------------------------------------------------------- serie

def test_serie_dia_24_horas():
    filas = [c(1, inicio="2026-11-01T08:10:00"), c(2, "FALLO_X", inicio="2026-11-01T08:50:00"),
             c(3, "CANCELADO", inicio="2026-11-01T23:59:00"),
             c(4, inicio="2026-11-02T00:00:00")]
    s = d.serie(filas, "dia", date(2026, 11, 1), date(2026, 11, 2))
    assert len(s) == 24
    assert s[8] == {"etiqueta": "08", "inicio": "2026-11-01T08:00:00",
                    "total": 2, "completados": 1, "fallos": 1}
    assert s[23]["total"] == 1 and s[23]["fallos"] == 0 and s[23]["completados"] == 0
    assert sum(p["total"] for p in s) == 3


def test_serie_semana_por_dia():
    filas = [c(1, inicio="2026-10-26T01:00:00"), c(2, "FALLO_X", inicio="2026-11-01T22:00:00")]
    s = d.serie(filas, "semana", date(2026, 10, 26), date(2026, 11, 2))
    assert [p["etiqueta"] for p in s][0] == "2026-10-26" and len(s) == 7
    assert s[0]["completados"] == 1 and s[6]["fallos"] == 1


def test_serie_mes_dias_28_y_31():
    assert len(d.serie([], "mes", date(2026, 2, 1), date(2026, 3, 1))) == 28
    assert len(d.serie([], "mes", date(2026, 10, 1), date(2026, 11, 1))) == 31


def test_serie_anio_por_mes():
    filas = [c(1, inicio="2026-01-31T23:00:00"), c(2, "FALLO_X", inicio="2026-12-01T00:00:00"),
             c(3, inicio="2025-12-31T23:00:00")]
    s = d.serie(filas, "anio", date(2026, 1, 1), date(2027, 1, 1))
    assert len(s) == 12 and s[0]["etiqueta"] == "2026-01" and s[11]["etiqueta"] == "2026-12"
    assert s[0]["total"] == 1 and s[11]["fallos"] == 1
    assert sum(p["total"] for p in s) == 2


def test_serie_sin_cierre_cuenta_en_total_pero_no_en_completados_ni_fallos():
    s = d.serie([c(1, None, inicio="2026-11-01T01:00:00")], "dia", DIA, date(2026, 11, 2))
    assert s[1]["total"] == 1 and s[1]["completados"] == 0 and s[1]["fallos"] == 0


def test_serie_ignora_fechas_ilegibles_y_periodo_invalido():
    assert sum(p["total"] for p in d.serie([c(1, inicio="x")], "mes", date(2026, 11, 1), date(2026, 12, 1))) == 0
    with pytest.raises(ValueError):
        d.serie([], "decada", DIA, HOY)


# -------------------------------------------------------- periodo_anterior

@pytest.mark.parametrize("periodo,fecha,esperado", [
    ("dia", date(2026, 11, 2), (date(2026, 11, 1), date(2026, 11, 2))),
    ("dia", date(2026, 1, 1), (date(2025, 12, 31), date(2026, 1, 1))),
    ("dia", date(2024, 3, 1), (date(2024, 2, 29), date(2024, 3, 1))),
    ("semana", date(2026, 11, 2), (date(2026, 10, 26), date(2026, 11, 2))),
    ("semana", date(2026, 11, 8), (date(2026, 10, 26), date(2026, 11, 2))),   # domingo
    ("semana", date(2026, 1, 1), (date(2025, 12, 22), date(2025, 12, 29))),   # jueves; cruza año
    ("semana", date(2025, 12, 29), (date(2025, 12, 22), date(2025, 12, 29))),
    ("mes", date(2026, 1, 15), (date(2025, 12, 1), date(2026, 1, 1))),
    ("mes", date(2026, 3, 31), (date(2026, 2, 1), date(2026, 3, 1))),         # febrero 28
    ("mes", date(2024, 3, 10), (date(2024, 2, 1), date(2024, 3, 1))),         # bisiesto 29
    ("mes", date(2026, 5, 1), (date(2026, 4, 1), date(2026, 5, 1))),          # abril 30
    ("mes", date(2026, 8, 20), (date(2026, 7, 1), date(2026, 8, 1))),         # julio 31
    ("anio", date(2026, 6, 30), (date(2025, 1, 1), date(2026, 1, 1))),
])
def test_periodo_anterior(periodo, fecha, esperado):
    assert d.periodo_anterior(periodo, fecha) == esperado


def test_periodo_anterior_semana_coincide_con_rango_de_utils():
    from autoclave.utils import periodos
    for f in (date(2026, 1, 1), date(2026, 11, 2), date(2025, 12, 31)):
        ini, fin = d.periodo_anterior("semana", f)
        assert periodos.rango("semana", ini) == (ini, fin)
        assert fin == periodos.rango("semana", f)[0]


def test_periodo_anterior_desconocido():
    with pytest.raises(ValueError):
        d.periodo_anterior("decada", HOY)


# ---------------------------------------------------------- agrupar_alarmas

def test_agrupar_alarmas_orden_nivel_luego_cantidad():
    filas = ([{"codigo": "A", "nivel": "AVISO", "titulo": "a"}] * 5
             + [{"codigo": "B", "nivel": "FALLO_CRITICO", "titulo": "b"}]
             + [{"codigo": "C", "nivel": "ALARMA", "titulo": "c"}] * 2
             + [{"codigo": "D", "nivel": "ALARMA", "titulo": "d"}] * 3)
    r = d.agrupar_alarmas(filas)
    assert [(g["codigo"], g["cantidad"]) for g in r] == [("B", 1), ("D", 3), ("C", 2), ("A", 5)]
    assert r[0]["nivel"] == "FALLO_CRITICO"


def test_agrupar_alarmas_codigo_visible_y_titulo_guardado():
    r = d.agrupar_alarmas([{"codigo": "TARJETA_SIN_COM", "nivel": "ALARMA", "titulo": "t"}])
    assert r[0]["codigo"] == "TARJETA_SIN_COM" and r[0]["codigo_visible"] == "MODULO_ES_SIN_COM"
    assert r[0]["titulo"] == "t"


def test_agrupar_alarmas_nivel_mas_grave_por_codigo():
    r = d.agrupar_alarmas([{"codigo": "X", "nivel": "AVISO", "titulo": ""},
                           {"codigo": "X", "nivel": "ALARMA", "titulo": ""}])
    assert len(r) == 1 and r[0]["nivel"] == "ALARMA" and r[0]["cantidad"] == 2


def test_agrupar_alarmas_nivel_desconocido_va_al_final():
    r = d.agrupar_alarmas([{"codigo": "Z", "nivel": "RARO", "titulo": ""},
                           {"codigo": "Y", "nivel": "INFORMATIVO", "titulo": ""}])
    assert [g["codigo"] for g in r] == ["Y", "Z"] and r[1]["nivel"] == "RARO"


def test_agrupar_alarmas_vacio():
    assert d.agrupar_alarmas([]) == []


# ------------------------------------------------------- agrupar_operadores

def test_operadores_vacio_es_sin_operador():
    r = d.agrupar_operadores([{"operador": None}, {"operador": ""}, {"operador": "  "},
                              {"operador": "Ana"}])
    assert r["operadores"][0] == {"operador": "Sin operador", "sin_operador": True, "cantidad": 3}
    assert r["operadores"][1]["operador"] == "Ana" and r["otros"] is None


def test_operadores_maximo_5_y_otros():
    filas = []
    for i, n in enumerate([7, 6, 5, 4, 3, 2, 1]):
        filas += [{"operador": f"op{i}"}] * n
    r = d.agrupar_operadores(filas)
    assert [o["operador"] for o in r["operadores"]] == ["op0", "op1", "op2", "op3", "op4"]
    assert r["otros"] == {"operadores": 2, "ciclos": 3}


def test_operadores_exactamente_5_sin_otros():
    r = d.agrupar_operadores([{"operador": f"o{i}"} for i in range(5)])
    assert len(r["operadores"]) == 5 and r["otros"] is None


def test_operadores_desempate_por_nombre_y_sin_filas():
    r = d.agrupar_operadores([{"operador": "b"}, {"operador": "a"}])
    assert [o["operador"] for o in r["operadores"]] == ["a", "b"]
    assert d.agrupar_operadores([]) == {"operadores": [], "otros": None}
