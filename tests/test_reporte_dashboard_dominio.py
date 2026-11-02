# tests/test_reporte_dashboard_dominio.py
#
# ui_qml/domain/reporte_dashboard.py: textos, indicadores, dona, serie, programas,
# calendario, alarmas, operadores y mantenimiento del dashboard de Reportes.
# `t` se inyecta con las claves de docs/informes/dashboard_reportes/claves_i18n_reportes.json
# (aún no están en i18n/es.json); los días y meses salen del catálogo real.

import json
import re
from datetime import date
from pathlib import Path

import pytest

from autoclave.ui_qml.domain import reporte_dashboard as d

RAIZ = Path(__file__).resolve().parents[1]
CLAVES = json.loads((RAIZ / "docs/informes/dashboard_reportes/claves_i18n_reportes.json").read_text(encoding="utf-8"))
FUENTE = (RAIZ / "src/autoclave/ui_qml/domain/reporte_dashboard.py").read_text(encoding="utf-8")


def _t(clave, idioma=None, **params):
    texto = CLAVES.get(idioma or "es", CLAVES["es"]).get(clave)
    if texto is None:
        return clave
    for k, v in params.items():
        texto = texto.replace("{" + k + "}", str(v))
    return texto


def _ind(total=0, comp=0, fallos=0, canc=0, sc=0, dur=None, excl=0):
    return {"total": total, "completados": comp, "fallos": fallos, "cancelados": canc, "sin_cierre": sc,
            "exito_pct": round(100 * comp / total) if total else 0, "duracion_media_s": dur,
            "duraciones_excluidas": excl}


def _dash(periodo="mes", desde="2026-10-01", hasta="2026-10-31", ind=None, ant="x", **extra):
    base = {"periodo": periodo, "desde": desde, "hasta": hasta,
            "anterior": {"desde": "2026-09-01", "hasta": "2026-09-30"},
            "indicadores": ind or _ind(10, 8, 1, 1, 0, 2700.0),
            "indicadores_anterior": _ind(8, 5, 2, 1, 0, 3000.0) if ant == "x" else ant,
            "serie": [], "por_programa": [], "causas_fallo": [], "alarmas": [], "operadores": [],
            "operadores_otros": None}
    base.update(extra)
    return base


# ── periodo ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("periodo,desde,hasta,idioma,esperado", [
    ("mes", "2026-10-01", "2026-10-31", "es", "Octubre 2026"),
    ("semana", "2026-10-26", "2026-11-01", "es", "Semana del 26/10 al 01/11"),
    ("dia", "2026-11-02", "2026-11-02", "es", "Lunes 2 de noviembre"),
    ("anio", "2026-01-01", "2026-12-31", "es", "2026"),
    ("semana", "2026-10-26", "2026-11-01", "en", "Week of 10/26 to 11/01"),
    ("anio", "2026-01-01", "2026-12-31", "en", "2026"),
])
def test_titulo_periodo(periodo, desde, hasta, idioma, esperado):
    e = d.encabezado(_dash(periodo, desde, hasta), idioma, _t)
    assert e["titulo"] == esperado
    assert e["comparado"].startswith("Compared with" if idioma == "en" else "Comparado con")


def test_titulo_en_dia_y_mes():
    e = d.encabezado(_dash("dia", "2026-11-02", "2026-11-02"), "en", _t)
    assert e["titulo"] == "Monday, November 2"
    assert d.encabezado(_dash(), "en", _t)["titulo"] == "October 2026"


def test_comparado_nombra_el_periodo_anterior():
    assert d.encabezado(_dash(), "es", _t)["comparado"] == "Comparado con Septiembre 2026"


def test_encabezado_mal_formado():
    assert d.encabezado(None, "es", _t)["titulo"] == ""
    assert d.encabezado({"periodo": "decada"}, "es", _t)["titulo"] == ""


# ── indicadores ──────────────────────────────────────────────────────────

def _por_clave(inds):
    return {i["clave"]: i for i in inds}


