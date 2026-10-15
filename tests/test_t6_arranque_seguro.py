"""T6 (E4, tanda 2026-10-14): contador persistente, índice UNIQUE,
instantánea del programa, ciclos interrumpidos y cierre inmediato del
COMPLETADO (planeacion_arranque_y_modo_sin_bd §7.5; fin de ciclo D-08)."""

import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from autoclave.core.managers.cycle_manager import Cycle
from autoclave.core.runtime.contador_ciclos import ContadorCiclos
from autoclave.services.domain.logging import db_manager
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.state_machine.machine.enum_global import GlobalState


# ── Contador persistente ────────────────────────────────────────────────────

def test_contador_empieza_en_1_y_persiste(tmp_path):
    ruta = tmp_path / "data" / "ciclo_contador.json"
    c = ContadorCiclos(ruta)
    assert c.siguiente() == 1
    assert c.siguiente() == 2
    assert ContadorCiclos(ruta).ultimo == 2
    assert json.loads(ruta.read_text(encoding="utf-8")) == {"ultimo": 2}
    assert not ruta.with_suffix(".json.tmp").exists()


def test_contador_se_sincroniza_con_la_base(tmp_path):
    c = ContadorCiclos(tmp_path / "c.json")
    assert c.sincronizar(41) == 41
    assert c.siguiente() == 42
    assert c.sincronizar(10) == 42            # nunca retrocede


def test_contador_no_queda_atras_de_la_base(tmp_path):
    c = ContadorCiclos(tmp_path / "c.json")
    assert c.siguiente(maximo_bd=100) == 101


def test_contador_ilegible_no_baja_de_la_base(tmp_path):
    ruta = tmp_path / "c.json"
    ruta.write_text("{roto", encoding="utf-8")
    c = ContadorCiclos(ruta)
    assert c.sincronizar(7) == 7
    assert c.siguiente() == 8


# ── Base de datos: v3, UNIQUE, interrumpidos ────────────────────────────────

def _crear(db, numero, **kw):
    return db.crear_ciclo(numero, "p", "Prog", 134, 4, "M", "S", "1.0", **kw)


