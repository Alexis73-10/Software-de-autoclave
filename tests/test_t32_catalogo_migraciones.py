"""Tanda 32: catálogo, JSON y migraciones del enfriamiento de líquidos con
contrapresión (modos 4 y 5 de descompresión).

LIQ-01: presion_despresurizacion_chaqueta (kPa sobre la atmosférica, clase
«diferencia», 20, 5–50), timeout_despresurizacion_chaqueta (min, 3, 1–15) y
timeout_presurizacion_enfriamiento (min, 3, 1–15) en modo_4 y modo_5; se
retiran tiempo_apertura_chaqueta y tiempo_cierre_chaqueta.
LIQ-03: descompresion_lenta_rapida (bool, false) y presion_cambio (kPa abs,
150, 1–400) en modo_5; con la opción activa presion_cambio <
presion_camara_enfriamiento (COHERENCIA_DESCOMPRESION).
LIQ-04: liquidos.json (fábrica y usuario) con presion_camara_enfriamiento 300.
Migración al cargar (auditoría «migración tanda 32», sin SIS-06, .bak).
"""

import json
import shutil
from pathlib import Path

import pytest

from autoclave.core.managers import catalogo_parametros as cp
from autoclave.core.managers.cycle_manager import Cycle, CycleManager, migrar_parametros
from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.state_machine.alarms.catalogo import SIS_06

RAIZ = Path(__file__).resolve().parents[1]
CICLOS = RAIZ / "src" / "autoclave" / "cycles"
PROGRAMAS = sorted(str(p) for p in CICLOS.glob("*/*.json"))
LIQ01 = ("presion_despresurizacion_chaqueta", "timeout_despresurizacion_chaqueta",
         "timeout_presurizacion_enfriamiento")
LIQ03 = ("descompresion_lenta_rapida", "presion_cambio")
RETIRADOS = ("tiempo_apertura_chaqueta", "tiempo_cierre_chaqueta")


@pytest.fixture(autouse=True)
def _sin_config_equipo():
    cp.fijar_config_equipo(None)
    yield
    cp.fijar_config_equipo(None)


def _datos(nombre="factory/liquidos.json"):
    return json.loads((CICLOS / nombre).read_text(encoding="utf-8"))


def _ids(r):
    return "/".join(Path(r).parts[-2:])


# ── Programas del repositorio ───────────────────────────────────────────────

@pytest.mark.parametrize("ruta", PROGRAMAS, ids=_ids)
def test_programas_del_repo_con_los_parametros(ruta):
    p = json.loads(Path(ruta).read_text(encoding="utf-8"))["parameters"]
    desc = p["descompresion"]
    for modo in ("modo_4", "modo_5"):
        m = desc[modo]
        for clave in RETIRADOS:
            assert clave not in m
        h = m["presion_despresurizacion_chaqueta"]
        assert (h["value"], h["type"], h["unit"], h["clase"], h["min"], h["max"]) == \
            (20.0, "float", "kPa", "diferencia", 5, 50)
        for clave in LIQ01[1:]:
            h = m[clave]
            assert (h["value"], h["type"], h["unit"], h["min"], h["max"]) == (3, "int", "min", 1, 15)
    m5 = desc["modo_5"]
    assert m5["descompresion_lenta_rapida"]["value"] is False
    assert m5["descompresion_lenta_rapida"]["type"] == "bool"
    h = m5["presion_cambio"]
    assert (h["value"], h["type"], h["unit"], h["clase"]) == (150, "int", "kPa", "absoluto")
    for clave in LIQ03:
        assert clave not in desc["modo_4"]
    # otros modos: sin cambios (los tiempos solo existían en 4 y 5)
    for modo in ("modo_1", "modo_2", "modo_3"):
        assert not set(desc[modo]) & set(RETIRADOS + LIQ01 + ("descompresion_lenta_rapida",))
    assert cp.errores_programa(p) == []
    agregadas = []
    migrar_parametros(p, [], [], recuperacion=True, agregadas=agregadas)
    # CRI-04 (tanda 35): la marca de significado de la brecha es la unica agregada
    assert [a for a in agregadas if a["parametro"] != "brecha_segura_presion"] == []