def test_indicadores_con_comparacion():
    i = _por_clave(d.indicadores(_dash(), "es", _t))
    assert [i[k]["valor"] for k in ("ciclos", "exito", "fallos", "duracion")] == ["10", "80%", "1", "45 min"]
    assert i["ciclos"]["comparacion"]["texto"] == "+2" and i["ciclos"]["comparacion"]["color"] == d.C_NEUTRO
    assert i["exito"]["comparacion"]["texto"] == "+18 pp"           # 80 - 62.5->62 (round)
    assert i["exito"]["comparacion"]["flecha"] == "arriba" and i["exito"]["comparacion"]["color"] == d.C_BUENO
    assert i["fallos"]["comparacion"]["texto"] == "−1"
    assert i["fallos"]["comparacion"]["flecha"] == "abajo" and i["fallos"]["comparacion"]["color"] == d.C_BUENO
    assert i["duracion"]["comparacion"]["texto"] == "−5 min" and i["duracion"]["comparacion"]["color"] == d.C_NEUTRO
    assert i["fallos"]["pie"] == "1 cancelados · 0 sin cierre"
    assert not i["ciclos"]["comparacion"]["sin_datos"]


def test_indicadores_color_rojo_si_empeora():
    r = _dash(ind=_ind(10, 3, 6, 1, 0, 100.0), indicadores_anterior=_ind(10, 8, 1, 1, 0, 100.0))
    i = _por_clave(d.indicadores(r, "es", _t))
    assert i["exito"]["comparacion"]["color"] == d.C_MALO and i["exito"]["comparacion"]["flecha"] == "abajo"
    assert i["fallos"]["comparacion"]["color"] == d.C_MALO and i["fallos"]["comparacion"]["flecha"] == "arriba"


def test_indicadores_sin_periodo_anterior():
    i = _por_clave(d.indicadores(_dash(ant=None), "es", _t))
    for k in i.values():
        assert k["comparacion"]["sin_datos"] is True
        assert k["comparacion"]["texto_sin_datos"] == "Sin datos del periodo anterior"
        assert k["comparacion"]["disponible"] is False


def test_indicadores_igual_y_duracion_ausente():
    r = _dash(ind=_ind(8, 5, 2, 1, 0, None, excl=2))
    i = _por_clave(d.indicadores(r, "es", _t))
    assert i["ciclos"]["comparacion"]["flecha"] == "igual" and i["ciclos"]["comparacion"]["texto"] == "0"
    assert i["duracion"]["valor"] == "—" and i["duracion"]["comparacion"]["disponible"] is False
    assert "2 ciclos excluidos" in i["duracion"]["pie"]


def test_indicadores_basura_no_tumba():
    assert len(d.indicadores(None, "es", _t)) == 4
    assert d.indicadores({"indicadores": "x"}, "es", _t)[0]["valor"] == "0"


def test_minigraficas_normalizadas():
    serie = [{"etiqueta": f"2026-10-0{i}", "inicio": f"2026-10-0{i}T00:00:00", "total": t, "completados": c, "fallos": f}
             for i, (t, c, f) in enumerate([(2, 2, 0), (4, 3, 1), (0, 0, 0)], 1)]
    i = _por_clave(d.indicadores(_dash(serie=serie), "es", _t))
    assert [p["y"] for p in i["ciclos"]["mini"]] == [0.5, 1.0, 0.0]
    assert [p["x"] for p in i["ciclos"]["mini"]] == [0.0, 0.5, 1.0]
    assert [p["y"] for p in i["fallos"]["mini"]] == [0.0, 1.0, 1.0]       # acumulado
    assert i["duracion"]["mini"] == []


# ── dona ─────────────────────────────────────────────────────────────────

def test_dona():
    r = d.dona(_dash(ind=_ind(10, 8, 1, 1, 0)), "es", _t)
    assert not r["vacia"] and r["centro"] == "80%"
    assert [(p["clave"], p["porcentaje"]) for p in r["porciones"]] == [
        ("completados", "80%"), ("fallos", "10%"), ("cancelados", "10%"), ("sin_cierre", "0%")]
    assert r["porciones"][1]["inicio"] == pytest.approx(0.8)
    assert r["porciones"][0]["color"] == "menuVerde" and r["porciones"][1]["color"] == "peligroTexto"


def test_dona_sin_ciclos():
    r = d.dona(_dash(ind=_ind()), "es", _t)
    assert r["vacia"] and r["texto_vacio"] == "Sin ciclos en el periodo" and r["color_vacio"] == "bordeCampo"
    assert r["centro"] == ""