def test_v3_crea_indice_unique_y_rechaza_numero_repetido(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    assert db.get_version_esquema() == 3 and db.indice_numero_unico()
    _crear(db, 5, uuid="u1", programa_json='{"x": 1}')
    with pytest.raises(sqlite3.IntegrityError):
        _crear(db, 5)
    fila = db.get_ciclo(1)
    assert fila["uuid"] == "u1" and fila["programa_json"] == '{"x": 1}'


def test_v3_con_duplicados_no_crea_el_indice(tmp_path):
    ruta = tmp_path / "t.db"
    db = DbManager(db_path=ruta)
    db._conn.execute("DROP INDEX idx_ciclos_numero_unico")
    _crear(db, 3); _crear(db, 3)
    db._conn.execute("PRAGMA user_version = 2")
    db._conn.commit()
    db.close() if hasattr(db, "close") else None
    db2 = DbManager(db_path=ruta)
    assert db2.get_version_esquema() == 3
    assert db2.indice_numero_unico() is False          # no destructiva


def test_cerrar_ciclos_interrumpidos(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    _crear(db, 1)
    db.cerrar_ciclo(1, "COMPLETADO")
    _crear(db, 2, programa_json='{"cycle_id": "p"}')
    cerrados = db.cerrar_ciclos_interrumpidos("interrumpido")
    assert [f["numero_ciclo"] for f in cerrados] == [2]
    fila = db.get_ciclo(2)
    assert fila["resultado"] == "INTERRUMPIDO" and fila["fecha_fin"]
    assert db.cerrar_ciclos_interrumpidos("x") == []


# ── Instantánea del programa ────────────────────────────────────────────────

def test_instantanea_reconstruye_el_programa():
    prog = Cycle("p", "Prog", {"globals": {"tipo_carga": {"value": "liquido"}}}, number=4)
    prog.source = "user"
    prog.sensores = {"temp_camara": "no_en_uso", "temp_2_camara": "principal",
                     "temp_ref": "no_en_uso"}
    copia = Cycle.desde_instantanea(json.loads(json.dumps(prog.instantanea())))
    assert (copia.id, copia.name, copia.number) == ("p", "Prog", 4)
    assert copia.get_param("globals", "tipo_carga") == "liquido"
    assert copia.sensores == prog.sensores


# ── Registro del ciclo ──────────────────────────────────────────────────────

from tests import test_cycle_logger_printer as tcl                      # noqa: E402


def test_completado_se_cierra_al_instante_en_el_registro():
    printer = tcl.FakePrinter()
    cl = tcl._build_logger(printer)
    cl.update()                        # inicio
    cl.estado.fase_ciclo = "COMPLETADO"
    cl.update()                        # sigue en CICLO esperando confirmación
    assert cl.db.cerrados and cl.db.cerrados[-1][1] == "COMPLETADO"


def test_numero_del_contador_y_uuid(tmp_path):
    printer = tcl.FakePrinter()
    cl = tcl._build_logger(printer)
    cl.contador = ContadorCiclos(tmp_path / "c.json")
    cl.contador.sincronizar(9)
    cl.db.max_numero_ciclo = lambda: 3
    cl.update()
    assert cl.contador.ultimo == 10
    assert cl.uuid_ciclo and len(cl.uuid_ciclo) == 36


# ── Recuperación de un ciclo interrumpido ───────────────────────────────────

def _loop():
    from autoclave.services.domain.loop.control_loop import ControlLoop
    from autoclave.core.runtime.status import EstadoAutoclave
    cm = MagicMock()
    cm.get_selected_cycle.return_value = None
    config = MagicMock()
    config.get.side_effect = lambda k, d=None: {"presion_admosferica": 101.3,
                                                "rango_presion_atm": 10.0,
                                                "temp_max_apertura": 80.0}.get(k, d)
    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(units=MagicMock(), door_service=MagicMock(), doors=[],
                           estado=EstadoAutoclave(), link=MagicMock(), set_do=MagicMock(),
                           alarm_manager=MagicMock(), cycle_manager=cm, config_manager=config)
    loop.cycle = None
    return loop


def _programa_liquido():
    prog = Cycle("liq", "Líquidos", {"globals": {"tipo_carga": {"value": "liquido"}},
                                     "descompresion": {"modo": {"value": 4}}}, number=4)
    return prog


def test_ciclo_interrumpido_con_camara_caliente_arranca_en_estado_seguro():
    loop = _loop()
    loop.estado.set_machine_state(GlobalState.PREPARACION)
    loop.estado.sensores_pres["pres_camara"] = 250.0
    loop.estado.sensores_temp["temp_camara"] = 115.0
    prog = _programa_liquido()
    loop.recuperar_ciclo_interrumpido(prog)
    assert prog in loop.programas_para_seguridad()
    loop._procesar_recuperacion()
    assert loop.estado_seguro.activo
    assert loop.estado_seguro.requiere_confirmacion       # nunca se reanuda solo
    loop.set_do.descompresion_rapida_on.assert_not_called()


def test_ciclo_interrumpido_con_camara_segura_no_hace_nada():
    loop = _loop()
    loop.estado.set_machine_state(GlobalState.PREPARACION)
    loop.estado.sensores_pres["pres_camara"] = 101.3
    loop.estado.sensores_temp["temp_camara"] = 40.0
    loop.recuperar_ciclo_interrumpido(_programa_liquido())
    loop._procesar_recuperacion()
    assert not loop.estado_seguro.activo


def test_preparacion_cede_la_camara_al_estado_seguro():
    from tests.test_adenda_estados import _make
    from autoclave.state_machine.states.preparacion import preparacion_state
    obj, am, set_do = _make(preparacion_state, None, pres_camara=250.0)
    obj.estado_seguro_activo = lambda: True
    assert obj.run() is False
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_called()


# ── Correcciones de la auditoría de temporización de T6 ────────────────────

def test_fallo_al_registrar_el_inicio_no_lanza_ni_se_reintenta(tmp_path):
    # TMG-01
    printer = tcl.FakePrinter()
    cl = tcl._build_logger(printer)
    cl.contador = ContadorCiclos(tmp_path / "c.json")
    cl.db.max_numero_ciclo = lambda: 0
    llamadas = []

    def crear(**kw):
        llamadas.append(kw)
        raise sqlite3.OperationalError("database is locked")

    cl.db.crear_ciclo = crear
    cl.update()
    cl.update()
    assert len(llamadas) == 1                 # no se reintenta en cada tick
    assert cl.sin_registro is True
    assert cl.contador.ultimo == 1            # un solo número reservado
    assert cl.contador.en_curso()["numero"] == 1   # la marca quedó igual


def test_marca_de_ciclo_en_curso_se_limpia_al_cerrar(tmp_path):
    printer = tcl.FakePrinter()
    cl = tcl._build_logger(printer)
    cl.contador = ContadorCiclos(tmp_path / "c.json")
    cl.db.max_numero_ciclo = lambda: 0
    cl.update()
    assert cl.contador.en_curso() is not None
    cl.estado.fase_ciclo = "COMPLETADO"
    cl.update()
    assert cl.contador.en_curso() is None


def test_contador_conserva_la_marca_al_avanzar(tmp_path):
    c = ContadorCiclos(tmp_path / "c.json")
    c.marcar_en_curso(5, {"cycle_id": "p"})
    c.sincronizar(9)
    assert c.en_curso() == {"numero": 5, "programa": {"cycle_id": "p"}}
    c.limpiar_en_curso()
    assert c.en_curso() is None and c.ultimo == 9


def test_programa_desconocido_se_trata_como_liquido():
    from autoclave.backend.context import _programa_desconocido
    assert _programa_desconocido().get_param("globals", "tipo_carga") == "liquido"


def test_sin_datos_vigentes_no_se_olvida_el_ultimo_ciclo():
    # TMG-04
    loop = _loop()
    loop.estado.set_machine_state(GlobalState.PREPARACION)
    loop.estado.sensores_pres["pres_camara"] = 101.3
    loop.estado.sensores_temp["temp_camara"] = 40.0
    prog = _programa_liquido()
    loop._programa_ultimo_ciclo = prog
    for _ in range(5):
        loop._seguir_programa_ultimo_ciclo(vigentes=False)
    assert prog in loop.programas_para_seguridad()


# ── Correcciones de la revisión de seguridad de T6 ─────────────────────────

def test_recuperacion_espera_tres_ticks_seguros():
    # SAF-02
    loop = _loop()
    loop.estado.set_machine_state(GlobalState.PREPARACION)
    loop.estado.sensores_pres["pres_camara"] = 101.3
    loop.estado.sensores_temp["temp_camara"] = 40.0
    loop.recuperar_ciclo_interrumpido(_programa_liquido())
    loop._procesar_recuperacion(); loop._procesar_recuperacion()
    assert loop._recuperacion_pendiente is not None
    loop._procesar_recuperacion()
    assert loop._recuperacion_pendiente is None and not loop.estado_seguro.activo


def test_modo_prueba_rechazado_con_recuperacion_pendiente():
    # SAF-03
    loop = _loop()
    loop.estado.set_machine_state(GlobalState.PREPARADO)
    loop.estado.set_flag("PARO_EMERGENCIA", False)
    loop.recuperar_ciclo_interrumpido(_programa_liquido())
    ok, motivo = loop.enter_test_mode()
    assert ok is False and "estado seguro" in motivo


def test_programa_para_arranque_sin_datos_es_conservador():
    # SAF-01 / SAF-05
    from autoclave.backend.context import BackendContext
    ctx = object.__new__(BackendContext)
    ctx.db = MagicMock()
    ctx.db.get_ciclos_recientes.return_value = []
    ctx.cycle_manager = MagicMock()
    programa = ctx._programa_para_arranque()
    assert programa.get_param("globals", "tipo_carga") == "liquido"


def test_programa_para_arranque_usa_el_ultimo_ciclo_y_lo_trata_como_liquido_si_falta():
    # SAF-04 / SAF-05
    from autoclave.backend.context import BackendContext
    ctx = object.__new__(BackendContext)
    prog = Cycle("p", "Prog", {"descompresion": {"modo": {"value": 2}}}, number=2)
    ctx.db = MagicMock()
    ctx.db.get_ciclos_recientes.return_value = [{"programa_json": json.dumps(prog.instantanea())}]
    ctx.cycle_manager = MagicMock()
    programa = ctx._programa_para_arranque()
    assert programa.id == "p"
    assert programa.get_param("globals", "tipo_carga") == "liquido"
