"""Tanda 16, s4 (PROGRAMAS Y LÍMITES).

- P1 (D-14.1): coherencia de la salida de RECUPERACION con el techo de control.
- Programas de fábrica de 134 °C con presion_add_esterilizacion = 15.
- P2 (D-14.2) y su extensión (V-04): migración al cargar con auditoría, SIS-06
  y .bak, y la salvaguarda del alivio de chaqueta.
- Parámetros de programa nuevos (histeresis_cierre_camara, max_reinicios_exposicion).
- DEU-01: límites de presión desde Parámetros del equipo.
- PRG-01 (D-PRG-1): roles sobre sondas no activas en el perfil de instalación."""

import glob
import json
import shutil
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers import catalogo_parametros as cp
from autoclave.core.managers.cycle_manager import Cycle, CycleManager, migrar_parametros
from autoclave.core.runtime import sensores_ciclo as sc
from autoclave.core.runtime.steam import p_saturacion_kpa, t_saturacion_c
from autoclave.installation.equipment import EquipmentClass
from autoclave.state_machine.alarms.catalogo import SIS_06

pytestmark = pytest.mark.req("T16-S4")

RAIZ = Path(__file__).resolve().parents[1]
CICLOS = RAIZ / "src" / "autoclave" / "cycles"


@pytest.fixture(autouse=True)
def _sin_config_equipo():
    cp.fijar_config_equipo(None)
    yield
    cp.fijar_config_equipo(None)


class _Config:
    """Doble mínimo del ConfigManager (solo get)."""

    def __init__(self, **valores):
        self.valores = {"presion_fondo_escala": 400, "presion_suministro_vapor": 350,
                        "presion_alivio_camara": 385, "presion_alivio_chaqueta": 385, **valores}

    def get(self, clave, default=None):
        return self.valores.get(clave, default)


def _datos(nombre):
    return json.loads((CICLOS / nombre).read_text(encoding="utf-8"))


def _params(nombre="factory/instrumental_134.json", **valores):
    p = _datos(nombre)["parameters"]
    for ruta, valor in valores.items():
        fase, clave = ruta.split("__")
        p[fase][clave]["value"] = valor
    return p


# ── P1 (D-14.1) ──────────────────────────────────────────────────────────────

def test_histeresis_del_catalogo_coincide_con_la_de_esterilizacion():
    from autoclave.state_machine.cycle_phases import esterilizacion
    assert cp.HIST_SALIDA_RECUPERACION_K == esterilizacion._HIST_RECUP_TEMP_K
    assert cp.MARGEN_COHERENCIA_RECUPERACION_K == 0.3


@pytest.mark.parametrize("t_est,minimo", [(121.0, 10.5), (134.0, 14.5)])
def test_minimo_de_p1_con_brecha_1(t_est, minimo):
    m = cp.presion_add_minima_recuperacion(t_est, 1.0)
    assert m == pytest.approx(minimo, abs=0.06)
    assert m == pytest.approx(p_saturacion_kpa(t_est + 1.6) - p_saturacion_kpa(t_est))
    # forma con Tsat de la regla: en el mínimo, Tsat(techo) = T_est + brecha + 0,3 + 0,3
    assert t_saturacion_c(p_saturacion_kpa(t_est) + m) == pytest.approx(t_est + 1.6, abs=1e-6)


@pytest.mark.parametrize("t_est,add,mostrado", [(134.0, 11.0, 14.6), (134.0, 9.0, 14.6),
                                                (121.0, 9.0, 10.6)])
def test_p1_rechaza_y_da_el_minimo(t_est, add, mostrado):
    nombre = "factory/instrumental_121.json" if t_est == 121.0 else "factory/instrumental_134.json"
    p = _params(nombre, esterilizacion__presion_add_esterilizacion=add)
    errores = cp.errores_coherencia(p)
    assert len(errores) == 1 and errores[0].startswith("Coherencia de recuperación")
    assert f"al menos {mostrado:.1f} kPa" in errores[0]
    assert cp.codigo_coherencia(errores) == cp.CODIGO_COHERENCIA_RECUPERACION
    assert cp.valor_limite(p) == pytest.approx(mostrado)
    # el mínimo mostrado sí se acepta
    p["esterilizacion"]["presion_add_esterilizacion"]["value"] = mostrado
    assert cp.errores_coherencia(p) == []