# ── serie ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("maximo,tope,paso", [(0, 4, 1), (1, 1, 1), (3, 3, 1), (4, 4, 1), (5, 6, 2), (9, 10, 5),
                                              (11, 15, 5), (23, 30, 10), (101, 150, 50)])
def test_eje_y_entero(maximo, tope, paso):
    e = d._eje_y(maximo)
    assert (e["max"], e["paso"]) == (tope, paso)
    assert e["max"] >= maximo and e["max"] % e["paso"] == 0 and len(e["marcas"]) <= 5
    assert e["marcas"][-1]["y"] == 1.0 and all(isinstance(m["valor"], int) for m in e["marcas"])


def test_serie_mes():
    filas = [{"etiqueta": f"2026-10-{n:02d}", "inicio": f"2026-10-{n:02d}T00:00:00",
              "total": 0 if n % 2 else 4, "completados": 3 if n == 2 else 0, "fallos": 1 if n == 2 else 0}
             for n in range(1, 32)]
    s = d.serie(_dash(serie=filas), "es", _t)
    assert len(s["puntos"]) == 31 and not s["vacia"]
    assert s["puntos"][0]["x"] == 0.0 and s["puntos"][-1]["x"] == 1.0
    assert s["puntos"][1]["y_total"] == 1.0 and s["puntos"][1]["y_completados"] == 0.75
    assert [p["con_fallo"] for p in s["puntos"]][:3] == [False, True, False]
    assert s["puntos"][1]["rotulo"] == "Vie 2 oct"
    assert [m["texto"] for m in s["eje_x"]][:3] == ["1", "5", "10"]
    assert all(0.0 <= p["y_total"] <= 1.0 for p in s["puntos"])


def test_serie_dia_y_anio():
    horas = [{"etiqueta": f"{h:02d}", "inicio": f"2026-11-02T{h:02d}:00:00", "total": 1 if h == 9 else 0,
              "completados": 0, "fallos": 0} for h in range(24)]
    s = d.serie(_dash("dia", "2026-11-02", "2026-11-02", serie=horas), "es", _t)
    assert s["puntos"][9]["rotulo"] == "09:00" and [m["texto"] for m in s["eje_x"]] == ["00:00", "06:00", "12:00", "18:00"]
    meses = [{"etiqueta": f"2026-{m:02d}", "inicio": f"2026-{m:02d}-01T00:00:00", "total": m, "completados": m,
              "fallos": 0} for m in range(1, 13)]
    s = d.serie(_dash("anio", "2026-01-01", "2026-12-31", serie=meses), "es", _t)
    assert len(s["puntos"]) == 12 and s["puntos"][9]["rotulo"] == "Octubre 2026"
    assert s["eje_y"]["max"] == 15 and [m["texto"] for m in s["eje_x"]][0] == "Ene"


def test_serie_vacia_o_un_punto():
    assert d.serie(None, "es", _t)["puntos"] == [] and d.serie(None, "es", _t)["vacia"]
    s = d.serie(_dash(serie=[{"etiqueta": "2026-10-01", "inicio": "2026-10-01T00:00:00", "total": 2,
                              "completados": 2, "fallos": 0}]), "es", _t)
    assert s["puntos"][0]["x"] == 0.5


# ── programas ────────────────────────────────────────────────────────────

def test_programas():
    pp = [{"programa_id": "a", "programa_nombre": "Instrumental", "programa_numero": 2, "total": 20, "completados": 19,
           "fallos": 1, "cancelados": 0, "sin_cierre": 0},
          {"programa_id": "b", "programa_nombre": "Bowie & Dick", "programa_numero": 1, "total": 30, "completados": 30,
           "fallos": 0, "cancelados": 0, "sin_cierre": 0},
          {"programa_id": "c", "programa_nombre": "Líquidos", "programa_numero": 5, "total": 4, "completados": 3,
           "fallos": 0, "cancelados": 1, "sin_cierre": 0}]
    r = d.programas(_dash(por_programa=pp), "es", _t)
    assert [p["numero"] for p in r] == ["01", "02", "05"]                  # cantidad descendente
    assert [p["color"] for p in r] == ["menuVerde", "menuVerde", "menuNaranja"]   # 100 %, 95 %, 75 %
    assert r[0]["detalle"] == "Sin incidencias" and r[1]["detalle"] == "1 con fallo"
    assert r[2]["exito_pct"] == 75 and r[2]["ancho"] == 0.75 and r[2]["detalle"] == "1 cancelados"


