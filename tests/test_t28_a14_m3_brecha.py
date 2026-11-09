"""A14-M3 (tanda 28, decisión de Cristian): brecha_segura_temperatura = 0,3 °C.

- 0,3 en todos los programas y como defecto del catálogo;
- se retira el paso 1 de P2 (0,3 → 1,0 en cada carga);
- migración única al cargar: 1,0 → 0,3 con auditoría «migración tanda 28
  (M3)», SIS-06 y .bak; la marca en la hoja la hace idempotente; un valor
  distinto de 1,0 y 0,3 no se toca;
- COHERENCIA_RECUPERACION se cumple con presion_add_esterilizacion sin cambio
  y la histéresis C-08 no cambia;
- escenario simulado de 134 °C (planta de A14-diag) con M1+M2+M3."""

import json
import shutil
from pathlib import Path

import pytest

from autoclave.core.managers import catalogo_parametros as cp
from autoclave.core.managers.cycle_manager import Cycle, CycleManager, migrar_parametros
from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.state_machine.alarms.catalogo import SIS_06
from autoclave.state_machine.cycle_phases import esterilizacion as est

pytestmark = pytest.mark.req("A14")

RAIZ = Path(__file__).resolve().parents[1]
CICLOS = RAIZ / "src" / "autoclave" / "cycles"
CLAVE = "brecha_segura_temperatura"
MARCA = cp.MARCA_MIGRACION_T28_M3


@pytest.fixture(autouse=True)
def _sin_config_equipo():
    cp.fijar_config_equipo(None)
    yield
    cp.fijar_config_equipo(None)


def _datos(nombre):
    return json.loads((CICLOS / nombre).read_text(encoding="utf-8"))


def _instalar(tmp_path, brecha, nombre="user/instrumental_134.json", marca=False):
    destino = tmp_path / "cycles"
    shutil.copytree(CICLOS / "factory", destino / "factory")
    (destino / "user").mkdir()
    datos = _datos(nombre)
    hoja = datos["parameters"]["esterilizacion"][CLAVE]
    hoja["value"] = brecha
    if marca:
        hoja[MARCA] = True
    ruta = destino / "user" / Path(nombre).name
    ruta.write_text(json.dumps(datos, indent=4, ensure_ascii=False), encoding="utf-8")
    return ruta


def _cargar(tmp_path):
    from autoclave.backend.context import BackendContext
    ctx = BackendContext()
    cm = CycleManager()
    cm.raiz = str(tmp_path)
    cm.load_all_cycles()
    ctx.cycle_manager = cm
    return ctx


def _correcciones(ctx, cycle_id="134_instrumental"):
    return {m["parametro"]: (m["anterior"], m["nuevo"], m["origen"])
            for c, m in ctx.cycle_manager.migraciones_correctivas() if c.id == cycle_id}


def _auditar(ctx, tmp_path):
    from autoclave.services.domain.logging.db_manager import DbManager
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.auditar_migraciones_correctivas()
    return ctx.db


# ── Valores y catálogo ──────────────────────────────────────────────────────

def test_defecto_del_catalogo_y_constantes_retiradas():
    assert cp.BRECHA_SEGURA_TEMPERATURA_DEFECTO == 0.3
    assert cp.ORIGEN_MIGRACION_T28_M3 == "migración tanda 28 (M3)"
    assert not hasattr(cp, "BRECHA_SEGURA_VIEJA") and not hasattr(cp, "BRECHA_SEGURA_NUEVA")


@pytest.mark.parametrize("ruta", sorted(str(p) for p in CICLOS.glob("*/*.json")),
                         ids=lambda r: "/".join(Path(r).parts[-2:]))
def test_programas_del_repo_con_0_3_y_coherentes(ruta):
    p = json.loads(Path(ruta).read_text(encoding="utf-8"))["parameters"]
    assert p["esterilizacion"][CLAVE]["value"] == 0.3
    assert cp.errores_programa(p) == []
    # presion_add_esterilizacion sin cambio (15 a 134/134,5 °C, 11 a 121 °C);
    # tanda 33 (CAS-05): liquidos sube a 15 a 121 °C
    t = p["esterilizacion"]["temperatura_esterilizacion"]["value"]
    add = p["esterilizacion"]["presion_add_esterilizacion"]["value"]
    esperado = 15.0 if (t != 121.0 or Path(ruta).name == "liquidos.json") else 11.0
    assert add == esperado
    corr, no_apl = [], []
    migrar_parametros(p, corr, no_apl, recuperacion=True)
    assert corr == [] and no_apl == []
    assert p["esterilizacion"][CLAVE]["value"] == 0.3


@pytest.mark.parametrize("t_est,minimo", [(134.0, 8.1), (121.0, 5.9)])
def test_coherencia_recuperacion_con_brecha_0_3(t_est, minimo):
    m = cp.presion_add_minima_recuperacion(t_est, 0.3)
    assert m == pytest.approx(minimo, abs=0.05)
    assert m == pytest.approx(p_saturacion_kpa(t_est + 0.9) - p_saturacion_kpa(t_est))