# ── Catálogo ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("modo", ["modo_4", "modo_5"])
def test_catalogo_rangos_liq01(modo):
    assert cp.limites("descompresion", f"{modo}.presion_despresurizacion_chaqueta") == (5, 50)
    assert cp.limites("descompresion", f"{modo}.timeout_despresurizacion_chaqueta") == (1, 15)
    assert cp.limites("descompresion", f"{modo}.timeout_presurizacion_enfriamiento") == (1, 15)
    hoja = {"type": "float"}
    ruta = [modo, "presion_despresurizacion_chaqueta"]
    assert cp.coercionar(hoja, "descompresion", ruta, 5) == 5
    assert cp.coercionar(hoja, "descompresion", ruta, 50) == 50
    for malo in (4.9, 50.1, True, "20"):
        with pytest.raises(ValueError):
            cp.coercionar(hoja, "descompresion", ruta, malo)
    for clave in LIQ01[1:]:
        ruta = [modo, clave]
        assert cp.coercionar({"type": "int"}, "descompresion", ruta, 15) == 15
        for malo in (0, 16, 2.5):
            with pytest.raises(ValueError):
                cp.coercionar({"type": "int"}, "descompresion", ruta, malo)


def test_catalogo_presion_cambio_modo5_como_modo3():
    assert cp.limites("descompresion", "modo_5.presion_cambio") == \
        cp.limites("descompresion", "modo_3.presion_cambio") == (1, 400)
    hoja = {"type": "int", "min": 0, "max": 500}
    for malo in (0, 401):
        with pytest.raises(ValueError):
            cp.coercionar(hoja, "descompresion", ["modo_5", "presion_cambio"], malo)
    with pytest.raises(ValueError):
        cp.coercionar({"type": "bool"}, "descompresion",
                      ["modo_5", "descompresion_lenta_rapida"], 1)


def test_catalogo_sin_los_tiempos_retirados():
    for (fase, ruta) in cp.CATALOGO:
        assert not any(r in ruta for r in RETIRADOS), ruta


def test_defectos_en_constantes():
    assert cp.PRESION_DESPRESURIZACION_CHAQUETA_DEFECTO == 20.0
    assert cp.TIMEOUT_DESPRESURIZACION_CHAQUETA_DEFECTO == 3
    assert cp.TIMEOUT_PRESURIZACION_ENFRIAMIENTO_DEFECTO == 3
    assert cp.DESCOMPRESION_LENTA_RAPIDA_DEFECTO is False
    assert cp.PRESION_CAMBIO_MODO_5_DEFECTO == 150
    assert cp.ORIGEN_MIGRACION_T32 == "migración tanda 32"


# ── Coherencia LIQ-03 ───────────────────────────────────────────────────────

def _con_opcion(activa, cambio, enfr=300):
    p = _datos()["parameters"]
    m5 = p["descompresion"]["modo_5"]
    m5["descompresion_lenta_rapida"]["value"] = activa
    m5["presion_cambio"]["value"] = cambio
    m5["presion_camara_enfriamiento"]["value"] = enfr
    return p


@pytest.mark.parametrize("cambio", [300, 350])
def test_coherencia_activa_rechaza_cambio_no_menor(cambio):
    p = _con_opcion(True, cambio)
    errores = cp.errores_coherencia(p)
    assert errores and cp.codigo_coherencia(errores) == cp.CODIGO_COHERENCIA_DESCOMPRESION
    assert any("presion_cambio" in e for e in cp.errores_programa(p))


def test_coherencia_activa_acepta_cambio_menor():
    assert cp.errores_programa(_con_opcion(True, 299)) == []


def test_coherencia_inactiva_sin_regla():
    assert cp.errores_programa(_con_opcion(False, 350)) == []


def test_coherencia_activa_sin_presion_cambio_falla_cerrada():
    p = _con_opcion(True, 150)
    del p["descompresion"]["modo_5"]["presion_cambio"]
    assert cp.errores_descompresion(p)


def test_coherencia_tambien_en_programa_solido():
    p = _datos("factory/instrumental_134.json")["parameters"]
    m5 = p["descompresion"]["modo_5"]
    m5["descompresion_lenta_rapida"]["value"] = True
    m5["presion_cambio"]["value"] = m5["presion_camara_enfriamiento"]["value"]
    assert cp.codigo_coherencia(cp.errores_coherencia(p)) == cp.CODIGO_COHERENCIA_DESCOMPRESION