# ── calendario ───────────────────────────────────────────────────────────

def _cal(estados: dict, anio=2026, mes=10, periodo="mes", programas=None, programa=1):
    import calendar as c
    n = c.monthrange(anio, mes)[1]
    dias = [{"fecha": f"{anio}-{mes:02d}-{x:02d}", "estado": estados.get(x, "sin_operacion"),
             "intentos": 1 if estados.get(x) in ("exito", "sin_exito") else 0, "exitos": 1 if estados.get(x) == "exito" else 0}
            for x in range(1, n + 1)]
    return {"periodo": periodo, "programas": programas if programas is not None else
            [{"numero": 1, "programa_id": "bd", "nombre": "Bowie & Dick"}, {"numero": 3, "programa_id": "x", "nombre": "Textiles"}],
            "programa": programa, "dias": dias}


def test_calendario_mes():
    estados = {1: "exito", 2: "exito_fallo_previo", 3: "sin_exito", 4: "falto", 5: "no_ejecutado", 6: "en_curso"}
    c = d.calendario(_dash(), _cal(estados), "es", _t)
    assert c["vista"] == "mes" and c["titulo"] == "Octubre 2026" and c["programa"] == 1
    assert [p["etiqueta"] for p in c["programas"]] == ["01 · Bowie & Dick", "03 · Textiles"]
    assert c["programa_etiqueta"] == "01 · Bowie & Dick"
    # 1 de octubre de 2026 es jueves: tres celdas vacías antes
    primera = c["semanas"][0]
    assert [x["vacia"] for x in primera][:4] == [True, True, True, False] and all(len(s) == 7 for s in c["semanas"])
    celdas = {x["dia"]: x for s in c["semanas"] for x in s if not x["vacia"]}
    assert len(celdas) == 31
    assert celdas[1]["forma"] == "relleno" and celdas[1]["estado_rotulo"] == "Con éxito (ciclo completado)"
    assert celdas[2]["forma"] == "relleno_punto" and celdas[2]["punto"] == "peligroTexto"
    assert celdas[3]["forma"] == "solido" and celdas[4]["forma"] == "borde_grueso" and celdas[4]["grosor"] == 3
    assert celdas[5]["forma"] == "gris" and celdas[6]["forma"] == "azul"
    assert celdas[7]["punteado"] is True and celdas[7]["estado"] == "sin_operacion"
    cuenta = {x["estado"]: x["cantidad"] for x in c["conteo"]}
    assert cuenta == {"exito": 1, "exito_fallo_previo": 1, "sin_exito": 1, "falto": 1, "no_ejecutado": 1,
                      "sin_operacion": 25, "en_curso": 1}
    assert [x["rotulo"] for x in c["conteo"]][:5] == ["Con éxito (ciclo completado)", "Con éxito tras un fallo previo",
                                                      "Sin éxito", "Faltó", "No ejecutado"]
    assert c["leyenda"] == "Muestra el resultado del ciclo. La lectura de la hoja de prueba no se registra en el equipo."
    assert c["dias_semana"][0] == "Lun"


def test_calendario_futuro_no_tocable_y_estado_desconocido_es_neutro():
    cal = _cal({1: "futuro", 2: "inventado"})
    c = d.calendario(_dash(), cal, "es", _t)
    celdas = {x["dia"]: x for s in c["semanas"] for x in s if not x["vacia"]}
    assert celdas[1]["tocable"] is False and celdas[2]["estado"] == "sin_operacion"


def test_calendario_semana_resalta_y_cuenta_solo_el_periodo():
    cal = _cal({27: "exito", 28: "sin_exito", 5: "exito"}, periodo="semana")
    c = d.calendario(_dash("semana", "2026-10-26", "2026-11-01"), cal, "es", _t)
    celdas = {x["dia"]: x for s in c["semanas"] for x in s if not x["vacia"]}
    assert celdas[27]["en_periodo"] and not celdas[5]["en_periodo"]
    cuenta = {x["estado"]: x["cantidad"] for x in c["conteo"]}
    assert cuenta["exito"] == 1 and cuenta["sin_exito"] == 1       # el éxito del día 5 no cuenta