@pytest.mark.parametrize("t_est,add", [(121.0, 11.0), (134.0, 15.0), (134.5, 15.0)])
def test_p1_acepta(t_est, add):
    p = _params(esterilizacion__presion_add_esterilizacion=add,
                esterilizacion__temperatura_esterilizacion=t_est,
                calentamiento__temperatura_calentamiento=t_est)
    assert cp.errores_programa(p) == []


def test_p1_aplica_a_carga_liquida():
    p = _params("factory/liquidos.json", esterilizacion__presion_add_esterilizacion=9.0)
    assert any(e.startswith("Coherencia de recuperación") for e in cp.errores_coherencia(p))


@pytest.mark.parametrize("valor", [None, "1.0", True, float("nan")])
def test_p1_no_evalua_valores_ausentes_o_no_numericos(valor):
    p = _params(esterilizacion__presion_add_esterilizacion=9.0)
    if valor is None:
        del p["esterilizacion"]["brecha_segura_temperatura"]
    else:
        p["esterilizacion"]["brecha_segura_temperatura"]["value"] = valor
    assert cp.errores_recuperacion(p) == []


def test_set_param_rechaza_p1_y_no_cambia_nada():
    c = Cycle("p", "P", _params(), 2)
    with pytest.raises(cp.ErrorCoherencia) as e:
        c.set_param("esterilizacion", ["presion_add_esterilizacion"], 12.0)
    assert e.value.codigo == cp.CODIGO_COHERENCIA_RECUPERACION
    assert e.value.valor == pytest.approx(14.6)
    assert c.get_param("esterilizacion", "presion_add_esterilizacion") == 15.0
    # subir la brecha también exige más presion_add
    with pytest.raises(cp.ErrorCoherencia):
        c.set_param("esterilizacion", ["brecha_segura_temperatura"], 1.5)


# ── Programas del repositorio ───────────────────────────────────────────────

@pytest.mark.parametrize("nombre", ["factory/bowe_dick.json", "factory/instrumental_134.json",
                                    "user/bowe_dick.json", "user/instrumental_134.json"])
def test_programas_de_134_con_15_y_consigna_bajo_el_alivio(nombre):
    p = _datos(nombre)["parameters"]
    assert p["esterilizacion"]["presion_add_esterilizacion"]["value"] == 15.0
    consigna = cp.consigna_chaqueta_programa(p)
    assert consigna + cp.BANDA_CHAQUETA_KPA < cp.PRESION_ALIVIO_CHAQUETA
    if p["esterilizacion"]["temperatura_esterilizacion"]["value"] == 134.0:
        assert consigna + cp.BANDA_CHAQUETA_KPA == pytest.approx(344.2, abs=0.1)


@pytest.mark.parametrize("ruta", sorted(glob.glob(str(CICLOS / "*" / "*.json"))))
def test_programas_del_repo_validos_y_con_claves_nuevas(ruta):
    p = json.loads(Path(ruta).read_text(encoding="utf-8"))["parameters"]
    assert cp.errores_programa(p) == []
    for fase in ("calentamiento", "esterilizacion"):
        hoja = p[fase]["histeresis_cierre_camara"]
        assert (hoja["value"], hoja["type"], hoja["unit"], hoja["clase"], hoja["min"], hoja["max"]) \
            == (3.0, "float", "kPa", "diferencia", 1, 10)
    hoja = p["esterilizacion"]["max_reinicios_exposicion"]
    assert (hoja["value"], hoja["type"], hoja["min"], hoja["max"]) == (3, "int", 0, 10)
    # sin migración pendiente al cargarlos
    corr, no_apl = [], []
    migrar_parametros(p, corr, no_apl, recuperacion=True)
    assert corr == [] and no_apl == []


def test_programa_de_usuario_121_cumple_p1():
    p = _datos("user/instrumental_121.json")["parameters"]
    assert p["esterilizacion"]["presion_add_esterilizacion"]["value"] == 11.0


# ── Parámetros nuevos: catálogo y migración ─────────────────────────────────

@pytest.mark.parametrize("fase", ["calentamiento", "esterilizacion"])
def test_catalogo_histeresis_cierre_camara(fase):
    hoja = {"type": "float"}
    assert cp.coercionar(hoja, fase, ["histeresis_cierre_camara"], 1) == 1
    assert cp.coercionar(hoja, fase, ["histeresis_cierre_camara"], 10) == 10
    for malo in (0.9, 10.1):
        with pytest.raises(ValueError):
            cp.coercionar(hoja, fase, ["histeresis_cierre_camara"], malo)


