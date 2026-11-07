"""Tanda 29: T29-03 (presión de fin de descompresión) y T29-05 (carga sólida
solo con descompresión 0 a 3).

T29-03 (decisión de Cristian): DESCOMPRESION termina con pres <= atm +
descompresion.presion_fin_descompresion (kPa, diferencia, defecto 10, rango
2–20) en los modos 1 a 5, sólidos y líquidos; el modo 0 y los timeouts no
cambian. Migración al cargar como A12 (auditoría y .bak).

T29-05: con tipo_carga sólido solo los modos 0 a 3 (rechazo al guardar con
MODO_NO_PERMITIDO_SOLIDO); al cargar, un sólido con 4 o 5 pasa al modo de
fábrica si es sólido y válido, si no al 1 (auditoría, SIS-06 y .bak).
"""

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers import catalogo_parametros as cp
from autoclave.core.managers.cycle_manager import Cycle, CycleManager, migrar_parametros
from autoclave.state_machine.alarms.catalogo import SIS_06
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.cycle_phases.descompresion import DescompresionFase

RAIZ = Path(__file__).resolve().parents[1]
CICLOS = RAIZ / "src" / "autoclave" / "cycles"
ATM = 75.0


@pytest.fixture(autouse=True)
def _sin_config_equipo():
    cp.fijar_config_equipo(None)
    yield
    cp.fijar_config_equipo(None)


# ── Fase: umbral de fin ─────────────────────────────────────────────────────

def _fase(modo, pres, margen=10.0, rango_atm=5.0, tipo="solido"):
    estado = MagicMock()
    estado.sensores_pres = {"pres_camara": pres}
    estado.sensores_temp = {"temp_camara": 60.0}
    config = MagicMock()
    valores = {"presion_admosferica": ATM, "rango_presion_atm": rango_atm}
    config.get.side_effect = lambda k, *a: valores.get(k)
    params = {("descompresion", "modo"): modo,
              ("descompresion", "tiempo_pre_despresurizacion"): 0,
              ("descompresion", "modo_3", "presion_cambio"): 150,
              ("globals", "tipo_carga"): tipo}
    for m in (1, 2, 3, 4, 5):
        params[("descompresion", f"modo_{m}", "timeout")] = 30
    if margen is not None:
        params[("descompresion", "presion_fin_descompresion")] = margen
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda *k, default=None: params.get(k, default)
    fase = DescompresionFase(estado, MagicMock(), cycle, config, alarm_manager=None, cap=MagicMock())
    fase.reset()
    return fase, estado


def _a_descompresion_final(fase, modo):
    fase.update()                                   # entra al modo
    if modo == 3:
        fase._sub_etapa = "rapida"
    elif modo in (4, 5):
        fase._sub_etapa = "descompresion"


@pytest.mark.parametrize("modo", [1, 2, 3, 4, 5])
@pytest.mark.parametrize("tipo", ["solido", "liquido"])
def test_modos_1_a_5_terminan_con_atm_mas_presion_fin(modo, tipo):
    # atm + 9 kPa: sobre el rango_presion_atm (5) pero bajo el margen (10)
    fase, _ = _fase(modo, ATM + 9.0, tipo=tipo)
    _a_descompresion_final(fase, modo)
    assert fase.update() == FaseResult.COMPLETADO


@pytest.mark.parametrize("modo", [1, 2, 3, 4, 5])
def test_sobre_el_margen_sigue_en_curso(modo):
    fase, _ = _fase(modo, ATM + 10.5)
    _a_descompresion_final(fase, modo)
    assert fase.update() == FaseResult.EN_CURSO


def test_modo_0_no_cambia_sigue_con_rango_presion_atm():
    fase, _ = _fase(0, ATM + 9.0)
    fase.update()
    assert fase.update() == FaseResult.EN_CURSO
    fase, _ = _fase(0, ATM + 4.0)
    fase.update()
    assert fase.update() == FaseResult.COMPLETADO


@pytest.mark.parametrize("margen", [None, 0, -3, True, float("nan"), "10"])
def test_sin_parametro_valido_rige_el_criterio_anterior(margen):
    fase, _ = _fase(1, ATM + 9.0, margen=margen)
    fase.update()
    assert fase.update() == FaseResult.EN_CURSO
    fase, _ = _fase(1, ATM + 4.0, margen=margen)
    fase.update()
    assert fase.update() == FaseResult.COMPLETADO


