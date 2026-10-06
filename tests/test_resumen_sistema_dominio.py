# tests/test_resumen_sistema_dominio.py
#
# Formateadores del Resumen del Sistema del Menú Principal
# (ui_qml/domain/resumen_sistema.py, Fase 2 de planeacion_menu_principal_ui_qml.md).

import pytest

from autoclave.ui_qml.domain import resumen_sistema as rs

SD = rs.SIN_DATO


def test_sin_dato_es_raya():
    assert SD == "—"


@pytest.mark.parametrize("valor, esperado", [
    (0, "0"), (5, "5"), (1234567, "1234567"),     # sin separador de miles
    (None, SD), (-1, SD), (True, SD), (3.5, SD), ("12", SD),
])
def test_formatear_entero(valor, esperado):
    assert rs.formatear_entero(valor) == esperado


@pytest.mark.parametrize("iso, fecha, hora", [
    ("2026-10-02T14:25:10.123456", "02/10/2026", "14:25"),
    ("2026-01-05T00:00:00", "05/01/2026", "00:00"),
    ("2026-12-31T23:59:59", "31/12/2026", "23:59"),
    (None, SD, SD), ("", SD, SD), ("ayer", SD, SD), (20261002, SD, SD),
])
def test_formatear_fecha_y_hora(iso, fecha, hora):
    assert rs.formatear_fecha(iso) == fecha
    assert rs.formatear_hora(iso) == hora


@pytest.mark.parametrize("numero, esperado", [
    (1, "01"), (12, "12"), (105, "105"), (None, SD), (0, SD), (True, SD), ("2", SD),
])
def test_formatear_numero_programa(numero, esperado):
    assert rs.formatear_numero_programa(numero) == esperado


# ciclos.resultado guarda la fase_ciclo con que terminó el ciclo (valores reales
# de la base: COMPLETADO, CANCELADO, FALLO_ESTERILIZACION, FALLO_CONEXION,
# EMERGENCIA, ...). Misma regla que progreso_ciclo.resultado del backend:
# COMPLETADO y CANCELADO tal cual; cualquier otro cierre es FALLO.
@pytest.mark.parametrize("valor, esperado", [
    ("COMPLETADO", "COMPLETADO"), ("CANCELADO", "CANCELADO"), ("FALLO", "FALLO"),
    ("FALLO_CALENTAMIENTO", "FALLO"), ("FALLO_SECADO", "FALLO"), ("FALLO_CONEXION", "FALLO"),
    ("FALLO_PUERTA_1_ABIERTA", "FALLO"), ("EMERGENCIA", "FALLO"), ("SENSOR_AUSENTE", "FALLO"),
    (None, ""), ("", ""), (3, ""),
    ("ESTERILIZACION", ""), ("SECADO", ""),   # fase en curso: no es un resultado
])
def test_clave_resultado(valor, esperado):
    assert rs.clave_resultado(valor) == esperado


@pytest.mark.parametrize("valor, esperado", [
    ("FALLO_CALENTAMIENTO", "FALLO_CALENTAMIENTO"), ("EMERGENCIA", "EMERGENCIA"),
    ("COMPLETADO", ""), ("CANCELADO", ""), ("FALLO", ""), (None, ""), ("SECADO", ""),
])
def test_detalle_resultado_solo_si_dice_mas_que_la_clave(valor, esperado):
    assert rs.detalle_resultado(valor) == esperado


def test_resumen_con_fallo_real_de_la_base():
    r = rs.resumen_presentable({"ultimo_ciclo": {"resultado": "FALLO_CALENTAMIENTO"}})
    assert r["ultimo_resultado"] == "FALLO"
    assert r["ultimo_resultado_detalle"] == "FALLO_CALENTAMIENTO"


def test_resumen_sin_respuesta_todo_sin_dato():
    r = rs.resumen_presentable(None)
    assert r == {
        "ciclos_totales": SD, "ciclos_hoy": SD,
        "ultimo_fecha": SD, "ultimo_hora": SD, "ultimo_programa": SD,
        "ultimo_programa_nombre": SD, "ultimo_resultado": "",
        "ultimo_resultado_detalle": "", "ultimo_operador": SD,
    }