def test_catalogo_max_reinicios_exposicion():
    hoja = {"type": "int"}
    assert cp.coercionar(hoja, "esterilizacion", ["max_reinicios_exposicion"], 0) == 0
    assert cp.coercionar(hoja, "esterilizacion", ["max_reinicios_exposicion"], 10) == 10
    for malo in (-1, 11, 2.5):
        with pytest.raises(ValueError):
            cp.coercionar(hoja, "esterilizacion", ["max_reinicios_exposicion"], malo)


def test_migracion_agrega_las_claves_nuevas_sin_aviso():
    p = _params()
    del p["calentamiento"]["histeresis_cierre_camara"]
    del p["esterilizacion"]["histeresis_cierre_camara"]
    del p["esterilizacion"]["max_reinicios_exposicion"]
    corr = []
    assert migrar_parametros(p, corr) is True
    assert corr == []
    claves = list(p["esterilizacion"])
    assert claves[claves.index("presion_add_esterilizacion") + 1] == "histeresis_cierre_camara"
    claves = list(p["calentamiento"])
    assert claves[claves.index("presion_add_calentamiento") + 1] == "histeresis_cierre_camara"
    assert p["esterilizacion"]["max_reinicios_exposicion"]["value"] == 3
    assert p["calentamiento"]["histeresis_cierre_camara"]["value"] == 3.0
    assert cp.errores_programa(p) == []
    assert migrar_parametros(p, corr) is False


# ── P2 (D-14.2) y su extensión ──────────────────────────────────────────────

def _instalar(tmp_path, nombre="user/instrumental_134.json", **valores):
    destino = tmp_path / "cycles"
    shutil.copytree(CICLOS / "factory", destino / "factory")
    (destino / "user").mkdir()
    datos = _datos(nombre)
    for ruta, valor in valores.items():
        fase, clave = ruta.split("__")
        datos["parameters"][fase][clave]["value"] = valor
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


def _correcciones(ctx, cycle_id):
    return {m["parametro"]: (m["anterior"], m["nuevo"], m["origen"])
            for c, m in ctx.cycle_manager.migraciones_correctivas() if c.id == cycle_id}


def test_p2_brecha_03_y_presion_add_al_minimo(tmp_path):
    from autoclave.services.domain.logging.db_manager import DbManager
    ruta = _instalar(tmp_path, esterilizacion__brecha_segura_temperatura=0.3,
                     esterilizacion__presion_add_esterilizacion=9.0)
    ctx = _cargar(tmp_path)
    c = ctx.cycle_manager.cycles["134_instrumental"]
    assert not c.danado
    assert c.get_param("esterilizacion", "brecha_segura_temperatura") == 1.0
    assert c.get_param("esterilizacion", "presion_add_esterilizacion") == 15.0
    assert _correcciones(ctx, c.id) == {
        "brecha_segura_temperatura": (0.3, 1.0, "migración tanda 16"),
        "presion_add_esterilizacion": (9.0, 15.0, "migración tanda 16")}
    # aviso SIS-06 por parámetro, con su unidad
    ctx._avisar_migraciones_correctivas()
    avisos = {i.valores["parametro"]: i.valores for i in ctx.alarm_manager.activas()
              if i.definicion.codigo == SIS_06}
    assert set(avisos) == {"brecha_segura_temperatura", "presion_add_esterilizacion"}
    assert avisos["brecha_segura_temperatura"]["unidad"] == "°C"
    assert (avisos["presion_add_esterilizacion"]["anterior"],
            avisos["presion_add_esterilizacion"]["nuevo"]) == ("9", "15")
    assert ctx.alarm_manager.has_blocking_alarm() is False
    # auditoría con valor anterior y nuevo; archivo reescrito con .bak
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.auditar_migraciones_correctivas()
    filas = {f["entidad"]: f for f in ctx.db.get_auditoria(evento="param_ciclo_cambio")}
    f = filas["134_instrumental/esterilizacion/presion_add_esterilizacion"]
    assert (f["valor_anterior"], f["valor_nuevo"]) == ("9.0", "15.0")
    assert f["detalle"]["origen"] == "migración tanda 16" and f["usuario"] == "sistema"
    f = filas["134_instrumental/esterilizacion/brecha_segura_temperatura"]
    assert (f["valor_anterior"], f["valor_nuevo"]) == ("0.3", "1.0")
    datos = json.loads(ruta.read_text(encoding="utf-8"))["parameters"]["esterilizacion"]
    assert datos["presion_add_esterilizacion"]["value"] == 15.0
    assert datos["brecha_segura_temperatura"]["value"] == 1.0
    bak = json.loads((ruta.parent / (ruta.name + ".bak")).read_text(encoding="utf-8"))
    assert bak["parameters"]["esterilizacion"]["brecha_segura_temperatura"]["value"] == 0.3
    # el siguiente arranque ya no migra
    assert _cargar(tmp_path).cycle_manager.migraciones_correctivas() == []


