"""A12 (tanda 28): prevacío atascado entre el escape y el vacío.

- DECOMPRESION pasa a VACIO_BAJO con pres <= atm + presion_inicio_vacio (ya
  no con rango_presion_atm, el rango de cámara segura);
- tiempo límite timeout_descompresion → FALLO CIC-20 sin encender la bomba;
- parámetros nuevos en los 10 programas, migración con defecto y auditoría
  (sin SIS-06), validación al guardar y al cargar, textos es/en."""

import json
import shutil
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers import catalogo_parametros as cp
from autoclave.core.managers.cycle_manager import Cycle, CycleManager, migrar_parametros
from autoclave.state_machine.alarms.catalogo import CATALOGO, CIC_20, SIS_06
from autoclave.state_machine.cycle_phases import prevacio as prev
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.cycle_phases.prevacio import PrevacioFase

pytestmark = pytest.mark.req("A12")

RAIZ = Path(__file__).resolve().parents[1]
CICLOS = RAIZ / "src" / "autoclave" / "cycles"
ATM = 74.6


@pytest.fixture(autouse=True)
def _sin_config_equipo():
    cp.fijar_config_equipo(None)
    yield
    cp.fijar_config_equipo(None)


@pytest.fixture
def reloj(monkeypatch):
    ahora = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: ahora[0])
    return ahora


def _fase(params=None, rango_atm=5.0, pres=ATM, conteo=2):
    valores = {
        "conteo_pulso_a": conteo, "conteo_pulso_b": 0, "conteo_pulso_c": 0, "conteo_pulso_d": 0,
        "presion_baja_pulso_a": 15, "tiempo_adicional_bajo_a": 0,
        "presion_alta_pulso_a": 180, "tiempo_adicional_alto_a": 0,
        "timeout_bajo": 10, "timeout_alto": 10,
    }
    valores.update(params or {})
    estado = MagicMock()
    estado.sensores_pres = {"pres_camara": pres}
    estado.motivo_fallo = None
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda seccion, clave, default=None: valores.get(clave, default)
    config = MagicMock()
    config.get.side_effect = lambda clave, default=None: {
        "presion_admosferica": ATM, "rango_presion_atm": rango_atm}.get(clave, default)
    cap = MagicMock()
    cap.has_vacuum = True
    fase = PrevacioFase(estado, set_do, cycle, config, MagicMock(), cap)
    fase.reset()
    return fase, set_do, estado


# ── DECOMPRESION → VACIO_BAJO con presion_inicio_vacio ──────────────────────

def test_presion_estancada_en_atm_mas_6_con_rango_5_pasa_a_vacio(reloj):
    """El caso del equipo: el escape no baja de atm + 6 kPa; con rango 5 el
    pulso quedaba detenido. Con presion_inicio_vacio 10 pasa a vacío."""
    fase, set_do, estado = _fase({"presion_inicio_vacio": 10.0}, rango_atm=5.0, pres=ATM + 6)
    assert fase.update() is FaseResult.EN_CURSO
    assert fase._paso == "VACIO_BAJO"
    set_do.descompresion_rapida_off.assert_called()
    set_do.descompresion_rapida_on.assert_not_called()
    fase.update()
    set_do.bomba_vacio_on.assert_called()
    set_do.vacio_camara_on.assert_called()


def test_con_presion_inicio_vacio_5_sigue_escapando(reloj):
    fase, set_do, _ = _fase({"presion_inicio_vacio": 5.0}, rango_atm=5.0, pres=ATM + 6)
    for _ in range(5):
        assert fase.update() is FaseResult.EN_CURSO
    assert fase._paso == "DECOMPRESION"
    set_do.descompresion_rapida_on.assert_called()
    set_do.bomba_vacio_on.assert_not_called()


@pytest.mark.parametrize("rango_atm", [1.0, 10.0, 20.0])
def test_ya_no_depende_de_rango_presion_atm(reloj, rango_atm):
    fase, _, _ = _fase({"presion_inicio_vacio": 10.0}, rango_atm=rango_atm, pres=ATM + 10.5)
    fase.update()
    assert fase._paso == "DECOMPRESION"          # sobre atm + 10, con cualquier rango
    fase, _, _ = _fase({"presion_inicio_vacio": 10.0}, rango_atm=rango_atm, pres=ATM + 10.0)
    fase.update()
    assert fase._paso == "VACIO_BAJO"            # en el límite (<=)


def test_sin_el_parametro_usa_el_defecto_10(reloj):
    fase, _, _ = _fase({}, rango_atm=5.0, pres=ATM + 9.9)
    fase.update()
    assert fase._paso == "VACIO_BAJO"
    fase, _, _ = _fase({}, rango_atm=5.0, pres=ATM + 10.1)
    fase.update()
    assert fase._paso == "DECOMPRESION"