def test_set_param_rechaza_y_no_muta():
    c = Cycle("liquidos", "L", _datos()["parameters"], 4)
    c.set_param("descompresion", ["modo_5", "presion_cambio"], 200)
    c.set_param("descompresion", ["modo_5", "descompresion_lenta_rapida"], True)
    with pytest.raises(cp.ErrorCoherencia) as e:
        c.set_param("descompresion", ["modo_5", "presion_cambio"], 300)
    assert e.value.codigo == "COHERENCIA_DESCOMPRESION"
    assert c.get_param("descompresion", "modo_5", "presion_cambio") == 200
    with pytest.raises(cp.ErrorCoherencia):
        c.set_param("descompresion", ["modo_5", "presion_camara_enfriamiento"], 200)
    assert c.get_param("descompresion", "modo_5", "presion_camara_enfriamiento") == 300
    # desactivada, la regla no rige
    c.set_param("descompresion", ["modo_5", "descompresion_lenta_rapida"], False)
    c.set_param("descompresion", ["modo_5", "presion_cambio"], 300)


# ── LIQ-04 ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("nombre", ["factory/liquidos.json", "user/liquidos.json"])
def test_liq04_contrapresion_300_cumple_las_reglas(nombre):
    p = _datos(nombre)["parameters"]
    assert p["globals"]["tipo_carga"]["value"] == "liquido"
    t_est = p["esterilizacion"]["temperatura_esterilizacion"]["value"]
    minimo = p_saturacion_kpa(t_est) + cp.MARGEN_CONTRAPRESION_LIQUIDO
    alivio = cp.limites_presion_equipo().alivio_camara
    for modo in ("modo_4", "modo_5"):
        v = p["descompresion"][modo]["presion_camara_enfriamiento"]["value"]
        assert v == 300
        assert minimo <= v < alivio
    assert round(p_saturacion_kpa(121) + 30) == 235 and alivio == 385
    assert cp.errores_programa(p) == []


def test_liq04_otros_programas_sin_cambio():
    for nombre in ("bowe_dick", "instrumental_121", "instrumental_134", "textiles"):
        for origen in ("factory", "user"):
            p = _datos(f"{origen}/{nombre}.json")["parameters"]["descompresion"]
            assert p["modo_4"]["presion_camara_enfriamiento"]["value"] != 300
            assert p["modo_5"]["presion_camara_enfriamiento"]["value"] != 300


def test_liq04_no_se_migra_un_programa_instalado():
    p = _datos()["parameters"]
    for modo in ("modo_4", "modo_5"):
        p["descompresion"][modo]["presion_camara_enfriamiento"]["value"] = 250
    migrar_parametros(p, [], [], recuperacion=True, agregadas=[])
    for modo in ("modo_4", "modo_5"):
        assert p["descompresion"][modo]["presion_camara_enfriamiento"]["value"] == 250


# ── Migración ───────────────────────────────────────────────────────────────

def _programa_viejo(nombre="factory/liquidos.json"):
    p = _datos(nombre)["parameters"]
    for modo in ("modo_4", "modo_5"):
        m = p["descompresion"][modo]
        for clave in LIQ01 + LIQ03:
            m.pop(clave, None)
        m["tiempo_apertura_chaqueta"] = {"value": 7, "type": "int", "unit": "sec",
                                         "min": 1, "max": 3600}
        m["tiempo_cierre_chaqueta"] = {"value": 0, "type": "int", "unit": "sec",
                                       "min": 0, "max": 3600}
        m["timeout"] = m.pop("timeout")          # timeout al final, como antes
    return p