def test_p2_solo_brecha_si_presion_add_ya_alcanza(tmp_path):
    _instalar(tmp_path, esterilizacion__brecha_segura_temperatura=0.3)
    ctx = _cargar(tmp_path)
    assert _correcciones(ctx, "134_instrumental") == {
        "brecha_segura_temperatura": (0.3, 1.0, "migración tanda 16")}


def test_extension_sube_presion_add_aunque_la_brecha_ya_sea_1(tmp_path):
    """V-04: un programa con brecha 1,0 que incumple P1 al cargar (los de
    usuario de la compilación I: 121 °C/9) sube presion_add_esterilizacion al
    mínimo redondeado a 0,5 kPa, con la misma auditoría."""
    _instalar(tmp_path, "user/instrumental_121.json",
              esterilizacion__presion_add_esterilizacion=9.0)
    ctx = _cargar(tmp_path)
    c = ctx.cycle_manager.cycles["instrumental_121"]
    assert not c.danado
    assert c.get_param("esterilizacion", "presion_add_esterilizacion") == 11.0
    assert _correcciones(ctx, c.id) == {
        "presion_add_esterilizacion": (9.0, 11.0, "migración tanda 16")}


def test_extension_134_5_sube_a_15(tmp_path):
    _instalar(tmp_path, "user/bowe_dick.json", esterilizacion__presion_add_esterilizacion=9.0)
    ctx = _cargar(tmp_path)
    c = ctx.cycle_manager.cycles["bowe_dick"]
    assert not c.danado and c.get_param("esterilizacion", "presion_add_esterilizacion") == 15.0


def test_c04_4_y_p2_una_sola_correccion(tmp_path):
    _instalar(tmp_path, esterilizacion__presion_add_esterilizacion=99.0)
    ctx = _cargar(tmp_path)
    c = ctx.cycle_manager.cycles["134_instrumental"]
    assert c.get_param("esterilizacion", "presion_add_esterilizacion") == 15.0
    assert _correcciones(ctx, c.id) == {
        "presion_add_esterilizacion": (99.0, 15.0, "migración tanda 12; migración tanda 16")}


def test_salvaguarda_del_alivio_no_migra_nada_y_avisa(tmp_path):
    """Con el alivio de chaqueta del equipo en 340 kPa, subir a 15 dejaría la
    consigna + 10 en 344,2 kPa: no se migra nada (ni la brecha) y se avisa.
    El programa queda como estaba (con brecha 0,3 y 9 cumple P1)."""
    cp.fijar_config_equipo(_Config(presion_suministro_vapor=300, presion_alivio_chaqueta=340))
    ruta = _instalar(tmp_path, esterilizacion__brecha_segura_temperatura=0.3,
                     esterilizacion__presion_add_esterilizacion=9.0,
                     globals__presion_chaqueta=250)
    antes = ruta.read_text(encoding="utf-8")
    ctx = _cargar(tmp_path)
    c = ctx.cycle_manager.cycles["134_instrumental"]
    assert c.get_param("esterilizacion", "brecha_segura_temperatura") == 0.3
    assert c.get_param("esterilizacion", "presion_add_esterilizacion") == 9.0
    assert not c.danado
    assert ctx.cycle_manager.migraciones_correctivas() == []
    [(prog, m)] = ctx.cycle_manager.migraciones_no_aplicadas()
    assert prog is c and "alivio de chaqueta (340 kPa)" in m["motivo"]
    ctx._avisar_migraciones_correctivas()
    avisos = [i for i in ctx.alarm_manager.activas() if i.definicion.codigo == SIS_06]
    assert {i.valores["parametro"] for i in avisos} == {"brecha_segura_temperatura",
                                                        "presion_add_esterilizacion"}
    assert all("no se migró" in i.valores["motivo"] for i in avisos)
    assert ruta.read_text(encoding="utf-8") == antes