@pytest.mark.parametrize("valor,esperado", [(-5, 2.0), (0, 2.0), (45, 15.0), ("10", 10.0),
                                            (None, 10.0), (True, 10.0)])
def test_presion_inicio_vacio_recortada(valor, esperado):
    fase, _, _ = _fase({"presion_inicio_vacio": valor})
    assert fase._presion_inicio_vacio() == esperado


# ── timeout_descompresion → FALLO CIC-20 ────────────────────────────────────

def test_timeout_descompresion_da_fallo_cic20_sin_bomba(reloj):
    fase, set_do, estado = _fase({"presion_inicio_vacio": 10.0, "timeout_descompresion": 5},
                                 pres=ATM + 20)
    assert fase.update() is FaseResult.EN_CURSO
    reloj[0] += 5 * 60                           # justo en el límite: sigue
    assert fase.update() is FaseResult.EN_CURSO
    reloj[0] += 0.5
    assert fase.update() is FaseResult.FALLO
    codigo, valores = fase.alarma_fallo
    assert codigo == CIC_20
    assert valores["maximo"] == pytest.approx(ATM + 10)
    assert valores["margen"] == "10" and valores["minutos"] == "5"
    assert valores["pulso"] == "A 1/2"
    assert estado.motivo_fallo and "prevacío" in estado.motivo_fallo
    set_do.bomba_vacio_on.assert_not_called()
    set_do.vacio_camara_on.assert_not_called()
    # al fallar, el escape rápido (salida de la fase) queda apagado
    assert set_do.mock_calls[-1] == ("descompresion_rapida_off", (), {})


def test_timeout_corre_sin_lectura_de_presion(reloj):
    fase, set_do, estado = _fase({"timeout_descompresion": 1}, pres=None)
    assert fase.update() is FaseResult.EN_CURSO
    reloj[0] += 61
    assert fase.update() is FaseResult.FALLO
    assert fase.alarma_fallo[0] == CIC_20
    set_do.bomba_vacio_on.assert_not_called()


def test_timeout_se_reinicia_en_cada_pulso(reloj):
    fase, set_do, estado = _fase({"timeout_descompresion": 5, "presion_inicio_vacio": 10.0},
                                 pres=ATM + 20)
    fase.update()
    reloj[0] += 4 * 60
    estado.sensores_pres["pres_camara"] = ATM            # baja: pasa a vacío
    fase.update()
    assert fase._paso == "VACIO_BAJO"
    # completa el pulso 1
    estado.sensores_pres["pres_camara"] = 10
    fase.update()                                         # HOLD_BAJO
    fase.update()                                         # APAGANDO_VACIO
    reloj[0] += prev._STAGGER_APAGADO_VACIO + 0.01
    fase.update()                                         # VAPOR_ALTO
    estado.sensores_pres["pres_camara"] = 180
    fase.update()                                         # HOLD_ALTO
    assert fase.update() is FaseResult.EN_CURSO           # pulso 2 → DECOMPRESION
    assert fase._paso == "DECOMPRESION" and fase._pulso_actual == 2
    estado.sensores_pres["pres_camara"] = ATM + 20
    fase.update()                                         # arma el límite del pulso 2
    reloj[0] += 4.9 * 60                                  # 8,9 min desde el pulso 1
    assert fase.update() is FaseResult.EN_CURSO
    reloj[0] += 0.2 * 60
    assert fase.update() is FaseResult.FALLO
    assert fase.alarma_fallo[1]["pulso"] == "A 2/2"


@pytest.mark.parametrize("valor,esperado", [(0, 1.0), (1, 1.0), (45, 30.0), (None, 5.0),
                                            ("5", 5.0)])
def test_timeout_descompresion_recortado(valor, esperado):
    fase, _, _ = _fase({"timeout_descompresion": valor})
    assert fase._timeout_descompresion_min() == esperado


def test_secuencia_escalonado_y_timeouts_existentes_sin_cambio():
    assert prev._STAGGER_APAGADO_VACIO == 0.15
    assert (prev._PASO_DECOMPRESION, prev._PASO_VACIO_BAJO, prev._PASO_HOLD_BAJO,
            prev._PASO_APAGANDO_VACIO, prev._PASO_VAPOR_ALTO, prev._PASO_HOLD_ALTO) == (
        "DECOMPRESION", "VACIO_BAJO", "HOLD_BAJO", "APAGANDO_VACIO", "VAPOR_ALTO", "HOLD_ALTO")


# ── CIC-20: catálogo, registro y textos ─────────────────────────────────────

