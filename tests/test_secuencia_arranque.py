# tests/test_secuencia_arranque.py
#
# Secuencia de arranque por etapas (backend/arranque/secuencia.py) y los
# métodos por etapa de BackendContext, sin hardware ni SQLite real
# (planeacion_arranque_y_modo_sin_bd.md §4-§5; D-1..D-6 de la propuesta de fase B).

import threading
from unittest.mock import MagicMock

import pytest

from autoclave.backend import context as ctx_mod
from autoclave.backend.arranque import secuencia
from autoclave.backend.arranque.registro import RegistroArranque
from autoclave.backend.arranque.secuencia import ErrorArranque, ejecutar_arranque
from autoclave.backend.arranque.sin_bd import BdNoDisponible, BdNoDisponibleError
from autoclave.backend.context import BackendContext
from autoclave.installation.clock_guard import ClockTamperedError
from tests.alarmas_helpers import ids_viejos_activados, ids_viejos_activos, ids_viejos_resueltos


# ── secuencia con un contexto falso ──────────────────────────────────────────

class _Reloj:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class _Contexto:
    """Registra el orden de llamadas; cada etapa puede fallar a demanda."""
    def __init__(self, fallos=None, degradados=None, conecta_tras=0):
        self.llamadas = []
        self.fallos = fallos or {}
        self.degradados = degradados or {}
        self.conecta_tras = conecta_tras   # consultas de es_conectada() antes de conectar
        self.consultas = 0
        self.control_loop = None

    def _etapa(self, nombre):
        self.llamadas.append(nombre)
        if nombre in self.fallos:
            raise self.fallos[nombre]
        return self.degradados.get(nombre)

    def verificar_instalacion(self):
        return self._etapa("instalacion")

    def cargar_configuracion(self):
        return self._etapa("configuracion")

    def verificar_calibracion(self):
        return self._etapa("calibracion")

    def abrir_base_datos(self, intentos):
        return self._etapa("bd")

    def construir_control(self, al_cancelar_prueba):
        self._etapa("control")
        self.control_loop = MagicMock()
        self.control_loop.al_cancelar_modo_prueba(al_cancelar_prueba)
        self.control_loop.start()

    def es_conectada(self):
        self.consultas += 1
        return self.consultas > self.conecta_tras


def _correr(contexto, **kw):
    reg = RegistroArranque()
    operable = threading.Event()
    reloj = kw.pop("reloj", _Reloj())
    ejecutar_arranque(contexto, reg, al_cancelar_prueba=kw.pop("aviso", lambda: None),
                      al_operable=operable.set, reloj=reloj,
                      dormir=kw.pop("dormir", lambda s: None), **kw)
    return reg, operable


def _estados(reg):
    return {e["clave"]: (e["estado"], e["codigo"]) for e in reg.instantanea()["etapas"]}


def test_arranque_normal_completa_las_etapas_en_orden():
    contexto = _Contexto()
    aviso = object()
    reg, operable = _correr(contexto, aviso=aviso)
    assert contexto.llamadas == ["instalacion", "configuracion", "calibracion", "bd", "control"]
    inst = reg.instantanea()
    assert inst["terminado"] is True and inst["falloBloqueante"] is False
    assert operable.is_set()
    assert [e["estado"] for e in inst["etapas"]] == ["ok"] * 8 + ["pendiente"]
    # el aviso de paro se registra antes de start()
    nombres = [c[0] for c in contexto.control_loop.method_calls]
    assert nombres == ["al_cancelar_modo_prueba", "start"]
    assert contexto.control_loop.al_cancelar_modo_prueba.call_args.args[0] is aviso