def test_salvaguarda_con_programa_que_incumple_p1_queda_danado_y_avisa(tmp_path):
    """Brecha 1,0 y 9 kPa a 134 °C, alivio de chaqueta 340: la subida a 15 no
    cabe; el programa no se toca, queda dañado por P1 y el aviso se emite."""
    cp.fijar_config_equipo(_Config(presion_suministro_vapor=300, presion_alivio_chaqueta=340))
    _instalar(tmp_path, esterilizacion__presion_add_esterilizacion=9.0,
              globals__presion_chaqueta=250)
    ctx = _cargar(tmp_path)
    c = ctx.cycle_manager.cycles["134_instrumental"]
    assert c.get_param("esterilizacion", "presion_add_esterilizacion") == 9.0
    assert c.danado and any(e.startswith("Coherencia de recuperación") for e in c.danado)
    ctx._avisar_migraciones_correctivas()
    assert [i.valores["parametro"] for i in ctx.alarm_manager.activas()
            if i.definicion.codigo == SIS_06] == ["presion_add_esterilizacion"]


def test_copia_e_instantanea_no_migran_p2():
    p = _params(esterilizacion__presion_add_esterilizacion=9.0)
    c = Cycle("p", "P", p, 2)
    assert c.get_param("esterilizacion", "presion_add_esterilizacion") == 9.0
    d = Cycle.desde_instantanea(c.instantanea())
    assert d.get_param("esterilizacion", "presion_add_esterilizacion") == 9.0


# ── DEU-01 ──────────────────────────────────────────────────────────────────

def test_sin_config_rigen_los_defectos():
    lim = cp.limites_presion_equipo()
    assert (lim.fondo_escala, lim.suministro, lim.alivio_camara, lim.alivio_chaqueta) == \
        (400, 350, 385, 385)
    assert cp.limites_para_mensaje() == {"alivio_camara": 385, "alivio_chaqueta": 385,
                                         "suministro": 350, "fondo_escala": 400}


def test_alivio_de_chaqueta_del_equipo_cambia_el_rechazo_y_el_mensaje():
    p = _params("factory/instrumental_121.json")        # presion_chaqueta 300 + 50
    assert cp.errores_programa(p) == []
    cp.fijar_config_equipo(_Config(presion_suministro_vapor=300, presion_alivio_chaqueta=345))
    errores = cp.errores_programa(p)
    assert any(e.startswith("Límite de presión de chaqueta") and "(345 kPa)" in e
               for e in errores)
    assert cp.codigo_coherencia(errores) == cp.CODIGO_LIMITE_CHAQUETA
    assert cp.valor_limite(p) == pytest.approx(345 - 50)
    assert cp.limites_para_mensaje()["alivio_chaqueta"] == 345


def test_alivio_de_camara_del_equipo_cambia_el_rechazo():
    c = Cycle("p", "P", _params(), 2)
    c.set_param("calentamiento", ["presion_add_calentamiento"], 25.0)     # 304 + 25 = 329
    cp.fijar_config_equipo(_Config(presion_suministro_vapor=300, presion_alivio_camara=325))
    with pytest.raises(cp.ErrorCoherencia) as e:
        c.set_param("calentamiento", ["presion_add_calentamiento"], 24.0)
    assert e.value.codigo == cp.CODIGO_LIMITE_CAMARA
    assert "alivio de cámara (325 kPa)" in str(e.value)
    assert e.value.valor == pytest.approx(round(325 - p_saturacion_kpa(134.0), 1))


def test_suministro_del_equipo_cambia_la_advertencia():
    p = _params("factory/instrumental_121.json")
    assert cp.advertencias_programa(p) == []
    cp.fijar_config_equipo(_Config(presion_suministro_vapor=200))
    claves = [c for c, _ in cp.advertencias_programa(p)]
    assert cp.ADVERTENCIA_CHAQUETA_ABIERTA in claves
    assert any("(200 kPa)" in m for _, m in cp.advertencias_programa(p))