def test_calendario_sin_programas_ni_dias():
    c = d.calendario(_dash(), {"periodo": "mes", "programas": [], "programa": None, "dias": []}, "es", _t)
    assert c["sin_programas"] and c["texto_sin_programas"] == "No hay programas con ciclos en el periodo"
    assert c["semanas"] == [] and c["programa"] is None
    assert d.calendario(None, None, "es", _t)["semanas"] == []


def _cal_anio():
    dias = []
    import calendar as c
    for m in range(1, 13):
        for x in range(1, c.monthrange(2026, m)[1] + 1):
            e = "futuro" if m >= 12 else "sin_operacion"
            if m == 10:
                e = {3: "exito_fallo_previo", 4: "exito_fallo_previo", 5: "falto", 6: "sin_exito"}.get(x, "exito")
            if m == 11:
                e = "exito" if x <= 2 else "futuro"
            if m == 9:
                e = "exito"
            dias.append({"fecha": f"2026-{m:02d}-{x:02d}", "estado": e, "intentos": 0, "exitos": 0})
    return {"periodo": "anio", "programas": [{"numero": 1, "programa_id": "bd", "nombre": "B&D"}], "programa": 1, "dias": dias}


def test_calendario_anio_12_miniaturas():
    c = d.calendario(_dash("anio", "2026-01-01", "2026-12-31"), _cal_anio(), "es", _t)
    assert c["vista"] == "anio" and c["titulo"] == "2026" and len(c["meses"]) == 12 and c["semanas"] == []
    m = {x["mes"]: x for x in c["meses"]}
    assert m[1]["habilitado"] is False and m[1]["resumen"] == "Sin datos"          # solo sin operación
    assert m[12]["habilitado"] is False                                            # solo futuro
    assert m[9]["habilitado"] and m[9]["resumen"] == "Sin novedad"
    assert m[10]["resumen"] == "2 con fallo previo · 2 sin éxito o faltó"
    assert m[11]["habilitado"] and m[11]["resumen"] == "Sin novedad"
    assert m[10]["nombre"] == "Octubre" and len(m[10]["semanas"]) in (5, 6)
    assert c["meses"][0]["nombre_corto"] == "ene"
    assert sum(x["cantidad"] for x in c["conteo"]) == sum(1 for _ in _cal_anio()["dias"] if _["estado"] != "futuro")


def test_panel_dia():
    r = {"fecha": "2026-10-05", "estado": "falto", "ciclos": []}
    p = d.panel_dia(r, "es", _t, n_otros=3)
    assert p["titulo"] == "Lunes 5 de octubre" and p["estado_rotulo"] == "Faltó"
    assert p["explicacion"] == "No se ejecutó Bowie & Dick. El equipo realizó 3 ciclos de otros programas ese día."
    assert "ciclos de otros" in d.panel_dia(r, "es", _t)["explicacion"] and "{n}" not in d.panel_dia(r, "es", _t)["explicacion"]
    assert d.panel_dia(None, "es", _t)["estado"] == "sin_operacion"


# ── alarmas ──────────────────────────────────────────────────────────────

def test_alarmas_orden_recorte_y_niveles():
    filas = [{"codigo": f"X{i}", "codigo_visible": f"X{i}", "nivel": "AVISO", "titulo": f"aviso {i}", "cantidad": i}
             for i in range(1, 8)]
    filas += [{"codigo": "TARJETA_ABC", "codigo_visible": "MODULO_ES_ABC", "nivel": "FALLO_CRITICO", "titulo": "t", "cantidad": 1},
              {"codigo": "Y", "codigo_visible": "Y", "nivel": "ALARMA", "titulo": "alarma", "cantidad": 2},
              {"codigo": "Z", "codigo_visible": "Z", "nivel": "RARO", "titulo": "raro", "cantidad": 9}]
    a = d.alarmas(_dash(alarmas=filas), "es", _t)
    assert a["total"] == sum(f["cantidad"] for f in filas) and len(a["filas"]) == 8 and len(a["todas"]) == 10
    assert a["hay_mas"] and a["texto_ver_todas"] == "Ver todas"
    # nivel descendente (desconocido = fallo crítico), luego cantidad descendente
    assert [f["nivel"] for f in a["todas"]][:3] == ["FALLO_CRITICO", "FALLO_CRITICO", "ALARMA"]
    assert a["todas"][0]["cantidad"] == 9 and a["todas"][1]["codigo_visible"] == "MODULO_ES_ABC"
    assert a["todas"][0]["color"] == "alarmaAlta" and a["todas"][2]["color"] == "alarmaMedia"
    assert a["todas"][3]["nivel_rotulo"] == "Aviso" and a["todas"][3]["titulo"].startswith("aviso")
    assert [n["nivel"] for n in a["niveles"]] == ["FALLO_CRITICO", "ALARMA", "AVISO", "INFORMATIVO"]
    assert sum(n["fraccion"] for n in a["niveles"]) == pytest.approx(1.0)