@pytest.mark.parametrize("etapa, clave, codigo", [
    ("instalacion", "verificando_instalacion", "ARR_PERFIL"),
    ("configuracion", "cargando_configuracion", "ARR_CONFIG_ILEGIBLE"),
    ("configuracion", "cargando_configuracion", "ARR_CICLO_DEFECTO"),
    ("configuracion", "cargando_configuracion", "CONFIGURACION_INVALIDA"),
    ("calibracion", "verificando_calibracion", "ARR_CALIBRACION"),
])
def test_fallo_bloqueante_detiene_la_secuencia_sin_construir_el_control(etapa, clave, codigo):
    contexto = _Contexto(fallos={etapa: ErrorArranque(codigo)})
    reg, operable = _correr(contexto)
    assert "control" not in contexto.llamadas     # ni serial ni ControlLoop
    assert contexto.control_loop is None
    assert not operable.is_set()
    inst = reg.instantanea()
    assert inst["falloBloqueante"] is True
    assert inst["etapaActual"] == clave
    assert _estados(reg)[clave] == ("fallo", codigo)
    claves = [e["clave"] for e in inst["etapas"]]
    for siguiente in claves[claves.index(clave) + 1:]:
        assert _estados(reg)[siguiente] == ("pendiente", None)


def test_ciclo_corrupto_degrada_y_continua():
    contexto = _Contexto(degradados={"configuracion": "ARR_CICLO_CORRUPTO"})
    reg, _ = _correr(contexto)
    assert _estados(reg)["cargando_configuracion"] == ("degradado", "ARR_CICLO_CORRUPTO")
    assert reg.terminado is True


def test_bd_degradada_no_bloquea_el_arranque():
    contexto = _Contexto(degradados={"bd": "ARR_SIN_BD"})
    reg, operable = _correr(contexto)
    assert _estados(reg)["abriendo_base_datos"] == ("degradado", "ARR_SIN_BD")
    assert reg.terminado is True and reg.fallo_bloqueante is False
    assert operable.is_set()


def test_sin_es_a_los_15_s_anota_arr_sin_es_y_reintenta_sin_fallar():
    reloj = _Reloj()
    contexto = _Contexto(conecta_tras=10**9)
    reg = RegistroArranque()
    operable = threading.Event()
    detener = threading.Event()
    vistos = []

    def dormir(s):
        reloj.t += s
        if reloj.t >= 14.9 and not vistos:
            vistos.append(("antes", _estados(reg)["conectando_modulos_es"]))
        if reloj.t >= 16 and len(vistos) == 1:
            vistos.append(("despues", _estados(reg)["conectando_modulos_es"],
                           _estados(reg)["verificando_sensores"], reg.fallo_bloqueante,
                           operable.is_set()))
            contexto.conecta_tras = contexto.consultas   # las E/S conectan
    ejecutar_arranque(contexto, reg, al_cancelar_prueba=lambda: None, al_operable=operable.set,
                      detener=detener, reloj=reloj, dormir=dormir)
    assert vistos[0] == ("antes", ("en_curso", None))
    assert vistos[1] == ("despues", ("en_curso", "ARR_SIN_ES"), ("pendiente", None), False, True)
    # al conectar se retoma desde la etapa 7 sin reiniciar
    assert _estados(reg)["conectando_modulos_es"] == ("ok", None)
    assert _estados(reg)["verificando_sensores"] == ("ok", None)
    assert reg.terminado is True


def test_detener_corta_la_espera_de_es():
    contexto = _Contexto(conecta_tras=10**9)
    detener = threading.Event()
    reg = RegistroArranque()

    def dormir(_s):
        detener.set()
    ejecutar_arranque(contexto, reg, al_cancelar_prueba=lambda: None, al_operable=lambda: None,
                      detener=detener, reloj=_Reloj(), dormir=dormir)
    assert _estados(reg)["conectando_modulos_es"][0] == "en_curso"
    assert reg.terminado is False


@pytest.mark.parametrize("etapa, clave", [
    ("configuracion", "cargando_configuracion"),
    ("control", "conectando_modulos_es"),
])
def test_excepcion_no_prevista_es_fallo_interno(etapa, clave):
    contexto = _Contexto(fallos={etapa: KeyError("x")})
    reg, operable = _correr(contexto)
    assert _estados(reg)[clave] == ("fallo", "ARR_ERROR_INTERNO")
    assert reg.fallo_bloqueante is True
    assert not operable.is_set()


# ── métodos por etapa de BackendContext ──────────────────────────────────────