def test_cic20_en_el_catalogo_y_en_las_propias_de_fase():
    from autoclave.state_machine.alarms.catalogo import Nivel
    from autoclave.state_machine.states import ciclo
    d = CATALOGO[CIC_20]
    assert d.nivel is Nivel.ALARMA and d.bloquea_inicio is True
    assert CIC_20 in ciclo._ALARMAS_PROPIAS_FASE


def test_ciclo_registra_cic20_de_la_fase():
    from types import SimpleNamespace
    from autoclave.state_machine.states.ciclo import CicloState
    estado = SimpleNamespace(motivo_fallo=None, codigo_fallo="", valores_fallo={})
    cs = CicloState.__new__(CicloState)
    cs.estado = estado
    vistos = []
    cs._registrar_fallo = lambda codigo, origen=None, **v: vistos.append((codigo, origen, v))
    fase = SimpleNamespace(alarma_fallo=(CIC_20, {"maximo": 84.6, "margen": 10.0,
                                                  "minutos": "5", "pulso": "A 1/4"}))
    cs._registrar_fallo_de_fase("PRE_VACIO", fase)
    [(codigo, _, valores)] = vistos
    assert codigo == CIC_20 and valores["pulso"] == "A 1/4"


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_cic20_textos(idioma):
    from autoclave import i18n
    valores = {"maximo": 84.6, "margen": "10", "minutos": "5", "pulso": "A 1/4"}
    for campo in ("titulo", "plantilla", "accion"):
        clave = f"alarmas.{CIC_20}.{campo}"
        if not i18n.existe(clave, idioma):
            pytest.skip("estructura de claves de alarmas distinta")
    texto = i18n.t(f"alarmas.{CIC_20}.plantilla", idioma).format(**valores)
    assert "84.6" in texto and "A 1/4" in texto


# ── Programas, catálogo y migración ─────────────────────────────────────────

@pytest.mark.parametrize("ruta", sorted(str(p) for p in CICLOS.glob("*/*.json")),
                         ids=lambda r: "/".join(Path(r).parts[-2:]))
def test_programas_del_repo_con_los_parametros(ruta):
    p = json.loads(Path(ruta).read_text(encoding="utf-8"))["parameters"]
    h = p["prevacio"]["presion_inicio_vacio"]
    assert (h["value"], h["type"], h["unit"], h["clase"], h["min"], h["max"]) == \
        (10.0, "float", "kPa", "diferencia", 2, 15)
    h = p["prevacio"]["timeout_descompresion"]
    assert (h["value"], h["type"], h["unit"], h["min"], h["max"]) == (5, "int", "min", 1, 30)
    assert cp.errores_programa(p) == []
    agregadas = []
    migrar_parametros(p, [], [], recuperacion=True, agregadas=agregadas)
    # CRI-04 (tanda 35): la marca de significado de la brecha es la unica agregada
    assert [a for a in agregadas if a["parametro"] != "brecha_segura_presion"] == []


def test_catalogo_rangos():
    hoja = {"type": "float"}
    assert cp.coercionar(hoja, "prevacio", ["presion_inicio_vacio"], 2) == 2
    assert cp.coercionar(hoja, "prevacio", ["presion_inicio_vacio"], 15) == 15
    for malo in (1.9, 15.1, True, "10"):
        with pytest.raises(ValueError):
            cp.coercionar(hoja, "prevacio", ["presion_inicio_vacio"], malo)
    hoja = {"type": "int"}
    assert cp.coercionar(hoja, "prevacio", ["timeout_descompresion"], 1) == 1
    assert cp.coercionar(hoja, "prevacio", ["timeout_descompresion"], 30) == 30
    for malo in (0, 31, 2.5):
        with pytest.raises(ValueError):
            cp.coercionar(hoja, "prevacio", ["timeout_descompresion"], malo)


def _datos(nombre="factory/instrumental_134.json"):
    return json.loads((CICLOS / nombre).read_text(encoding="utf-8"))


@pytest.mark.parametrize("clave,valor", [("presion_inicio_vacio", 15.1),
                                         ("timeout_descompresion", 0)])
def test_validacion_al_cargar_y_al_guardar(clave, valor):
    p = _datos()["parameters"]
    p["prevacio"][clave]["value"] = valor
    assert any(e.startswith(f"prevacio.{clave}") for e in cp.errores_programa(p))
    c = Cycle("p", "P", _datos()["parameters"], 2)
    with pytest.raises(ValueError):
        c.set_param("prevacio", [clave], valor)
    assert c.get_param("prevacio", clave) == (10.0 if clave == "presion_inicio_vacio" else 5)