def test_migracion_agrega_y_retira():
    p = _programa_viejo()
    agregadas, corr = [], []
    assert migrar_parametros(p, corr, agregadas=agregadas) is True
    assert corr == []
    desc = p["descompresion"]
    assert list(desc["modo_4"]) == ["presion_camara_enfriamiento", "temperatura_enfriamiento",
                                    *LIQ01, "timeout"]
    assert list(desc["modo_5"]) == ["presion_camara_enfriamiento", "temperatura_enfriamiento",
                                    *LIQ01, *LIQ03, "timeout"]
    assert desc["modo_4"]["presion_despresurizacion_chaqueta"]["value"] == 20.0
    assert desc["modo_5"]["descompresion_lenta_rapida"]["value"] is False
    assert desc["modo_5"]["presion_cambio"]["value"] == 150
    registros = {(a["parametro"], a["anterior"], a["nuevo"]) for a in agregadas}
    assert ("modo_4.tiempo_apertura_chaqueta", 7, None) in registros
    assert ("modo_5.tiempo_cierre_chaqueta", 0, None) in registros
    assert ("modo_4.presion_despresurizacion_chaqueta", None, 20.0) in registros
    assert ("modo_5.timeout_presurizacion_enfriamiento", None, 3) in registros
    assert ("modo_5.descompresion_lenta_rapida", None, False) in registros
    assert ("modo_5.presion_cambio", None, 150) in registros
    assert len(agregadas) == 2 * 2 + 3 * 2 + 2
    assert {a["origen"] for a in agregadas} == {"migración tanda 32"}
    assert {a["fase"] for a in agregadas} == {"descompresion"}
    assert cp.errores_programa(p) == []
    # idempotente; un valor existente nunca se toca
    desc["modo_4"]["presion_despresurizacion_chaqueta"]["value"] = 12.0
    otra = []
    migrar_parametros(p, agregadas=otra)
    assert otra == [] and desc["modo_4"]["presion_despresurizacion_chaqueta"]["value"] == 12.0


def test_migracion_sin_timeout_agrega_al_final_y_no_toca_otros_modos():
    p = _programa_viejo()
    del p["descompresion"]["modo_4"]["timeout"]
    antes = {m: json.dumps(p["descompresion"][m]) for m in ("modo_1", "modo_2", "modo_3")}
    migrar_parametros(p, agregadas=[])
    assert list(p["descompresion"]["modo_4"])[-3:] == list(LIQ01)
    assert {m: json.dumps(p["descompresion"][m]) for m in antes} == antes


def test_programa_sin_modos_de_enfriamiento_no_recibe_nada():
    p = {"descompresion": {"modo": {"value": 1}}}
    agregadas = []
    migrar_parametros(p, agregadas=agregadas)
    assert p == {"descompresion": {"modo": {"value": 1}, "presion_fin_descompresion":
                                   p["descompresion"]["presion_fin_descompresion"]}}
    assert [a for a in agregadas if a["origen"] == "migración tanda 32"] == []


def test_copia_e_instantanea_no_repiten_la_migracion():
    c = Cycle("liquidos", "L", _programa_viejo(), 4)
    assert len(c.migraciones_agregadas) == 12
    assert c.copia().migraciones_agregadas == []
    assert Cycle.desde_instantanea(c.instantanea()).migraciones_agregadas == []


