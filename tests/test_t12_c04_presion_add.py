"""J12 (tanda 12, C-04): presion_add_* con máximo 30 kPa, B&D de usuario con 9,
migración correctiva 99 → 9 y techo de cámara Psat(T) + presion_add contra el
alivio de cámara (385 kPa, rechazo) y el suministro (350 kPa, advertencia)."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers import catalogo_parametros as cp
from autoclave.core.managers.cycle_manager import Cycle, CycleManager, migrar_parametros
from autoclave.core.runtime.steam import p_saturacion_kpa

RAIZ = Path(__file__).resolve().parents[1]
CICLOS = RAIZ / "src" / "autoclave" / "cycles"
_ADDS = (("calentamiento", "presion_add_calentamiento"),
         ("esterilizacion", "presion_add_esterilizacion"))


def _datos(nombre):
    return json.loads((CICLOS / nombre).read_text(encoding="utf-8"))


def test_bowe_dick_de_usuario_con_9():
    p = _datos("user/bowe_dick.json")["parameters"]
    assert p["calentamiento"]["presion_add_calentamiento"]["value"] == 9.0


@pytest.mark.parametrize("fase,clave", _ADDS)
def test_presion_add_31_rechazado_30_aceptado(fase, clave):
    hoja = {"type": "float", "min": 0, "max": 100}
    assert cp.coercionar(hoja, fase, [clave], 30) == 30
    with pytest.raises(ValueError, match="máximo 30"):
        cp.coercionar(hoja, fase, [clave], 31)


@pytest.mark.parametrize("fase,clave", _ADDS)
def test_programa_cargado_con_99_migra_a_9(fase, clave):
    p = _datos("factory/bowe_dick.json")["parameters"]
    p[fase][clave]["value"] = 99.0
    c = Cycle("bowe_dick", "Bowie & Dick", p, 1)
    assert c.get_param(fase, clave) == 9.0
    assert c.migraciones_correctivas == [{"fase": fase, "parametro": clave, "anterior": 99.0,
                                          "nuevo": 9.0, "origen": "migración tanda 12"}]
    assert cp.errores_programa(c.parameters) == []


def test_bd_original_de_usuario_migra_al_cargar(tmp_path):
    """El B&D de usuario instalado en sitio (134.5 °C, presion_add_calentamiento
    99) se carga migrado a 9, sin quedar dañado."""
    datos = _datos("user/bowe_dick.json")
    datos["parameters"]["calentamiento"]["presion_add_calentamiento"]["value"] = 99.0
    carpeta = tmp_path / "cycles" / "user"
    carpeta.mkdir(parents=True)
    (carpeta / "bowe_dick.json").write_text(json.dumps(datos), encoding="utf-8")
    cm = CycleManager()
    cm._load_from_folder(str(carpeta), source="user")
    c = cm.cycles["bowe_dick"]
    assert not c.danado and cm.errores_carga == []
    assert c.get_param("calentamiento", "presion_add_calentamiento") == 9.0
    assert [(x.id, m["parametro"], m["anterior"], m["nuevo"]) for x, m in cm.migraciones_correctivas()] \
        == [("bowe_dick", "presion_add_calentamiento", 99.0, 9.0)]


def test_bd_original_sin_migracion_queda_rechazado():
    """134.5 °C + 99 = 407.7 kPa (IAPWS-IF97, tanda 13; antes 405.7): sin la migración, el programa es inválido
    (catálogo > 30 y techo de cámara sobre el alivio)."""
    p = _datos("user/bowe_dick.json")["parameters"]
    p["calentamiento"]["presion_add_calentamiento"]["value"] = 99.0
    assert p_saturacion_kpa(134.5) + 99 == pytest.approx(407.7, abs=0.1)
    errores = cp.errores_programa(p)
    assert any("presion_add_calentamiento" in e and "máximo 30" in e for e in errores)
    assert any(e.startswith("Límite de presión de cámara") for e in errores)


def test_migracion_sin_valor_alto_no_corrige_y_agrega_claves_nuevas():
    p = {"globals": {"presion_chaqueta": {"value": 300}},
         "calentamiento": {"presion_add_calentamiento": {"value": 30.0}},
         "esterilizacion": {"presion_add_esterilizacion": {"value": 11.0}}}
    correcciones = []
    assert migrar_parametros(p, correcciones) is True
    assert correcciones == []
    assert p["calentamiento"]["presion_add_calentamiento"]["value"] == 30.0
    assert p["globals"]["delta_temp_chaqueta"]["value"] == 1.5
    assert p["globals"]["margen_flujo_chaqueta"]["value"] == 15.0
    assert p["esterilizacion"]["timeout_excursion_referencia"]["value"] == 5
    # segunda pasada: nada que migrar
    assert migrar_parametros(p, correcciones) is False


def test_migracion_no_crea_secciones():
    p = {"calentamiento": {"rango_temp_estabilizacion": {"value": 1.0}}}
    migrar_parametros(p)
    assert set(p) == {"calentamiento"}


def test_programa_que_sigue_invalido_tras_migrar_queda_danado_sin_romper(tmp_path):
    """C-04.4: tras migrar, si viola la regla 3 sigue el camino de programa
    inválido (dañado), sin romper la carga de los demás."""
    datos = _datos("factory/instrumental_134.json")
    datos["parameters"]["calentamiento"]["presion_add_calentamiento"]["value"] = 99.0
    datos["parameters"]["calentamiento"]["temperatura_calentamiento"]["value"] = 140.0
    datos["parameters"]["esterilizacion"]["temperatura_esterilizacion"]["value"] = 140.0
    carpeta = tmp_path / "cycles" / "user"
    carpeta.mkdir(parents=True)
    (carpeta / "malo.json").write_text(json.dumps(datos), encoding="utf-8")
    (carpeta / "bueno.json").write_text(
        json.dumps(_datos("factory/instrumental_121.json")), encoding="utf-8")
    cm = CycleManager()
    cm._load_from_folder(str(carpeta), source="user")
    malo = cm.cycles["134_instrumental"]
    assert malo.get_param("calentamiento", "presion_add_calentamiento") == 9.0
    assert malo.danado and any("consigna" in e for e in malo.danado)
    assert not cm.cycles["instrumental_121"].danado


# ── techo de cámara (C-04.3) ───────────────────────────────────────────────

def _cycle_alto(tipo):
    """Programa a 140.0 °C sin presion_add ni margen de chaqueta: la consigna
    (≈ 359 + 10 kPa) queda bajo el alivio, de modo que solo el techo de
    cámara decide."""
    nombre = "factory/liquidos.json" if tipo == "liquido" else "factory/instrumental_121.json"
    p = _datos(nombre)["parameters"]
    p["calentamiento"]["temperatura_calentamiento"]["value"] = 140.0
    p["esterilizacion"]["temperatura_esterilizacion"]["value"] = 140.0
    for fase, clave in _ADDS:
        p[fase][clave]["value"] = 0.0
    p["globals"]["delta_temp_chaqueta"]["value"] = 0.0
    p["globals"]["margen_flujo_chaqueta"]["value"] = 0.0
    if tipo == "liquido":
        p["descompresion"]["modo_4"]["presion_camara_enfriamiento"]["value"] = 395
    c = Cycle("p", "P", p, 9)
    assert cp.errores_programa(c.parameters) == []
    assert c.get_param("globals", "tipo_carga") == tipo
    return c


@pytest.mark.parametrize("tipo", ["solido", "liquido"])
@pytest.mark.parametrize("fase,clave", _ADDS)
def test_techo_sobre_el_alivio_se_rechaza(tipo, fase, clave):
    c = _cycle_alto(tipo)
    psat = p_saturacion_kpa(140.0)
    with pytest.raises(cp.ErrorCoherencia) as e:
        c.set_param(fase, [clave], 30.0)                  # techo = psat + 30 >= 385
    assert psat + 30 >= 385
    assert e.value.codigo == cp.CODIGO_LIMITE_CAMARA
    assert e.value.valor == pytest.approx(round(385 - psat, 1))
    assert f"menor que {385 - psat:.1f} kPa" in str(e.value)
    assert c.get_param(fase, clave) == 0.0


@pytest.mark.parametrize("tipo", ["solido", "liquido"])
@pytest.mark.parametrize("fase,clave", _ADDS)
def test_techo_entre_suministro_y_alivio_se_guarda_con_advertencia(tipo, fase, clave):
    c = _cycle_alto(tipo)
    c.set_param(fase, [clave], 5.0)                       # techo ≈ 364, bajo el alivio
    assert c.get_param(fase, clave) == 5.0
    adv = c.advertencias(fase, [clave])
    assert cp.ADVERTENCIA_TECHO_CAMARA in [a for a, _ in adv]
    assert any("válvula de vapor de cámara quedará abierta" in m for _, m in adv)


def test_techo_bajo_el_suministro_sin_advertencia():
    c = Cycle("p", "P", _datos("factory/instrumental_134.json")["parameters"], 2)
    c.set_param("calentamiento", ["presion_add_calentamiento"], 9.0)
    assert c.advertencias("calentamiento", ["presion_add_calentamiento"]) == []


# ── PATCH /cycle/parameter: rechazo con el máximo y advertencia ────────────

@pytest.fixture
def cliente(tmp_path):
    from fastapi.testclient import TestClient
    from tests.helpers.backend_doble import cabecera, cargar_servidor
    c = _cycle_alto("solido")
    ruta = tmp_path / "prog.json"
    ruta.write_text(json.dumps({"cycle_id": "prog", "parameters": c.parameters}), encoding="utf-8")
    c.id, c.source, c._path = "prog", "user", str(ruta)
    ctx = MagicMock()
    ctx.sin_base_de_datos = False
    ctx.cycle_manager.cycles = {"prog": c}
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app, headers=cabecera(srv, "ingeniero")), c


def _patch(client, clave, valor):
    return client.patch("/cycle/parameter", json={
        "cycle_id": "prog", "fase": "calentamiento", "path": [clave], "value": valor})


def test_patch_rechaza_el_techo_con_el_maximo(cliente):
    client, c = cliente
    r = _patch(client, "presion_add_calentamiento", 30.0)
    assert r.status_code == 422
    cuerpo = r.json()
    assert cuerpo["codigo"] == cp.CODIGO_LIMITE_CAMARA
    assert cuerpo["valor"] == pytest.approx(round(385 - p_saturacion_kpa(140.0), 1))
    assert c.get_param("calentamiento", "presion_add_calentamiento") == 0.0


def test_patch_guarda_con_advertencia(cliente):
    client, c = cliente
    r = _patch(client, "presion_add_calentamiento", 5.0)
    assert r.status_code == 200
    assert [a["clave"] for a in r.json()["advertencias"]] == [cp.ADVERTENCIA_TECHO_CAMARA]
    assert c.get_param("calentamiento", "presion_add_calentamiento") == 5.0


def test_patch_sin_advertencia_no_trae_la_clave(cliente):
    client, _ = cliente
    r = client.patch("/cycle/parameter", json={
        "cycle_id": "prog", "fase": "esterilizacion", "path": ["tiempo_esterilizacion"], "value": 20})
    assert r.status_code == 200 and "advertencias" not in r.json()


# ── pantalla: código del rechazo y texto de la advertencia ─────────────────

def test_controlador_traduce_rechazo_y_advertencia():
    pytest.importorskip("PySide6")
    from autoclave.ui_qml.controllers import parametros_ciclo_controller as pc
    from autoclave import i18n
    for codigo in (cp.CODIGO_LIMITE_CAMARA, cp.CODIGO_LIMITE_CONSIGNA, cp.CODIGO_LIMITE_CHAQUETA):
        clave = pc.mensaje_de(codigo)
        assert clave != "opciones.err_generico"
        for idioma in ("es", "en"):
            assert i18n.existe(clave, idioma) and "{valor}" in i18n.t(clave, idioma)
    for clave in (cp.ADVERTENCIA_TECHO_CAMARA, cp.ADVERTENCIA_CHAQUETA_ABIERTA):
        assert pc._ADVERTENCIAS[clave] == "opciones." + clave
        for idioma in ("es", "en"):
            assert i18n.existe(pc._ADVERTENCIAS[clave], idioma)