def test_alarmas_vacia_y_titulo_del_catalogo():
    assert d.alarmas(_dash(), "es", _t)["vacia"] and d.alarmas(None, "es", _t)["filas"] == []
    from autoclave.state_machine.alarms.catalogo import CATALOGO
    codigo = next(iter(CATALOGO))
    a = d.alarmas(_dash(alarmas=[{"codigo": codigo, "nivel": "AVISO", "titulo": "GUARDADO", "cantidad": 1}]), "es", _t)
    assert a["filas"][0]["titulo"] and a["filas"][0]["codigo_visible"]


# ── operadores ───────────────────────────────────────────────────────────

def test_operadores():
    ops = [{"operador": "Ana Pérez", "sin_operador": False, "cantidad": 10},
           {"operador": "", "sin_operador": True, "cantidad": 5},
           {"operador": "luis", "sin_operador": False, "cantidad": 2}]
    r = d.operadores(_dash(operadores=ops, operadores_otros={"operadores": 3, "ciclos": 4}), "es", _t)
    assert [(f["nombre"], f["iniciales"], f["fraccion"]) for f in r["filas"]] == [
        ("Ana Pérez", "AP", 1.0), ("Sin operador", "?", 0.5), ("luis", "LU", 0.2)]
    assert r["otros"] == {"texto": "Otros (3)", "cantidad": 4} and not r["vacia"]
    assert d.operadores(None, "es", _t)["vacia"]


# ── mantenimiento ────────────────────────────────────────────────────────

def _mant(estado="ok", restantes=580, ultimo="2026-06-01", tipo="preventivo"):
    return {"estado": estado, "ciclos_restantes": restantes, "ultimo_fecha": ultimo, "ultimo_tipo": tipo,
            "configuracion": {"intervalo_dias": 365, "intervalo_ciclos": 1000}, "ciclos_actuales": 420}


_REG = [{"fecha": "2026-10-20", "usuario": "tecnico1", "tipo": "correctivo", "observaciones": "Cambio de repuesto de empaque"},
        {"fecha": "2026-10-02", "usuario": "tecnico1", "tipo": "correctivo", "observaciones": "ajuste"},
        {"fecha": "2026-06-01", "usuario": "tecnico2", "tipo": "preventivo", "observaciones": ""},
        {"fecha": "2026-09-15", "usuario": "tecnico1", "tipo": "correctivo", "observaciones": "repuesto fuera del periodo"}]


def test_mantenimiento():
    m = d.mantenimiento(_mant(), _REG, date(2026, 10, 1), date(2026, 10, 31), "es", _t)
    assert m["disponible"] and m["desde_ultimo"] == 420 and m["fraccion"] == pytest.approx(0.42)
    assert m["anillo_texto"] == "420 / 1000" and m["proximo"] == "Próximo en 580 ciclos" and m["color"] == "menuVerde"
    assert m["ultimo_texto"] == "Último preventivo: 01/06/2026 · tecnico2"
    assert m["correctivos"] == 2 and m["repuestos"] == 1 and m["registros_disponibles"]


def test_mantenimiento_vencido_proximo_y_sin_preventivo():
    m = d.mantenimiento(_mant("vencido", -20), _REG, None, None, "es", _t)
    assert m["proximo"] == "Vencido por 20 ciclos" and m["color"] == "peligroTexto" and m["fraccion"] == 1.0
    assert d.mantenimiento(_mant("proximo", 30), [], None, None, "es", _t)["color"] == "menuNaranja"
    sp = d.mantenimiento(_mant(ultimo=None, tipo=""), [], date(2026, 10, 1), date(2026, 10, 31), "es", _t)
    assert sp["ultimo_preventivo"] is None and sp["ultimo_texto"] == "Sin preventivo registrado"