def test_sin_lectura_no_termina():
    fase, estado = _fase(1, None)
    fase.update()
    assert fase.update() == FaseResult.EN_CURSO


# ── Catálogo, programas y migración T29-03 ──────────────────────────────────

def test_catalogo_rango_2_a_20():
    hoja = {"type": "float"}
    assert cp.coercionar(hoja, "descompresion", ["presion_fin_descompresion"], 2) == 2
    assert cp.coercionar(hoja, "descompresion", ["presion_fin_descompresion"], 20) == 20
    for malo in (1.9, 20.1, True, "10"):
        with pytest.raises(ValueError):
            cp.coercionar(hoja, "descompresion", ["presion_fin_descompresion"], malo)


@pytest.mark.parametrize("ruta", sorted(str(p) for p in CICLOS.glob("*/*.json")),
                         ids=lambda r: "/".join(Path(r).parts[-2:]))
def test_programas_del_repo_con_el_parametro_y_validos(ruta):
    p = json.loads(Path(ruta).read_text(encoding="utf-8"))["parameters"]
    h = p["descompresion"]["presion_fin_descompresion"]
    assert (h["value"], h["type"], h["unit"], h["clase"], h["min"], h["max"]) == \
        (10.0, "float", "kPa", "diferencia", 2, 20)
    assert cp.errores_programa(p) == []
    agregadas, corr = [], []
    migrar_parametros(p, corr, [], recuperacion=True, agregadas=agregadas)
    assert agregadas == [] and corr == []


def _datos(nombre="factory/instrumental_134.json"):
    return json.loads((CICLOS / nombre).read_text(encoding="utf-8"))


def test_migracion_agrega_el_defecto_tras_la_espera():
    p = _datos()["parameters"]
    del p["descompresion"]["presion_fin_descompresion"]
    agregadas, corr = [], []
    assert migrar_parametros(p, corr, agregadas=agregadas) is True
    assert corr == []
    assert [(a["fase"], a["parametro"], a["anterior"], a["nuevo"], a["origen"]) for a in agregadas] == [
        ("descompresion", "presion_fin_descompresion", None, 10.0, "migración tanda 29 (T29-03)")]
    claves = list(p["descompresion"])
    assert claves[claves.index("tiempo_pre_despresurizacion") + 1] == "presion_fin_descompresion"
    assert cp.errores_programa(p) == []
    p["descompresion"]["presion_fin_descompresion"]["value"] = 4.0
    otra = []
    migrar_parametros(p, agregadas=otra)
    assert otra == [] and p["descompresion"]["presion_fin_descompresion"]["value"] == 4.0


def test_validacion_al_guardar_fuera_de_rango():
    c = Cycle("p", "P", _datos()["parameters"], 2)
    with pytest.raises(ValueError):
        c.set_param("descompresion", ["presion_fin_descompresion"], 25)
    assert c.get_param("descompresion", "presion_fin_descompresion") == 10.0
    assert c.set_param("descompresion", ["presion_fin_descompresion"], 20) == 20


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_textos(idioma):
    from autoclave import i18n
    assert i18n.existe("parametros.descompresion.presion_fin_descompresion", idioma)
    assert i18n.existe("parametros_desc.descompresion.presion_fin_descompresion", idioma)
    assert i18n.existe("opciones.err_modo_solido", idioma)


# ── T29-05: sólido solo con modos 0 a 3 ─────────────────────────────────────

@pytest.mark.parametrize("modo", [4, 5])
def test_guardar_modo_4_o_5_en_solido_se_rechaza(modo):
    c = Cycle("p", "P", _datos()["parameters"], 2)
    with pytest.raises(cp.ErrorCoherencia) as e:
        c.set_param("descompresion", ["modo"], modo)
    assert e.value.codigo == "MODO_NO_PERMITIDO_SOLIDO"
    assert c.get_param("descompresion", "modo") == 1