def test_limites_incoherentes_del_equipo_vuelven_a_los_defectos():
    cp.fijar_config_equipo(_Config(presion_suministro_vapor=390))       # suministro >= alivio
    assert cp.limites_presion_equipo().alivio_chaqueta == 385


def test_fondo_de_escala_acota_las_presiones_absolutas():
    assert cp.limites("globals", ["presion_chaqueta"]) == (1, 400)
    cp.fijar_config_equipo(_Config(presion_alivio_camara=380, presion_alivio_chaqueta=380,
                                   presion_fondo_escala=380))
    assert cp.limites("globals", ["presion_chaqueta"]) == (1, 380)
    # subirlo no amplía el límite del modelo
    cp.fijar_config_equipo(_Config(presion_fondo_escala=600))
    assert cp.limites("globals", ["presion_chaqueta"]) == (1, 400)


def test_bajar_el_alivio_vuelve_danado_un_programa_instalado(tmp_path):
    _instalar(tmp_path)
    ctx = _cargar(tmp_path)              # con los límites de fábrica: válido
    c = ctx.cycle_manager.cycles["134_instrumental"]
    assert not c.danado
    cp.fijar_config_equipo(_Config(presion_suministro_vapor=300, presion_alivio_chaqueta=340))
    danados = ctx.cycle_manager.revalidar_programas()
    assert "134_instrumental" in danados
    assert c.danado and any(e.startswith("Límite de consigna de chaqueta")
                            and "alivio de chaqueta (340 kPa)" in e for e in c.danado)
    # volver a los límites de fábrica no "repara" en caliente: queda dañado
    # hasta la próxima carga (la revalidación solo marca)
    cp.fijar_config_equipo(None)
    assert ctx.cycle_manager.revalidar_programas() == []
    assert c.danado


def test_abrir_base_datos_vincula_y_revalida_antes_de_auditar(monkeypatch):
    from autoclave.backend import context as modulo
    orden = []
    monkeypatch.setattr(modulo, "DbManager", lambda: MagicMock())
    monkeypatch.setattr(modulo, "SensorCalibrationAuditDB", lambda: MagicMock())
    ctx = modulo.BackendContext()
    ctx._numeracion_y_ciclos_interrumpidos = lambda: orden.append("numeracion")
    ctx.revisar_contrasenas_semilla = lambda: orden.append("contrasenas")
    ctx.auditar_migraciones_correctivas = lambda: orden.append("auditar")
    ctx.config_manager = SimpleNamespace(vincular_bd=lambda db: orden.append("vincular"))
    ctx.cycle_manager = SimpleNamespace(revalidar_programas=lambda: orden.append("revalidar"))
    assert ctx.abrir_base_datos(intentos=1) is None
    assert orden == ["numeracion", "vincular", "revalidar", "auditar", "contrasenas"]


def test_cargar_configuracion_fija_el_config_antes_de_cargar(monkeypatch):
    from autoclave.backend import context as modulo
    visto = {}

    class _CM:
        def __init__(self):
            self.cycles, self.errores_carga = {}, []

        def load_all_cycles(self):
            visto["config"] = cp._config_equipo

        def set_default_cycle(self, _):
            pass

        def migraciones_correctivas(self):
            return []

    monkeypatch.setattr(modulo, "CycleManager", _CM)
    ctx = modulo.BackendContext()
    ctx._validar_configuracion = lambda: None
    ctx.cargar_asignacion_io = lambda *a, **k: None
    ctx.cargar_configuracion()
    assert visto["config"] is ctx.config_manager


# ── PRG-01 (D-PRG-1) ────────────────────────────────────────────────────────

def _perfil(clase=EquipmentClass.PISO_LAB, probes=None):
    return SimpleNamespace(equipment_class=clase, temperature_probes=probes)


_CON_REF = {"temp_camara": "principal", "temp_2_camara": "no_en_uso", "temp_ref": "referencia"}


def test_roles_sonda_no_activa():
    assert sc.roles_sonda_no_activa(_CON_REF, None) == []
    assert sc.roles_sonda_no_activa(_CON_REF, _perfil()) == []
    assert sc.roles_sonda_no_activa(_CON_REF, _perfil(probes={"temp_ref": False})) == ["temp_ref"]
    principal_2 = {"temp_camara": "no_en_uso", "temp_2_camara": "principal", "temp_ref": "no_en_uso"}
    assert sc.roles_sonda_no_activa(principal_2, _perfil(EquipmentClass.PISO)) == ["temp_2_camara"]