def test_mantenimiento_sin_registros_o_sin_dato():
    m = d.mantenimiento(_mant(), None, date(2026, 10, 1), date(2026, 10, 31), "es", _t)
    assert not m["registros_disponibles"] and m["correctivos"] is None and m["correctivos_texto"] == "—"
    assert m["ultimo_texto"].endswith("· —")
    s = d.mantenimiento({"estado": "sin_dato"}, None, None, None, "es", _t)
    assert not s["disponible"] and s["proximo"] == "—" and s["anillo_texto"] == "—"
    assert d.mantenimiento(None, None, None, None, "es", _t)["disponible"] is False


# ── entrada principal y reglas transversales ─────────────────────────────

def test_presentable_completo_y_vacio():
    p = d.presentable(_dash(), _cal({1: "exito"}), "es", _t)
    assert set(p) == {"valido", "encabezado", "indicadores", "dona", "serie", "programas", "calendario", "causas",
                      "alarmas", "operadores"} and p["valido"]
    v = d.presentable(None, None, "es", _t)
    assert v["valido"] is False and v["dona"]["vacia"] and v["calendario"]["semanas"] == []


def _cadenas(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _cadenas(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _cadenas(v)


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_sin_hexadecimales_y_sin_palabras_prohibidas(idioma):
    """Colores solo por clave de tema; DR-H01: nunca «conforme» ni «apto»."""
    estados = {1: "exito", 2: "exito_fallo_previo", 3: "sin_exito", 4: "falto"}
    p = d.presentable(_dash(alarmas=[{"codigo": "Y", "nivel": "ALARMA", "titulo": "a", "cantidad": 1}],
                            operadores=[{"operador": "", "sin_operador": True, "cantidad": 1}]),
                      _cal(estados), idioma, _t)
    p["panel"] = d.panel_dia({"fecha": "2026-10-04", "estado": "falto"}, idioma, _t, 2)
    p["mant"] = d.mantenimiento(_mant(), _REG, date(2026, 10, 1), date(2026, 10, 31), idioma, _t)
    for s in _cadenas(p):
        assert not s.startswith("#"), s
        assert not re.search(r"conform|\bapto|\bapta|compliant|\bfit for", s, re.I), s


def test_textos_i18n_sin_palabras_prohibidas_y_con_paridad():
    assert set(CLAVES["es"]) == set(CLAVES["en"])
    for idioma in ("es", "en"):
        for clave, texto in CLAVES[idioma].items():
            assert clave.startswith("reportes.")
            assert not re.search(r"conform|\bapto|\bapta|compliant", texto, re.I), (clave, texto)
            # mismos marcadores {…} en los dos idiomas
            assert sorted(re.findall(r"\{\w+\}", texto)) == sorted(re.findall(r"\{\w+\}", CLAVES["es"][clave])), clave


def test_toda_clave_usada_esta_en_el_json():
    usadas = set(re.findall(r'"(reportes\.[a-z_0-9]+)"', FUENTE))
    puente = (RAIZ / "src/autoclave/ui_qml/bridge/reporte_dashboard.py").read_text(encoding="utf-8")
    usadas |= set(re.findall(r'"(reportes\.[a-z_0-9]+)"', puente))
    usadas |= {f"reportes.dona_{c}" for c in d.SERIES_RESULTADO}
    usadas |= {f"reportes.estado_{e}" for e in d.ESTADOS_DIA}
    usadas |= {f"reportes.expl_{e}" for e in d.ESTADOS_DIA}
    usadas |= {f"reportes.ind_{k}" for k in ("ciclos", "exito", "fallos", "duracion")}
    faltan = sorted(k for k in usadas if k not in CLAVES["es"] or k not in CLAVES["en"])
    assert faltan == []


def test_claves_de_tema_son_nombres_validos():
    """Los colores del dominio son identificadores (nombres de propiedad de Colores)."""
    claves = {a[k] for a in d._ASPECTO_DIA.values() for k in ("relleno", "borde", "punto")} - {""}
    claves |= set(d._COLOR_RESULTADO.values()) | set(d._COLOR_NIVEL.values()) | {d.C_BUENO, d.C_MALO, d.C_NEUTRO}
    assert all(re.fullmatch(r"[a-z][A-Za-z0-9]*", c) for c in claves)