def test_arrastre_a_solido_ignora_un_defecto_4_o_5():
    c = Cycle("l", "L", _datos("factory/liquidos.json")["parameters"], 4)
    assert c.arrastres_tipo_carga("solido", modo_solido=4) == [("descompresion", ["modo"], 1)]
    assert c.arrastres_tipo_carga("solido", modo_solido=3) == [("descompresion", ["modo"], 3)]


@pytest.mark.parametrize("modo_fabrica,esperado", [(2, 2), (None, 1), (4, 1), (True, 1)])
def test_migracion_solido_4_al_modo_de_fabrica_o_1(modo_fabrica, esperado):
    p = _datos()["parameters"]
    p["descompresion"]["modo"]["value"] = 5
    corr = []
    assert migrar_parametros(p, corr, [], recuperacion=True, modo_fabrica=modo_fabrica) is True
    assert p["descompresion"]["modo"]["value"] == esperado
    assert corr == [{"fase": "descompresion", "parametro": "modo", "anterior": 5, "nuevo": esperado,
                     "origen": "migración tanda 29 (T29-05)", "unidad": ""}]
    assert cp.errores_programa(p) == []


def test_migracion_no_toca_liquidos_ni_sin_recuperacion():
    p = _datos("factory/liquidos.json")["parameters"]
    corr = []
    migrar_parametros(p, corr, [], recuperacion=True)
    assert p["descompresion"]["modo"]["value"] == 4 and corr == []
    p = _datos()["parameters"]
    p["descompresion"]["modo"]["value"] = 4
    migrar_parametros(p, corr, [])          # copia / instantánea: sin migrar
    assert p["descompresion"]["modo"]["value"] == 4 and corr == []


def test_migracion_al_cargar_bowie_dick_con_auditoria_sis06_y_bak(tmp_path):
    from autoclave.backend.context import BackendContext
    from autoclave.services.domain.logging.db_manager import DbManager
    destino = tmp_path / "cycles"
    shutil.copytree(CICLOS / "factory", destino / "factory")
    (destino / "user").mkdir()
    datos = _datos("user/bowe_dick.json")
    datos["parameters"]["descompresion"]["modo"]["value"] = 4     # el caso del equipo
    ruta = destino / "user" / "bowe_dick.json"
    ruta.write_text(json.dumps(datos, indent=4, ensure_ascii=False), encoding="utf-8")

    def cargar():
        ctx = BackendContext()
        cm = CycleManager()
        cm.raiz = str(tmp_path)
        cm.load_all_cycles()
        ctx.cycle_manager = cm
        return ctx

    ctx = cargar()
    c = ctx.cycle_manager.cycles[datos["cycle_id"]]
    assert not c.danado
    fabrica = ctx.cycle_manager.fabrica[c.number].get_param("descompresion", "modo")
    assert fabrica in cp.MODOS_SOLIDO
    assert c.get_param("descompresion", "modo") == fabrica
    ctx._avisar_migraciones_correctivas()
    assert [i for i in ctx.alarm_manager.activas() if i.definicion.codigo == SIS_06]
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.auditar_migraciones_correctivas()
    filas = {f["entidad"]: f for f in ctx.db.get_auditoria(evento="param_ciclo_cambio")}
    f = filas[f"{c.id}/descompresion/modo"]
    assert f["valor_anterior"] == "4" and f["valor_nuevo"] == str(fabrica)
    assert f["detalle"]["origen"] == "migración tanda 29 (T29-05)"
    escrito = json.loads(ruta.read_text(encoding="utf-8"))["parameters"]["descompresion"]
    assert escrito["modo"]["value"] == fabrica
    bak = json.loads((ruta.parent / (ruta.name + ".bak")).read_text(encoding="utf-8"))
    assert bak["parameters"]["descompresion"]["modo"]["value"] == 4
    assert cargar().cycle_manager.migraciones_correctivas() == []


def test_migracion_no_toca_programa_sin_tipo_carga():
    """Revisión T29 (M1): sin globals.tipo_carga se trata como líquida (SAF-03)."""
    p = _datos()["parameters"]
    p["descompresion"]["modo"]["value"] = 4
    p["globals"].pop("tipo_carga", None)
    corr = []
    migrar_parametros(p, corr, [], recuperacion=True)
    assert p["descompresion"]["modo"]["value"] == 4 and corr == []