def test_migracion_al_cargar_con_auditoria_sin_sis06_y_bak(tmp_path):
    from autoclave.backend.context import BackendContext
    from autoclave.services.domain.logging.db_manager import DbManager
    destino = tmp_path / "cycles"
    shutil.copytree(CICLOS / "factory", destino / "factory")
    (destino / "user").mkdir()
    datos = _datos("user/liquidos.json")
    datos["parameters"] = _programa_viejo("user/liquidos.json")
    ruta = destino / "user" / "liquidos.json"
    ruta.write_text(json.dumps(datos, indent=4, ensure_ascii=False), encoding="utf-8")
    cid = datos["cycle_id"]

    def cargar():
        ctx = BackendContext()
        cm = CycleManager()
        cm.raiz = str(tmp_path)
        cm.load_all_cycles()
        ctx.cycle_manager = cm
        return ctx

    ctx = cargar()
    c = ctx.cycle_manager.cycles[cid]
    assert not c.danado
    assert c.get_param("descompresion", "modo_5", "presion_cambio") == 150
    assert c.get_param("descompresion", "modo_4", "tiempo_apertura_chaqueta") is None
    # CRI-04: la fila de brecha_segura_presion es aparte (sin SIS-06)
    assert len([m for _, m in ctx.cycle_manager.migraciones_agregadas()
                if m["parametro"] != "brecha_segura_presion"]) == 12
    assert ctx.cycle_manager.migraciones_correctivas() == []
    ctx._avisar_migraciones_correctivas()
    assert not [i for i in ctx.alarm_manager.activas() if i.definicion.codigo == SIS_06]
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.auditar_migraciones_correctivas()
    filas = {f["entidad"]: f for f in ctx.db.get_auditoria(evento="param_ciclo_cambio")}
    f = filas[f"{cid}/descompresion/modo_4.presion_despresurizacion_chaqueta"]
    assert f["valor_anterior"] is None and f["valor_nuevo"] == "20.0"
    assert f["detalle"]["origen"] == "migración tanda 32" and f["usuario"] == "sistema"
    f = filas[f"{cid}/descompresion/modo_5.tiempo_apertura_chaqueta"]
    assert f["valor_anterior"] == "7" and f["valor_nuevo"] is None
    escrito = json.loads(ruta.read_text(encoding="utf-8"))["parameters"]["descompresion"]
    assert "tiempo_apertura_chaqueta" not in escrito["modo_4"]
    assert escrito["modo_5"]["descompresion_lenta_rapida"]["value"] is False
    bak = json.loads((ruta.parent / (ruta.name + ".bak")).read_text(encoding="utf-8"))
    assert bak["parameters"]["descompresion"]["modo_4"]["tiempo_apertura_chaqueta"]["value"] == 7
    ctx.auditar_migraciones_correctivas()
    assert len([f for f in ctx.db.get_auditoria(evento="param_ciclo_cambio")
                if "/descompresion/modo_" in f["entidad"]]) == 12
    # CRI-04: los programas de fabrica no se reescriben y repiten su fila de brecha;
    # el programa de usuario migrado ya no
    assert [m for c, m in cargar().cycle_manager.migraciones_agregadas()
            if c.source == "user" or m["parametro"] != "brecha_segura_presion"] == []


# ── Textos y pantalla ───────────────────────────────────────────────────────

@pytest.mark.parametrize("idioma", ["es", "en"])
def test_textos_de_los_parametros(idioma):
    from autoclave import i18n
    for modo, claves in (("modo_4", LIQ01), ("modo_5", LIQ01 + LIQ03)):
        for clave in claves:
            assert i18n.existe(f"parametros.descompresion.{modo}.{clave}", idioma)
            assert i18n.existe(f"parametros_desc.descompresion.{modo}.{clave}", idioma)
        for clave in RETIRADOS:
            assert not i18n.existe(f"parametros.descompresion.{modo}.{clave}", idioma)
            assert not i18n.existe(f"parametros_desc.descompresion.{modo}.{clave}", idioma)
    assert i18n.existe("opciones.err_coherencia_descompresion", idioma)


def test_codigo_de_error_con_texto_en_la_pantalla():
    from autoclave.ui_qml import sesion_backend
    from autoclave.ui_qml.controllers import parametros_ciclo_controller as pcc
    assert pcc.mensaje_de("COHERENCIA_DESCOMPRESION") == "opciones.err_coherencia_descompresion"
    assert sesion_backend._CLAVES["COHERENCIA_DESCOMPRESION"] == \
        "opciones.err_coherencia_descompresion"


def test_pantalla_modo_5_muestra_los_parametros_nuevos():
    from tests.helpers.backend_doble import cargar_servidor, modulo_backend
    cargar_servidor()
    _hojas_seccion = modulo_backend("rutas.programas")._hojas_seccion
    c = Cycle("liquidos", "L", _datos()["parameters"], 4)
    c.set_param("descompresion", ["modo"], 5)
    rutas = [".".join(r) for r, _ in _hojas_seccion(c, "descompresion")]
    for clave in LIQ01 + LIQ03:
        assert f"modo_5.{clave}" in rutas
    assert not [r for r in rutas if r.startswith("modo_4.")]
    c.set_param("descompresion", ["modo"], 4)
    rutas = [".".join(r) for r, _ in _hojas_seccion(c, "descompresion")]
    assert {f"modo_4.{k}" for k in LIQ01} <= set(rutas)
    assert not [r for r in rutas if "descompresion_lenta_rapida" in r or "presion_cambio" in r]