def test_el_constructor_no_hace_e_s(monkeypatch):
    for nombre in ("get_installation_profile", "ConfigManager", "CycleManager", "Units",
                   "DbManager", "SensorCalibrationAuditDB", "build_serial", "ControlLoop"):
        monkeypatch.setattr(ctx_mod, nombre, MagicMock(side_effect=AssertionError(nombre)))
    ctx = BackendContext()
    assert ctx.control_loop is None and ctx.db is None and ctx.serial is None


def test_instalacion_sin_perfil_o_con_reloj_alterado(monkeypatch):
    monkeypatch.setattr(ctx_mod, "get_installation_profile", lambda: None)
    with pytest.raises(ErrorArranque) as e:
        BackendContext().verificar_instalacion()
    assert e.value.codigo == "ARR_PERFIL"

    def reloj_alterado():
        raise ClockTamperedError("reloj")
    monkeypatch.setattr(ctx_mod, "get_installation_profile", reloj_alterado)
    with pytest.raises(ErrorArranque) as e:
        BackendContext().verificar_instalacion()
    assert e.value.codigo == "ARR_RELOJ"


class _Config:
    def __init__(self, error=None):
        self.error = error

    def load_config(self):
        if self.error:
            raise self.error


class _Ciclos:
    def __init__(self, con_defecto=True, errores=()):
        self.cycles = {"bowe_dick": object()} if con_defecto else {}
        self.errores_carga = list(errores)

    def load_all_cycles(self):
        pass

    def set_default_cycle(self, cycle_id):
        if cycle_id not in self.cycles:
            raise Exception(f"Ciclo por defecto '{cycle_id}' no encontrado")


def _configuracion(monkeypatch, config=None, ciclos=None, errores_validacion=()):
    monkeypatch.setattr(ctx_mod, "ConfigManager", lambda: config or _Config())
    monkeypatch.setattr(ctx_mod, "CycleManager", lambda: ciclos or _Ciclos())
    monkeypatch.setattr(ctx_mod, "errores_config_arranque", lambda _c: list(errores_validacion))
    return BackendContext()


@pytest.mark.parametrize("error", [OSError("no existe"), ValueError("json")])
def test_global_params_ilegible(monkeypatch, error):
    ctx = _configuracion(monkeypatch, config=_Config(error))
    with pytest.raises(ErrorArranque) as e:
        ctx.cargar_configuracion()
    assert e.value.codigo == "ARR_CONFIG_ILEGIBLE"


def test_ciclo_por_defecto_inexistente(monkeypatch):
    ctx = _configuracion(monkeypatch, ciclos=_Ciclos(con_defecto=False))
    with pytest.raises(ErrorArranque) as e:
        ctx.cargar_configuracion()
    assert e.value.codigo == "ARR_CICLO_DEFECTO"


def test_configuracion_invalida_es_fallo_con_alarma_y_sin_control_loop(monkeypatch):
    ctx = _configuracion(monkeypatch, errores_validacion=["rango_presion_atm fuera de rango"])
    with pytest.raises(ErrorArranque) as e:
        ctx.cargar_configuracion()
    assert e.value.codigo == "CONFIGURACION_INVALIDA"
    assert ids_viejos_activos(ctx.alarm_manager) == ["CONFIGURACION_INVALIDA"]


def test_ciclo_corrupto_devuelve_degradado(monkeypatch):
    ctx = _configuracion(monkeypatch, ciclos=_Ciclos(errores=["user/roto.json"]))
    assert ctx.cargar_configuracion() == "ARR_CICLO_CORRUPTO"


def test_configuracion_correcta(monkeypatch):
    assert _configuracion(monkeypatch).cargar_configuracion() is None


@pytest.mark.parametrize("contenido", [None, "", "# solo un comentario\n", "a: [1, 2\n"])
def test_calibracion_ausente_vacia_o_corrupta(monkeypatch, tmp_path, contenido):
    ruta = tmp_path / "calibration.yaml"
    if contenido is not None:
        ruta.write_text(contenido, encoding="utf-8")
    monkeypatch.setattr(ctx_mod, "calibration_path", lambda: ruta)
    monkeypatch.setattr(ctx_mod, "Units", MagicMock(side_effect=AssertionError("no debe cargarse")))
    with pytest.raises(ErrorArranque) as e:
        BackendContext().verificar_calibracion()
    assert e.value.codigo == "ARR_CALIBRACION"