def test_histeresis_c08_sin_cambio():
    assert est._HIST_RECUP_TEMP_K == 0.3
    assert est._HIST_RECUP_PRES_KPA == 1.0
    assert cp.HIST_SALIDA_RECUPERACION_K == 0.3


def test_valores_esperados_a_134():
    p_sp = cp.consigna_pwm_esterilizacion(134.0, 0.3)
    assert p_sp == pytest.approx(p_saturacion_kpa(134.6))
    assert p_sp == pytest.approx(309.6, abs=0.05)
    techo = p_saturacion_kpa(134.0) + 15.0
    # margen del borde alto de la banda (P_sp + 1) al techo de control
    assert techo - (p_sp + cp.BANDA_PWM_ALTA_KPA) == pytest.approx(8.6, abs=0.05)
    # sin la advertencia de A14-M1 en los programas de fábrica
    for nombre in ("factory/instrumental_134.json", "factory/instrumental_121.json",
                   "factory/bowe_dick.json"):
        claves = [c for c, _ in cp.advertencias_programa(_datos(nombre)["parameters"])]
        assert cp.ADVERTENCIA_BANDA_PWM_TECHO not in claves


# ── Migración única ─────────────────────────────────────────────────────────

def test_0_3_se_conserva_tras_varias_cargas(tmp_path):
    ruta = _instalar(tmp_path, 0.3)
    for _ in range(3):
        ctx = _cargar(tmp_path)
        c = ctx.cycle_manager.cycles["134_instrumental"]
        assert c.get_param("esterilizacion", CLAVE) == 0.3
        assert not c.danado
        assert _correcciones(ctx) == {}
        _auditar(ctx, tmp_path)
    assert json.loads(ruta.read_text(encoding="utf-8"))["parameters"]["esterilizacion"][
        CLAVE]["value"] == 0.3
    # CRI-04 (tanda 35) reescribe el archivo una vez (marca migrado_cri) y deja .bak


def test_1_0_pasa_a_0_3_una_sola_vez(tmp_path):
    ruta = _instalar(tmp_path, 1.0)
    ctx = _cargar(tmp_path)
    c = ctx.cycle_manager.cycles["134_instrumental"]
    assert not c.danado
    assert c.get_param("esterilizacion", CLAVE) == 0.3
    # presion_add_esterilizacion no cambia (15 cumple P1 con 0,3)
    assert c.get_param("esterilizacion", "presion_add_esterilizacion") == 15.0
    assert _correcciones(ctx) == {CLAVE: (1.0, 0.3, "migración tanda 28 (M3)")}
    # aviso SIS-06, no bloqueante, con su unidad
    ctx._avisar_migraciones_correctivas()
    avisos = [i.valores for i in ctx.alarm_manager.activas() if i.definicion.codigo == SIS_06]
    assert len(avisos) == 1
    assert (avisos[0]["parametro"], avisos[0]["anterior"], avisos[0]["nuevo"],
            avisos[0]["unidad"]) == (CLAVE, "1", "0.3", "°C")
    assert avisos[0]["motivo"] == "migración tanda 28 (M3)"
    assert ctx.alarm_manager.has_blocking_alarm() is False
    # auditoría y archivo reescrito con la marca; .bak con el original
    db = _auditar(ctx, tmp_path)
    filas = {f["entidad"]: f for f in db.get_auditoria(evento="param_ciclo_cambio")}
    f = filas[f"134_instrumental/esterilizacion/{CLAVE}"]
    assert (f["valor_anterior"], f["valor_nuevo"]) == ("1.0", "0.3")
    assert f["detalle"]["origen"] == "migración tanda 28 (M3)" and f["usuario"] == "sistema"
    hoja = json.loads(ruta.read_text(encoding="utf-8"))["parameters"]["esterilizacion"][CLAVE]
    assert hoja["value"] == 0.3 and hoja[MARCA] is True
    bak = json.loads((ruta.parent / (ruta.name + ".bak")).read_text(encoding="utf-8"))
    assert bak["parameters"]["esterilizacion"][CLAVE]["value"] == 1.0
    # el siguiente arranque ya no migra
    ctx2 = _cargar(tmp_path)
    assert _correcciones(ctx2) == {}
    # un 1,0 fijado después a mano (archivo con la marca) se conserva
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    datos["parameters"]["esterilizacion"][CLAVE]["value"] = 1.0
    datos["parameters"]["esterilizacion"]["presion_add_esterilizacion"]["value"] = 15.0
    ruta.write_text(json.dumps(datos, indent=4, ensure_ascii=False), encoding="utf-8")
    for _ in range(2):
        ctx3 = _cargar(tmp_path)
        assert ctx3.cycle_manager.cycles["134_instrumental"].get_param(
            "esterilizacion", CLAVE) == 1.0
        assert _correcciones(ctx3) == {}


