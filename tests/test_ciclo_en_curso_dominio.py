# tests/test_ciclo_en_curso_dominio.py
#
# Dominio de la pantalla de ciclo en curso (ui_qml/domain/ciclo_en_curso.py):
# acumulación incremental de la gráfica, inicios de fase para los divisores y
# normalización de GET /cycle/current/progress (frontera de confianza).

import pytest

from autoclave.ui_qml.domain.ciclo_en_curso import (
    AcumuladorGrafica, normalizar_progreso,
)


def _lectura(i, t_s, fase_ui="vacio", tc=80.0, tr=79.0, p=101.3):
    return {"id": i, "t_s": t_s, "fase": "PRE_VACIO", "fase_ui": fase_ui,
            "temp_camara": tc, "temp_ref": tr, "pres_camara": p}


# ── acumulador ──────────────────────────────────────────────────────────

def test_acumulador_vacio_pide_historico_completo():
    acc = AcumuladorGrafica()
    assert acc.desde_id is None
    # Tanda 17 (SON-01, decisión de Cristian): también la serie de Cámara 2
    assert acc.datos() == {"t_min": [], "temp_camara": [], "temp_ref": [], "pres_camara": [],
                           "temp_2_camara": []}


def test_acumulador_incorpora_y_convierte_a_minutos():
    acc = AcumuladorGrafica()
    assert acc.incorporar({"ciclo_db_id": 5, "lecturas": [_lectura(1, 0.0), _lectura(2, 30.0)]})
    assert acc.desde_id == 2
    d = acc.datos()
    assert d["t_min"] == [0.0, 0.5]
    assert d["temp_ref"] == [79.0, 79.0]


def test_acumulador_incremental_ignora_repetidas():
    acc = AcumuladorGrafica()
    acc.incorporar({"ciclo_db_id": 5, "lecturas": [_lectura(1, 0.0), _lectura(2, 1.0)]})
    assert acc.incorporar({"ciclo_db_id": 5, "lecturas": [_lectura(2, 1.0), _lectura(3, 2.0)]})
    assert acc.datos()["t_min"] == [0.0, 1 / 60, 2 / 60]
    assert not acc.incorporar({"ciclo_db_id": 5, "lecturas": []})


def test_acumulador_reinicia_al_cambiar_de_ciclo():
    acc = AcumuladorGrafica()
    acc.incorporar({"ciclo_db_id": 5, "lecturas": [_lectura(1, 0.0), _lectura(2, 1.0)]})
    assert acc.incorporar({"ciclo_db_id": 6, "lecturas": [_lectura(9, 0.0)]})
    assert acc.ciclo_db_id == 6
    assert acc.datos()["t_min"] == [0.0]
    assert acc.desde_id == 9


def test_acumulador_sin_ciclo_se_vacia():
    acc = AcumuladorGrafica()
    acc.incorporar({"ciclo_db_id": 5, "lecturas": [_lectura(1, 0.0)]})
    assert acc.incorporar({"ciclo_db_id": None, "lecturas": []})
    assert acc.datos()["t_min"] == []
    assert acc.desde_id is None


@pytest.mark.parametrize("basura", [
    None, [], "x", {"ciclo_db_id": 5, "lecturas": "x"},
    {"ciclo_db_id": 5, "lecturas": [None, {"id": "a", "t_s": 1}, {"id": 3, "t_s": "b"}]},
])
def test_acumulador_descarta_respuestas_mal_formadas(basura):
    acc = AcumuladorGrafica()
    acc.incorporar(basura)
    assert acc.datos()["t_min"] == []


def test_acumulador_valor_no_numerico_queda_sin_lectura():
    acc = AcumuladorGrafica()
    acc.incorporar({"ciclo_db_id": 5, "lecturas": [_lectura(1, 0.0, tc="x", tr=None)]})
    d = acc.datos()
    assert d["temp_camara"] == [None] and d["temp_ref"] == [None]


def test_inicios_de_fase_solo_de_las_que_aplican():
    acc = AcumuladorGrafica()
    acc.incorporar({"ciclo_db_id": 5, "lecturas": [
        _lectura(1, 0.0, "precalentamiento"),        # saltada: un instante en t = 0
        _lectura(2, 0.5, "vacio"), _lectura(3, 60.0, "vacio"),
        _lectura(4, 120.0, "calentamiento"), _lectura(5, 180.0, "calentamiento"),
    ]})
    assert acc.inicios_de_fase(["vacio", "calentamiento", "esterilizacion"]) == [
        {"clave": "vacio", "inicioMin": 0.0},        # la primera fase dibujada arranca en 0
        {"clave": "calentamiento", "inicioMin": 2.0},
    ]


def test_inicios_de_fase_sin_datos():
    assert AcumuladorGrafica().inicios_de_fase(["vacio"]) == []


# ── progreso ────────────────────────────────────────────────────────────

def test_progreso_sin_ciclo():
    p = normalizar_progreso({"activo": False})
    assert p["activo"] is False
    assert p["fases"] == [] and p["transcurrido_s"] is None and p["restante_s"] is None


def test_progreso_con_ciclo():
    p = normalizar_progreso({
        "activo": True, "ciclo_db_id": 7, "fase_ciclo": "CALENTAMIENTO",
        "fase_activa": "calentamiento", "transcurrido_s": 710.4, "restante_s": None,
        "fases": [{"fase": "vacio", "estado": "completada", "duracion_s": 650.0},
                  {"fase": "calentamiento", "estado": "activa", "duracion_s": 60.4},
                  {"fase": "secado", "estado": "pendiente", "duracion_s": None}],
    })
    assert p["activo"] is True
    assert p["fase_ciclo"] == "CALENTAMIENTO"
    assert p["transcurrido_s"] == 710.4 and p["restante_s"] is None
    assert p["fases"][1] == {"fase": "calentamiento", "estado": "activa", "duracion_s": 60.4}
    assert p["aplicables"] == ["vacio", "calentamiento", "secado"]


def test_progreso_descarta_fases_desconocidas_y_estados_invalidos():
    p = normalizar_progreso({"activo": True, "transcurrido_s": "x", "fases": [
        {"fase": "purga", "estado": "activa"},
        {"fase": "vacio", "estado": "rara", "duracion_s": 1.0},
        "basura",
        {"fase": "secado", "estado": "pendiente", "duracion_s": "x"},
    ]})
    assert p["transcurrido_s"] is None
    assert p["fases"] == [
        {"fase": "vacio", "estado": "pendiente", "duracion_s": 1.0},
        {"fase": "secado", "estado": "pendiente", "duracion_s": None},
    ]


@pytest.mark.parametrize("basura", [None, [], "x", 3])
def test_progreso_mal_formado_es_sin_ciclo(basura):
    assert normalizar_progreso(basura)["activo"] is False


@pytest.mark.parametrize("valor, esperado", [
    ("exitoso", "exitoso"), ("cancelado", "cancelado"), ("fallo", "fallo"),
    (None, None), ("raro", None), (3, None),
])
def test_progreso_resultado_validado(valor, esperado):
    assert normalizar_progreso({"activo": True, "resultado": valor})["resultado"] == esperado
    assert normalizar_progreso({"activo": False})["resultado"] is None