def test_migracion_agrega_los_defectos():
    p = _datos()["parameters"]
    del p["prevacio"]["presion_inicio_vacio"]
    del p["prevacio"]["timeout_descompresion"]
    agregadas, corr = [], []
    assert migrar_parametros(p, corr, agregadas=agregadas) is True
    assert corr == []
    assert p["prevacio"]["presion_inicio_vacio"]["value"] == 10.0
    assert p["prevacio"]["timeout_descompresion"]["value"] == 5
    assert {(a["parametro"], a["anterior"], a["nuevo"], a["origen"]) for a in agregadas} == {
        ("presion_inicio_vacio", None, 10.0, "migración tanda 28 (A12)"),
        ("timeout_descompresion", None, 5, "migración tanda 28 (A12)")}
    assert cp.errores_programa(p) == []
    # idempotente; un valor existente nunca se toca
    p["prevacio"]["presion_inicio_vacio"]["value"] = 3.0
    otra = []
    migrar_parametros(p, agregadas=otra)
    assert otra == [] and p["prevacio"]["presion_inicio_vacio"]["value"] == 3.0


def test_programa_sin_prevacio_no_recibe_nada():
    p = {"esterilizacion": {}}
    agregadas = []
    migrar_parametros(p, agregadas=agregadas)
    assert "prevacio" not in p and agregadas == []


def test_migracion_al_cargar_con_auditoria_sin_sis06_y_bak(tmp_path):
    from autoclave.backend.context import BackendContext
    from autoclave.services.domain.logging.db_manager import DbManager
    destino = tmp_path / "cycles"
    shutil.copytree(CICLOS / "factory", destino / "factory")
    (destino / "user").mkdir()
    datos = _datos("user/instrumental_134.json")
    del datos["parameters"]["prevacio"]["presion_inicio_vacio"]
    del datos["parameters"]["prevacio"]["timeout_descompresion"]
    ruta = destino / "user" / "instrumental_134.json"
    ruta.write_text(json.dumps(datos, indent=4, ensure_ascii=False), encoding="utf-8")

    def cargar():
        ctx = BackendContext()
        cm = CycleManager()
        cm.raiz = str(tmp_path)
        cm.load_all_cycles()
        ctx.cycle_manager = cm
        return ctx

    ctx = cargar()
    c = ctx.cycle_manager.cycles["134_instrumental"]
    assert not c.danado
    assert c.get_param("prevacio", "presion_inicio_vacio") == 10.0
    assert c.get_param("prevacio", "timeout_descompresion") == 5
    assert {m["parametro"] for _, m in ctx.cycle_manager.migraciones_agregadas()} == {
        "presion_inicio_vacio", "timeout_descompresion", "brecha_segura_presion"}   # + CRI-04
    assert ctx.cycle_manager.migraciones_correctivas() == []
    # sin aviso SIS-06
    ctx._avisar_migraciones_correctivas()
    assert not [i for i in ctx.alarm_manager.activas() if i.definicion.codigo == SIS_06]
    # auditoría y archivo reescrito con .bak
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.auditar_migraciones_correctivas()
    filas = {f["entidad"]: f for f in ctx.db.get_auditoria(evento="param_ciclo_cambio")}
    f = filas["134_instrumental/prevacio/presion_inicio_vacio"]
    assert f["valor_anterior"] is None and f["valor_nuevo"] == "10.0"
    assert f["detalle"]["origen"] == "migración tanda 28 (A12)"
    assert f["detalle"]["causa"] == "migracion_parametro_nuevo" and f["usuario"] == "sistema"
    assert filas["134_instrumental/prevacio/timeout_descompresion"]["valor_nuevo"] == "5"
    escrito = json.loads(ruta.read_text(encoding="utf-8"))["parameters"]["prevacio"]
    assert escrito["presion_inicio_vacio"]["value"] == 10.0
    assert escrito["timeout_descompresion"]["value"] == 5
    bak = json.loads((ruta.parent / (ruta.name + ".bak")).read_text(encoding="utf-8"))
    assert "presion_inicio_vacio" not in bak["parameters"]["prevacio"]
    # un reintento no duplica y el siguiente arranque ya no migra
    ctx.auditar_migraciones_correctivas()
    assert len([f for f in ctx.db.get_auditoria(evento="param_ciclo_cambio")
                if f["entidad"].startswith("134_instrumental/prevacio/")]) == 2
    # CRI-04: los programas de fabrica no se reescriben y repiten su fila de brecha;
    # el programa de usuario migrado ya no
    assert [m for c, m in cargar().cycle_manager.migraciones_agregadas()
            if c.source == "user" or m["parametro"] != "brecha_segura_presion"] == []


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_textos_de_los_parametros(idioma):
    from autoclave import i18n
    for clave in ("presion_inicio_vacio", "timeout_descompresion"):
        assert i18n.existe(f"parametros.prevacio.{clave}", idioma)
        assert i18n.existe(f"parametros_desc.prevacio.{clave}", idioma)