@pytest.mark.parametrize("valor", [0.7, 0.0, 2.0])
def test_otro_valor_no_se_toca(tmp_path, valor):
    ruta = _instalar(tmp_path, valor)
    antes = ruta.read_text(encoding="utf-8")
    ctx = _cargar(tmp_path)
    c = ctx.cycle_manager.cycles["134_instrumental"]
    assert c.get_param("esterilizacion", CLAVE) == valor
    corr = _correcciones(ctx)
    assert CLAVE not in corr
    _auditar(ctx, tmp_path)
    assert json.loads(ruta.read_text(encoding="utf-8"))["parameters"]["esterilizacion"][
        CLAVE]["value"] == valor
    # con CRI-04 el archivo se reescribe siempre (marca migrado_cri); el valor no cambia


def test_m3_no_pasa_por_la_salvaguarda_del_alivio(tmp_path):
    """Bajar la brecha reduce el mínimo de P1: la salvaguarda de P2 (que
    impide SUBIR presion_add) no aplica a M3."""
    class _Config:
        def get(self, clave, default=None):
            return {"presion_fondo_escala": 400, "presion_suministro_vapor": 300,
                    "presion_alivio_camara": 385, "presion_alivio_chaqueta": 340}.get(clave, default)
    cp.fijar_config_equipo(_Config())
    destino = _instalar(tmp_path, 1.0)
    datos = json.loads(destino.read_text(encoding="utf-8"))
    datos["parameters"]["esterilizacion"]["presion_add_esterilizacion"]["value"] = 9.0
    datos["parameters"]["globals"]["presion_chaqueta"]["value"] = 250
    destino.write_text(json.dumps(datos, indent=4, ensure_ascii=False), encoding="utf-8")
    ctx = _cargar(tmp_path)
    c = ctx.cycle_manager.cycles["134_instrumental"]
    assert c.get_param("esterilizacion", CLAVE) == 0.3
    assert c.get_param("esterilizacion", "presion_add_esterilizacion") == 9.0
    assert _correcciones(ctx) == {CLAVE: (1.0, 0.3, "migración tanda 28 (M3)")}
    assert ctx.cycle_manager.migraciones_no_aplicadas() == []


def test_valor_no_numerico_ni_se_toca_ni_se_marca():
    p = _datos("factory/instrumental_134.json")["parameters"]
    p["esterilizacion"][CLAVE]["value"] = "1.0"
    corr = []
    migrar_parametros(p, corr, [], recuperacion=True)
    assert corr == [] and MARCA not in p["esterilizacion"][CLAVE]


def test_copia_e_instantanea_no_migran_m3():
    """La instantánea de un ciclo interrumpido conserva los valores con los
    que corrió (como P2)."""
    p = _datos("factory/instrumental_134.json")["parameters"]
    p["esterilizacion"][CLAVE]["value"] = 1.0
    c = Cycle("p", "P", p, 2)
    assert c.get_param("esterilizacion", CLAVE) == 1.0
    assert c.copia().get_param("esterilizacion", CLAVE) == 1.0
    d = Cycle.desde_instantanea(c.instantanea())
    assert d.get_param("esterilizacion", CLAVE) == 1.0


# ── Escenario simulado de 134 °C (planta de A14-diag) ───────────────────────

# Diagnóstico (antes de A14, modo chaqueta, programa vigente con brecha 1,0):
# FALLO CIC-16 con 6 aislamientos y sobreimpulso 1,21 K. Umbral fijo, por
# debajo de ese valor con margen.
SOBREIMPULSO_MAX_K = 0.8


def test_simulado_134_chaqueta_m1_m2_m3_sin_aislamientos(monkeypatch):
    import logging
    from tests.helpers.planta_vapor import programa_134, simular
    logging.disable(logging.CRITICAL)
    try:
        programa = programa_134()
        assert programa.get_param("esterilizacion", CLAVE) == 0.3
        res = simular("chaqueta", programa, monkeypatch=monkeypatch)
    finally:
        logging.disable(logging.NOTSET)
    assert res.resultado == "COMPLETADO", (res.resultado, res.motivo, res.alarma)
    assert res.aislamientos == 0
    assert res.sobreimpulso_k is not None and res.sobreimpulso_k < SOBREIMPULSO_MAX_K
    assert res.sobreimpulso_k < 1.21
    # la presión no llega al techo de control
    assert res.p_max_ester < res.p_control_max - cp.MARGEN_BANDA_TECHO_KPA
    # la temperatura de exposición no baja del umbral de falla
    assert res.t_min_ester >= 134.0 - 0.1


def test_simulado_134_camara_sin_regresion(monkeypatch):
    import logging
    from tests.helpers.planta_vapor import programa_134, simular
    logging.disable(logging.CRITICAL)
    try:
        res = simular("camara", programa_134(), monkeypatch=monkeypatch)
    finally:
        logging.disable(logging.NOTSET)
    assert res.resultado == "COMPLETADO", (res.resultado, res.motivo, res.alarma)
    assert res.aislamientos == 0
    # diagnóstico en modo cámara (vigente): 1,30 K
    assert res.sobreimpulso_k < 1.30
    assert res.t_min_ester >= 134.0 - 0.1
