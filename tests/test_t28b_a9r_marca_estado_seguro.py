"""Tanda 28b (A9-R1/R3, revisión de seguridad de A9; Cristian 6-nov: marca
persistente).

El registro del ciclo cierra el ciclo y borra la marca del contador apenas la
fase sale de "en curso", antes y durante el protocolo de fin de ciclo. Un
corte de energía o un reinicio del backend a mitad del protocolo de fallo o
del estado seguro se tomaba como un encendido normal (sin protocolo). Ahora:

- MarcaEstadoSeguro (core/runtime/marca_estado_seguro.py): archivo propio,
  escritura atómica; ilegible o corrupto = presente (falla cerrada).
- ControlLoop la escribe mientras el protocolo de fin de ciclo no termina
  (estado seguro activo, también en pausa por paro o modo prueba; FALLO o
  CANCELADO esperando confirmación en CICLO; arranque tras un ciclo
  interrumpido sin decidir) y la borra solo con la cámara segura confirmada o
  al empezar un ciclo nuevo.
- hubo_ciclo_interrumpido() devuelve True si la marca existe.
- A9-R3: un respaldo importado sin cierre cuenta como interrumpido, y un
  segundo intento de la etapa 6 no olvida lo del primero.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from autoclave.core.runtime.contador_ciclos import ContadorCiclos
from autoclave.core.runtime.marca_estado_seguro import MarcaEstadoSeguro
from autoclave.core.runtime.respaldo_ciclos import RespaldoCiclos, reimportar
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.helpers.arranque_doble import evento_liberado


# ── 1. la marca ────────────────────────────────────────────────────────────

def test_marca_ausente_escrita_y_borrada(tmp_path):
    m = MarcaEstadoSeguro(tmp_path / "data" / "es.json")
    assert m.presente() is False
    m.marcar({"origen": "fallo"})
    assert m.presente() is True
    assert json.loads(m.ruta.read_text(encoding="utf-8")) == {"origen": "fallo"}
    assert not list(m.ruta.parent.glob("*.tmp"))          # escritura atómica
    m.borrar()
    assert m.presente() is False
    m.borrar()                                            # sin marca: nada


@pytest.mark.parametrize("contenido", ["{no es json", "", "[1, 2]", "null"])
def test_marca_corrupta_o_ilegible_cuenta_como_presente(tmp_path, contenido):
    m = MarcaEstadoSeguro(tmp_path / "es.json")
    m.ruta.write_text(contenido, encoding="utf-8")
    assert m.presente() is True


def test_marca_que_no_se_puede_leer_cuenta_como_presente(tmp_path):
    m = MarcaEstadoSeguro(tmp_path / "es.json")
    m.ruta.write_text("{}", encoding="utf-8")
    with patch.object(type(m.ruta), "read_text", side_effect=PermissionError("bloqueado")):
        assert m.presente() is True


# ── 2. el contexto clasifica el arranque con la marca ──────────────────────

def _ctx(marca, ciclo=None, marca_contador=None):
    from autoclave.backend.context import BackendContext
    ctx = BackendContext()
    ctx._marca_estado_seguro = marca
    ctx._ciclo_interrumpido = ciclo
    ctx._marca_interrumpido = marca_contador
    ctx.sin_base_de_datos = False
    return ctx


def test_hubo_ciclo_interrumpido_con_la_marca(tmp_path):
    marca = MarcaEstadoSeguro(tmp_path / "es.json")
    ctx = _ctx(marca)
    assert ctx.hubo_ciclo_interrumpido() is False
    marca.marcar({"origen": "fallo"})
    assert ctx.hubo_ciclo_interrumpido() is True


def test_hubo_ciclo_interrumpido_con_la_marca_corrupta(tmp_path):
    marca = MarcaEstadoSeguro(tmp_path / "es.json")
    marca.ruta.write_text("\x00\x01", encoding="utf-8")
    assert _ctx(marca).hubo_ciclo_interrumpido() is True


def test_hubo_ciclo_interrumpido_si_la_marca_lanza():
    marca = MagicMock()
    marca.presente.side_effect = OSError("disco")
    assert _ctx(marca).hubo_ciclo_interrumpido() is True


# ── 3. A9-R3: respaldo importado sin cierre y segundo intento ──────────────

_SIN_CIERRE = "0f8fad5b-d9cb-469f-a165-70867728950e"
_CON_CIERRE = "7c9e6679-7425-40de-944b-e07fc1f90ae7"


def test_reimportar_separa_los_importados_sin_cierre(tmp_path):
    from autoclave.services.domain.logging.db_manager import DbManager
    respaldo = RespaldoCiclos(tmp_path / "respaldo")
    for uuid_ciclo, numero in ((_SIN_CIERRE, 5), (_CON_CIERRE, 6)):
        assert respaldo.encabezado(uuid_ciclo, {"numero": numero, "tipo": "p", "nombre": "p"})
    assert respaldo.cierre(_CON_CIERRE, {"resultado": "FALLO", "fecha_fin": "2026-11-06T10:00:00"})
    db = DbManager(tmp_path / "t.db")
    try:
        r = reimportar(respaldo, db, "interrumpido")
    finally:
        db.close()
    assert sorted(r["importados"]) == sorted([_SIN_CIERRE, _CON_CIERRE])
    assert r["interrumpidos"] == [_SIN_CIERRE]


@pytest.mark.parametrize("resultado, esperado", [
    ({"importados": ["u"], "completados": [], "errores": [], "interrumpidos": ["u"]}, True),
    ({"importados": ["u"], "completados": [], "errores": [], "interrumpidos": []}, False),
    ({"importados": [], "completados": [], "errores": ["x.jsonl"], "interrumpidos": []}, True),
])
def test_respaldo_sin_cierre_o_no_reimportado_es_interrumpido(tmp_path, monkeypatch,
                                                             resultado, esperado):
    from autoclave.backend import context as ctx_mod
    monkeypatch.setattr(ctx_mod, "reimportar", lambda *a, **k: resultado)
    ctx = _ctx(MarcaEstadoSeguro(tmp_path / "es.json"))
    ctx._respaldo_ciclos = MagicMock()
    ctx.db = MagicMock()
    ctx._reimportar_respaldos()
    assert ctx.hubo_ciclo_interrumpido() is esperado


def test_reimportacion_que_lanza_es_interrumpido(tmp_path, monkeypatch):
    from autoclave.backend import context as ctx_mod
    monkeypatch.setattr(ctx_mod, "reimportar", MagicMock(side_effect=RuntimeError("x")))
    ctx = _ctx(MarcaEstadoSeguro(tmp_path / "es.json"))
    ctx._respaldo_ciclos = MagicMock()
    ctx.db = MagicMock()
    ctx._reimportar_respaldos()
    assert ctx.hubo_ciclo_interrumpido() is True


def test_segundo_intento_de_la_etapa_6_no_olvida_el_ciclo_cerrado(tmp_path):
    """abrir_base_datos reintenta _numeracion_y_ciclos_interrumpidos: el
    segundo intento ya no ve el ciclo que cerró el primero."""
    from autoclave.backend.context import BackendContext
    ctx = BackendContext()
    ctx._marca_estado_seguro = MarcaEstadoSeguro(tmp_path / "es.json")
    ctx._contador_ciclos = ContadorCiclos(tmp_path / "contador.json")
    ctx._reimportar_respaldos = lambda: None
    ctx.db = MagicMock()
    ctx.db.max_numero_ciclo.return_value = 3
    ctx.db.cerrar_ciclos_interrumpidos.side_effect = [[{"id": 9, "numero_ciclo": 3}], []]
    ctx._numeracion_y_ciclos_interrumpidos()
    ctx._numeracion_y_ciclos_interrumpidos()
    ctx.sin_base_de_datos = False
    assert ctx._ciclo_interrumpido == {"id": 9, "numero_ciclo": 3}
    assert ctx.hubo_ciclo_interrumpido() is True


def test_segundo_intento_que_falla_al_cerrar_es_interrumpido(tmp_path):
    from autoclave.backend.context import BackendContext
    ctx = BackendContext()
    ctx._marca_estado_seguro = MarcaEstadoSeguro(tmp_path / "es.json")
    ctx._contador_ciclos = ContadorCiclos(tmp_path / "contador.json")
    ctx._reimportar_respaldos = lambda: None
    ctx.db = MagicMock()
    ctx.db.max_numero_ciclo.return_value = 0
    ctx.db.cerrar_ciclos_interrumpidos.side_effect = [[], RuntimeError("base")]
    ctx._numeracion_y_ciclos_interrumpidos()
    ctx._numeracion_y_ciclos_interrumpidos()
    ctx.sin_base_de_datos = False
    assert ctx.hubo_ciclo_interrumpido() is True


# ── 4. el ControlLoop escribe y borra la marca ─────────────────────────────

class _Config(dict):
    def get(self, k, d=None):
        return super().get(k, d)


def _loop(tmp_path):
    from autoclave.services.domain.loop.control_loop import ControlLoop
    cm = MagicMock()
    cm.get_selected_cycle.return_value = None
    marca = MarcaEstadoSeguro(tmp_path / "es.json")
    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(arranque_liberado=evento_liberado(), units=MagicMock(),
                           door_service=MagicMock(), doors=[], estado=EstadoAutoclave(),
                           link=MagicMock(), set_do=MagicMock(), alarm_manager=AlarmManager(),
                           cycle_manager=cm, config_manager=_Config({}),
                           marca_estado_seguro=marca)
    loop.estado.set_machine_state(GlobalState.PREPARACION)
    loop.state_machine.ciclo._protocolo.ejecutado = False
    return loop, marca


def _activar_estado_seguro(loop, origen="fallo"):
    protocolo = MagicMock()
    protocolo.ejecutado = True
    loop.estado_seguro.iniciar(protocolo, origen=origen)
    assert loop.estado_seguro.activo


def test_sin_protocolo_no_hay_marca(tmp_path):
    loop, marca = _loop(tmp_path)
    loop._sincronizar_marca_estado_seguro()
    assert marca.presente() is False


def test_fallo_esperando_confirmacion_en_ciclo_pone_la_marca(tmp_path):
    """Ventana entre el cierre del ciclo en la base (fase fuera de "en
    curso") y la confirmación: el ProtocoloFallo del ciclo ya corre."""
    loop, marca = _loop(tmp_path)
    loop.estado.set_machine_state(GlobalState.CICLO)
    loop._sincronizar_marca_estado_seguro()
    assert marca.presente() is False                   # ciclo en curso: el contador
    loop.state_machine.ciclo._protocolo.ejecutado = True
    loop._sincronizar_marca_estado_seguro()
    assert marca.presente() is True


@pytest.mark.parametrize("origen", ["fallo", "cancelado", "completado", "ciclo_interrumpido"])
def test_estado_seguro_activo_pone_la_marca_y_alcanzado_la_borra(tmp_path, origen):
    loop, marca = _loop(tmp_path)
    _activar_estado_seguro(loop, origen)
    loop._sincronizar_marca_estado_seguro()
    assert marca.presente() is True
    assert json.loads(marca.ruta.read_text(encoding="utf-8"))["origen"] == origen
    loop.estado_seguro._protocolo = None               # estado_seguro_alcanzado
    loop._sincronizar_marca_estado_seguro()
    assert marca.presente() is False


@pytest.mark.parametrize("pausa", ["paro", "modo_prueba", "confirmacion", "falla_a_preparacion"])
def test_pausas_y_salida_de_falla_no_borran_la_marca(tmp_path, pausa):
    loop, marca = _loop(tmp_path)
    _activar_estado_seguro(loop)
    loop._sincronizar_marca_estado_seguro()
    if pausa == "paro":
        loop.estado.set_flag("PARO_EMERGENCIA", True)
        loop.estado.set_flag("PARO_REAL", True)
        loop.estado_seguro.update(datos_vigentes=True)
    elif pausa == "modo_prueba":
        loop.estado_seguro.pausar("modo_prueba")
    elif pausa == "confirmacion":
        loop.estado_seguro.requiere_confirmacion = True
    else:
        loop.estado.set_machine_state(GlobalState.PREPARACION)
    for _ in range(5):
        loop._sincronizar_marca_estado_seguro()
    assert loop.estado_seguro.activo and marca.presente() is True


def test_ciclo_nuevo_borra_la_marca(tmp_path):
    loop, marca = _loop(tmp_path)
    _activar_estado_seguro(loop)
    loop._sincronizar_marca_estado_seguro()
    loop.estado_seguro.terminar()                       # on_state_entry(CICLO)
    loop.estado.set_machine_state(GlobalState.CICLO)
    loop._sincronizar_marca_estado_seguro()
    assert marca.presente() is False


def test_arranque_tras_ciclo_interrumpido_conserva_la_marca_hasta_decidir(tmp_path):
    loop, marca = _loop(tmp_path)
    marca.marcar({"origen": "fallo"})                   # del proceso anterior
    loop.recuperar_ciclo_interrumpido(MagicMock(), interrumpido=True)
    loop._sincronizar_marca_estado_seguro()
    assert marca.presente() is True
    loop._recuperacion_pendiente = None                 # 3 lecturas seguras al arrancar
    loop._sincronizar_marca_estado_seguro()
    assert marca.presente() is False


def test_arranque_normal_no_escribe_la_marca(tmp_path):
    loop, marca = _loop(tmp_path)
    loop.recuperar_ciclo_interrumpido(MagicMock(), interrumpido=False)
    loop._sincronizar_marca_estado_seguro()
    assert marca.presente() is False


def test_error_al_escribir_se_reintenta(tmp_path):
    loop, _ = _loop(tmp_path)
    falsa = MagicMock()
    falsa.marcar.side_effect = [OSError("disco"), None]
    loop.marca_estado_seguro = falsa
    _activar_estado_seguro(loop)
    loop._sincronizar_marca_estado_seguro()
    loop._sincronizar_marca_estado_seguro()
    loop._sincronizar_marca_estado_seguro()
    assert falsa.marcar.call_count == 2                 # reintento y luego nada (ya escrita)


def test_error_al_consultar_el_protocolo_mantiene_la_marca(tmp_path):
    loop, marca = _loop(tmp_path)
    marca.marcar({})
    with patch.object(type(loop.estado_seguro), "activo",
                      new=property(lambda self: (_ for _ in ()).throw(RuntimeError("x")))):
        assert loop.protocolo_fin_ciclo_en_curso() is True
        loop._sincronizar_marca_estado_seguro()
    assert marca.presente() is True


# ── 5. integración: lazo real, corte a mitad del protocolo y reinicio ───────

from tests.test_e1_ensayo_simulador import programas  # noqa: E402,F401
from tests.test_s9_planta_simulada import _caliente_a_presion, _equipo, _tick  # noqa: E402


def _clasificar(marca):
    """Proceso nuevo: el contexto decide con la base (ciclo ya cerrado, sin
    filas abiertas) y la marca."""
    return _ctx(marca).hubo_ciclo_interrumpido()


def test_corte_a_mitad_del_protocolo_y_reinicio_vuelve_a_correrlo(programas, monkeypatch,  # noqa: F811
                                                                   tmp_path):
    a = _equipo(programas[4], monkeypatch, programas)            # Líquidos
    marca = MarcaEstadoSeguro(tmp_path / "es.json")
    a["loop"].marca_estado_seguro = marca
    _caliente_a_presion(a["planta"])
    a["loop"].recuperar_ciclo_interrumpido(a["programa"].copia(), interrumpido=True)
    for _ in range(40):
        _tick(a)
    es = a["loop"].estado_seguro
    assert es.activo and marca.presente() is True
    # corte de energía / reinicio del backend aquí: el proceso nuevo lo sabe
    assert _clasificar(marca) is True
    # modo prueba a mitad: el protocolo queda en pausa y la marca sigue
    ok, _ = a["loop"].enter_test_mode()
    assert ok
    for _ in range(10):
        _tick(a)
    assert marca.presente() is True
    a["loop"].exit_test_mode()
    for _ in range(int(4 * 3600 / 0.5)):
        _tick(a)
        if not es.activo:
            break
    assert not es.activo
    _tick(a)
    assert marca.presente() is False                    # terminó de verdad
    assert _clasificar(marca) is False                  # el encendido siguiente es normal