# ── M-A (segunda revisión): contrapresión de enfriamiento bajo el alivio ────

class _ConfigEquipo:
    def __init__(self, **valores):
        self._v = {"presion_fondo_escala": 400, "presion_suministro_vapor": 350,
                   "presion_alivio_camara": 385, "presion_alivio_chaqueta": 385}
        self._v.update(valores)

    def get(self, clave, defecto=None):
        return self._v.get(clave, defecto)


def _con_enfriamiento(valor, modo="modo_4", nombre="factory/liquidos.json"):
    p = _datos(nombre)["parameters"]
    p["descompresion"][modo]["presion_camara_enfriamiento"]["value"] = valor
    return p


def test_ma_margen_igual_al_de_limites_equipo():
    from autoclave.core.managers import limites_equipo
    assert cp.MARGEN_CONTRAPRESION_BAJO_ALIVIO == limites_equipo.MARGEN_CORTE_BAJO_ALIVIO


@pytest.mark.parametrize("modo", ["modo_4", "modo_5"])
@pytest.mark.parametrize("valor", [376, 380, 400])
def test_ma_rechaza_sobre_alivio_menos_10(modo, valor):
    p = _con_enfriamiento(valor, modo)
    errores = cp.errores_programa(p)                       # al cargar
    assert any("presion_camara_enfriamiento" in e and "alivio" in e for e in errores)
    lim = cp.errores_limites_fisicos(p)
    assert lim and cp.codigo_coherencia(lim) == cp.CODIGO_LIMITE_CONTRAPRESION
    assert cp.valor_limite(p) == 375.0


@pytest.mark.parametrize("valor", [300, 375])
def test_ma_acepta_hasta_alivio_menos_10(valor):
    for modo in ("modo_4", "modo_5"):
        assert cp.errores_programa(_con_enfriamiento(valor, modo)) == []


def test_ma_tambien_en_programa_solido_y_codigo_propio():
    p = _con_enfriamiento(390, "modo_5", "factory/instrumental_134.json")
    errores = cp.errores_coherencia(p)
    assert cp.codigo_coherencia(errores) == cp.CODIGO_LIMITE_CONTRAPRESION


def test_ma_usa_el_alivio_del_equipo():
    cp.fijar_config_equipo(_ConfigEquipo(presion_alivio_camara=360))
    assert cp.errores_programa(_con_enfriamiento(350)) == []
    p = _con_enfriamiento(351)
    assert cp.valor_limite(p) == 350.0
    assert cp.codigo_coherencia(cp.errores_limites_fisicos(p)) == cp.CODIGO_LIMITE_CONTRAPRESION


def test_ma_set_param_rechaza_y_no_muta():
    c = Cycle("liquidos", "L", _datos()["parameters"], 4)
    with pytest.raises(cp.ErrorCoherencia) as e:
        c.set_param("descompresion", ["modo_4", "presion_camara_enfriamiento"], 380)
    assert e.value.codigo == "LIMITE_CONTRAPRESION_ENFRIAMIENTO"
    assert e.value.valor == 375.0
    assert c.get_param("descompresion", "modo_4", "presion_camara_enfriamiento") == 300
    c.set_param("descompresion", ["modo_4", "presion_camara_enfriamiento"], 375)


def test_ma_no_se_migra_el_valor():
    p = _con_enfriamiento(390, "modo_5")
    migrar_parametros(p, [], [], recuperacion=True, agregadas=[])
    assert p["descompresion"]["modo_5"]["presion_camara_enfriamiento"]["value"] == 390
    assert cp.errores_programa(p)


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_ma_texto_y_codigo_en_la_pantalla(idioma):
    from autoclave import i18n
    from autoclave.ui_qml import sesion_backend
    from autoclave.ui_qml.controllers import parametros_ciclo_controller as pcc
    clave = "opciones.err_limite_contrapresion_enfriamiento"
    assert i18n.existe(clave, idioma)
    assert pcc.mensaje_de("LIMITE_CONTRAPRESION_ENFRIAMIENTO") == clave
    assert sesion_backend._CLAVES["LIMITE_CONTRAPRESION_ENFRIAMIENTO"] == clave