def test_calibracion_que_no_valida(monkeypatch, tmp_path):
    ruta = tmp_path / "calibration.yaml"
    ruta.write_text("sensores: 1\n", encoding="utf-8")
    monkeypatch.setattr(ctx_mod, "calibration_path", lambda: ruta)
    monkeypatch.setattr(ctx_mod, "Units", MagicMock(side_effect=ValueError("no valida")))
    with pytest.raises(ErrorArranque) as e:
        BackendContext().verificar_calibracion()
    assert e.value.codigo == "ARR_CALIBRACION"


def test_calibracion_valida(monkeypatch, tmp_path):
    ruta = tmp_path / "calibration.yaml"
    ruta.write_text("sensores: 1\n", encoding="utf-8")
    monkeypatch.setattr(ctx_mod, "calibration_path", lambda: ruta)
    units = object()
    monkeypatch.setattr(ctx_mod, "Units", lambda r: units)
    ctx = BackendContext()
    ctx.verificar_calibracion()
    assert ctx.units is units


def test_bd_que_falla_tres_veces_degrada_con_alarma(monkeypatch):
    db = MagicMock(side_effect=OSError("disco"))
    monkeypatch.setattr(ctx_mod, "DbManager", db)
    monkeypatch.setattr(ctx_mod, "SensorCalibrationAuditDB", MagicMock())
    ctx = BackendContext()
    assert ctx.abrir_base_datos(3) == "ARR_SIN_BD"
    assert db.call_count == 3
    assert isinstance(ctx.db, BdNoDisponible) and isinstance(ctx.calibration_audit, BdNoDisponible)
    assert ctx.sin_base_de_datos is True
    [alarma] = ctx.alarm_manager.activas()
    assert alarma.codigo == "OPERANDO_SIN_BD"
    assert alarma.definicion.bloquea_inicio is True
    assert alarma.definicion.despeje.value == "MANUAL"
    with pytest.raises(BdNoDisponibleError):
        ctx.db.get_ciclo(1)


def test_bd_que_falla_una_vez_y_luego_abre(monkeypatch):
    abierta = object()
    db = MagicMock(side_effect=[OSError("ocupada"), abierta])
    monkeypatch.setattr(ctx_mod, "DbManager", db)
    monkeypatch.setattr(ctx_mod, "SensorCalibrationAuditDB", MagicMock())
    ctx = BackendContext()
    assert ctx.abrir_base_datos(3) is None
    assert ctx.db is abierta
    assert ctx.sin_base_de_datos is False
    assert ctx.alarm_manager.activas() == []


def test_construir_control_registra_el_aviso_antes_de_start(monkeypatch):
    loop = MagicMock()
    monkeypatch.setattr(ctx_mod, "build_serial", lambda units, al_conectar=None: MagicMock())
    monkeypatch.setattr(ctx_mod, "build_doors_cfg", lambda profile: [])
    for nombre in ("SetOutput", "ServicioPuertas", "RealtimePrinter", "CycleLogger"):
        monkeypatch.setattr(ctx_mod, nombre, MagicMock())
    monkeypatch.setattr(ctx_mod, "ControlLoop", MagicMock(return_value=loop))
    ctx = BackendContext()
    aviso = object()
    ctx.construir_control(aviso)
    # T6 (E4): la recuperación de arranque se arma antes de start()
    assert [c[0] for c in loop.method_calls] == ["al_cancelar_modo_prueba",
                                                 "recuperar_ciclo_interrumpido", "start"]
    assert loop.al_cancelar_modo_prueba.call_args.args[0] is aviso
    assert ctx.control_loop is loop


def test_es_conectada_sin_serial_es_falso():
    assert BackendContext().es_conectada() is False


def test_bd_no_disponible_no_engana_a_un_chequeo_de_verdad():
    bd = BdNoDisponible()
    assert not bd
    assert secuencia.ARR_SIN_BD == "ARR_SIN_BD"