def test_resumen_sin_ciclos():
    r = rs.resumen_presentable({"ciclos_totales": 0, "ciclos_hoy": 0, "ultimo_ciclo": None})
    assert r["ciclos_totales"] == "0" and r["ciclos_hoy"] == "0"
    assert (r["ultimo_fecha"], r["ultimo_hora"], r["ultimo_programa"], r["ultimo_resultado"]) \
        == (SD, SD, SD, "")


def test_resumen_un_ciclo():
    r = rs.resumen_presentable({
        "ciclos_totales": 128, "ciclos_hoy": 3,
        "ultimo_ciclo": {"numero_ciclo": 128, "fecha_inicio": "2026-10-02T14:25:10",
                         "fecha_fin": "2026-10-02T15:02:00", "programa_id": "instrumental_134",
                         "programa_nombre": "Instrumental 134", "programa_numero": 2,
                         "resultado": "CANCELADO"},
    })
    assert r == {
        "ciclos_totales": "128", "ciclos_hoy": "3",
        "ultimo_fecha": "02/10/2026", "ultimo_hora": "14:25", "ultimo_programa": "02",
        "ultimo_programa_nombre": "Instrumental 134", "ultimo_resultado": "CANCELADO",
        "ultimo_resultado_detalle": "",
        "ultimo_operador": SD,   # sin operador guardado (Paso 1 b)
    }


def test_resumen_mal_formado_no_tumba_el_resto():
    r = rs.resumen_presentable({"ciclos_totales": "x", "ciclos_hoy": 4,
                                "ultimo_ciclo": {"fecha_inicio": None, "resultado": None}})
    assert r["ciclos_totales"] == SD and r["ciclos_hoy"] == "4"
    assert r["ultimo_fecha"] == SD and r["ultimo_resultado"] == ""
    assert rs.resumen_presentable(["no", "es", "dict"])["ciclos_hoy"] == SD
    assert rs.resumen_presentable({"ultimo_ciclo": "texto"})["ultimo_programa"] == SD


def test_operador_guardado_se_muestra():
    r = rs.resumen_presentable({"ultimo_ciclo": {"operador": "Ana Pérez"}})
    assert r["ultimo_operador"] == "Ana Pérez"
    for vacio in (None, "", "   ", 7):
        assert rs.resumen_presentable({"ultimo_ciclo": {"operador": vacio}})["ultimo_operador"] == SD


@pytest.mark.parametrize("respuesta, esperado", [
    ({"ultimo_ciclo": {"id": 42}}, 42),
    ({"ultimo_ciclo": {"id": True}}, None),
    ({"ultimo_ciclo": {"id": "42"}}, None),
    ({"ultimo_ciclo": None}, None),
    (None, None),
])
def test_id_del_ultimo_ciclo(respuesta, esperado):
    assert rs.id_ultimo_ciclo(respuesta) == esperado


# ── listado de ciclos (Ciclos hoy e Historial) ────────────────────────────

_CICLO = {"id": 80, "numero_ciclo": 80, "fecha_inicio": "2026-10-02T08:05:00",
          "fecha_fin": "2026-10-02T08:40:00", "programa_id": "instrumental_134",
          "programa_nombre": "Instrumental 134", "programa_numero": 2,
          "resultado": "FALLO_SECADO", "operador": None}


def test_ciclo_presentable():
    assert rs.ciclo_presentable(_CICLO) == {
        "id": 80, "numero": "80", "fecha": "02/10/2026", "hora": "08:05",
        "programa": "02", "programa_nombre": "Instrumental 134",
        "resultado": "FALLO", "resultado_detalle": "FALLO_SECADO", "operador": SD,
    }


def test_ciclo_presentable_mal_formado():
    c = rs.ciclo_presentable({"id": "x", "numero_ciclo": None})
    assert c["id"] == -1 and c["numero"] == SD and c["fecha"] == SD and c["resultado"] == ""


def test_lista_presentable():
    r = rs.lista_presentable({"periodo": "dia", "truncado": True,
                              "ciclos": [_CICLO, "basura", {**_CICLO, "id": 79, "resultado": None}]})
    assert r["truncado"] is True
    assert [c["id"] for c in r["ciclos"]] == [80, 79]      # filas que no son dict se descartan
    assert r["ciclos"][1]["resultado"] == ""


@pytest.mark.parametrize("respuesta", [None, [], {"ciclos": "no"}, "texto"])
def test_lista_presentable_sin_respuesta(respuesta):
    assert rs.lista_presentable(respuesta) == {"ciclos": [], "truncado": False}