def test_inicio_bloqueado_por_rol_en_sonda_no_activa_aunque_lea():
    estado = SimpleNamespace(sensores_temp={"temp_camara": 25.0, "temp_ref": 24.0})
    prog = SimpleNamespace(sensores=_CON_REF)
    codigo, motivo = sc.verificar_inicio(prog, _perfil(probes={"temp_ref": False}), estado)
    assert codigo == sc.SENSOR_NO_DISPONIBLE
    assert motivo.startswith(sc.MOTIVO_SONDA_NO_ACTIVA) and "Referencia" in motivo
    # con la sonda activa (o sin perfil) inicia
    assert sc.verificar_inicio(prog, _perfil(), estado) is None
    assert sc.verificar_inicio(prog, None, estado) is None


@pytest.fixture
def entorno(tmp_path):
    from fastapi.testclient import TestClient
    from autoclave.services.domain.logging.db_manager import DbManager
    from autoclave.state_machine.machine.enum_global import GlobalState
    from tests.helpers.backend_doble import cargar_servidor
    ctx = MagicMock()
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.estado.get_flag.side_effect = lambda f: f == "LISTO_PARA_CICLO"
    ctx.estado.sensores_temp = {"temp_camara": 25.0, "temp_2_camara": 25.0, "temp_ref": 24.0}
    ctx.control_loop.bloqueo_maquina.return_value = threading.Lock()
    ctx.control_loop.test_mode_active = False
    ctx.control_loop.aplicar_roles_sensores.return_value = (False, "sin_copias")
    ctx.sin_base_de_datos = False
    ctx.profile = _perfil(probes={"temp_camara": True, "temp_2_camara": True, "temp_ref": False})
    archivo = tmp_path / "prog.json"
    archivo.write_text(json.dumps({"cycle_id": "p", "cycle_number": 2, "parameters": {}}),
                       encoding="utf-8")
    prog = Cycle("p", "Prog", {}, number=2)
    prog.source, prog._path = "user", str(archivo)
    ctx.cycle_manager.cycles = {"p": prog}
    ctx.control_loop.cycle = prog
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app), ctx, srv, prog, archivo


def _put(client, srv, asignacion):
    from tests.helpers.backend_doble import cabecera
    return client.put("/cycle/sensor-roles", headers=cabecera(srv, "tecnico"),
                      json={"programa": 2, "asignacion": asignacion,
                            "asignacion_anterior_esperada": sc.asignacion_por_omision()})


def test_put_roles_rechaza_sonda_no_activa(entorno):
    client, ctx, srv, prog, archivo = entorno
    antes = archivo.read_text(encoding="utf-8")
    r = _put(client, srv, _CON_REF)
    assert r.status_code == 422
    assert r.json()["codigo"] == sc.ROL_SONDA_NO_ACTIVA and r.json()["sensores"] == ["temp_ref"]
    assert prog.sensores == sc.asignacion_por_omision()
    assert archivo.read_text(encoding="utf-8") == antes


def test_put_roles_acepta_sonda_activa(entorno):
    client, ctx, srv, prog, _ = entorno
    asignacion = {"temp_camara": "principal", "temp_2_camara": "referencia", "temp_ref": "no_en_uso"}
    r = _put(client, srv, asignacion)
    assert r.status_code == 200 and prog.sensores == asignacion


def test_start_rechaza_rol_en_sonda_no_activa(entorno):
    client, ctx, srv, prog, _ = entorno
    prog.sensores = dict(_CON_REF)
    r = client.post("/cycle/start")
    assert r.status_code == 409 and r.json()["codigo"] == sc.SENSOR_NO_DISPONIBLE
    assert sc.MOTIVO_SONDA_NO_ACTIVA in r.json()["detail"]
    assert ("START_CICLO", True) not in [c.args for c in ctx.estado.set_flag.call_args_list]


# ── textos nuevos (los une la sesión principal) ─────────────────────────────

def test_fragmento_i18n_es_en():
    datos = json.loads((RAIZ / "docs" / "informes" / "tanda16" / "i18n" / "s4.json")
                       .read_text(encoding="utf-8"))
    for clave in ("opciones.err_coherencia_recuperacion", "opciones.err_rol_sonda_no_activa"):
        assert datos["es"][clave] and datos["en"][clave]
    assert set(datos["es"]) == set(datos["en"])
