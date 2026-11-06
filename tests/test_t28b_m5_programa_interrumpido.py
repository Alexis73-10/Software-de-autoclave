"""Tanda 28b (A13-M5, decisión de Cristian del 6-nov): secado tras fallo en
el arranque tras un ciclo interrumpido solo con un programa seguro.

En origen `ciclo_interrumpido` el secado corre SOLO si el programa es la
instantánea del propio ciclo (programa_json de la fila o la de la marca del
contador, escrita al iniciarlo) o la que guardó la marca persistente del
protocolo de fin de ciclo (`marca_estado_seguro`, A9-R1). Con la copia de la
definición actual del programa, el último ciclo registrado o el programa
desconocido se omite con el motivo `programa_incierto`. Tipo de carga
ilegible = líquida (no seca).
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from autoclave import i18n
from autoclave.backend.context import BackendContext
from autoclave.core.managers.cycle_manager import Cycle
from autoclave.core.runtime.marca_estado_seguro import MarcaEstadoSeguro
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.installation import profile as perfil_mod
from autoclave.services.domain.logging import ticket_formatter as tf
from autoclave.state_machine.cycle_phases import protocolo_fallo as pf
from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.test_t28b_a13_secado_tras_fallo import ATM, _Equipo, _perfil, _programa


class _Config(dict):
    def get(self, k, d=None):
        return super().get(k, d)


def _ctx(fila=None, marca_contador=None, cycles=None, ultimo=None, marca_es=None):
    ns = SimpleNamespace(_ciclo_interrumpido=fila, _marca_interrumpido=marca_contador,
                         cycle_manager=SimpleNamespace(cycles=cycles or {}),
                         db=SimpleNamespace(get_ciclos_recientes=lambda n: [ultimo] if ultimo else []),
                         marca_estado_seguro=marca_es)
    ns._programa_del_ciclo_interrumpido_con_origen = (
        lambda: BackendContext._programa_del_ciclo_interrumpido_con_origen(ns))
    ns._programa_del_ciclo_interrumpido = (
        lambda: BackendContext._programa_del_ciclo_interrumpido(ns))
    return ns


def _origen(ns):
    return BackendContext._programa_para_arranque_con_origen(ns)


def _tipo(programa):
    return programa.get_param("globals", "tipo_carga")


# ── origen del programa en el contexto ──────────────────────────────────────

def test_instantanea_de_la_fila_es_del_ciclo():
    fila = {"id": 7, "tipo_ciclo": "p", "programa_json": json.dumps(_programa("solido").instantanea())}
    programa, del_ciclo = _origen(_ctx(fila=fila))
    assert del_ciclo is True and _tipo(programa) == "solido"


def test_instantanea_liquida_gana_a_la_definicion_actual_cambiada_a_solido():
    """El ciclo corrió con carga líquida; después alguien cambió el programa
    a sólido. Rige la instantánea (líquida): no seca."""
    fila = {"id": 7, "tipo_ciclo": "p", "programa_json": json.dumps(_programa("liquido").instantanea())}
    actual = _programa("solido")
    programa, del_ciclo = _origen(_ctx(fila=fila, cycles={"p": actual}))
    assert del_ciclo is True and _tipo(programa) == "liquido"


def test_copia_de_la_definicion_actual_es_incierta():
    """Fila v2 sin instantánea: el programa se reconstruye con la definición
    vigente (ahora sólida, antes líquida): incierto, no seca."""
    fila = {"id": 7, "tipo_ciclo": "p", "programa_json": None, "asignacion_sensores": None}
    programa, del_ciclo = _origen(_ctx(fila=fila, cycles={"p": _programa("solido")}))
    assert del_ciclo is False and _tipo(programa) == "solido"


def test_marca_del_contador_con_instantanea_es_del_ciclo():
    marca = {"numero": 5, "programa": _programa("solido").instantanea()}
    programa, del_ciclo = _origen(_ctx(marca_contador=marca))
    assert del_ciclo is True


def test_marca_del_contador_sin_programa_es_desconocido_liquido():
    programa, del_ciclo = _origen(_ctx(marca_contador={"numero": 5}))
    assert del_ciclo is False and _tipo(programa) == "liquido"


def test_ultimo_ciclo_registrado_es_incierto():
    ultimo = {"programa_json": json.dumps(_programa("solido").instantanea())}
    programa, del_ciclo = _origen(_ctx(ultimo=ultimo))
    assert del_ciclo is False and _tipo(programa) == "solido"


def test_sin_nada_es_desconocido():
    programa, del_ciclo = _origen(_ctx())
    assert del_ciclo is False and _tipo(programa) == "liquido"


def test_contexto_sin_el_metodo_con_origen_es_incierto():
    """Un contexto que solo sabe dar el programa (dobles anteriores): falla
    cerrada, incierto."""
    ns = SimpleNamespace(_programa_del_ciclo_interrumpido=lambda: _programa("solido"),
                         db=SimpleNamespace(get_ciclos_recientes=lambda n: []))
    programa, del_ciclo = _origen(ns)
    assert del_ciclo is False


def test_programa_para_arranque_conserva_su_firma():
    fila = {"id": 7, "tipo_ciclo": "p", "programa_json": json.dumps(_programa("solido").instantanea())}
    programa = BackendContext._programa_para_arranque(_ctx(fila=fila))
    assert isinstance(programa, Cycle) and _tipo(programa) == "solido"


# ── marca persistente de estado seguro ──────────────────────────────────────

def test_marca_estado_seguro_con_programa_es_del_ciclo(tmp_path):
    marca = MarcaEstadoSeguro(tmp_path / "m.json")
    marca.marcar({"origen": "fallo", "programa": _programa("solido").instantanea(),
                  "tipo_carga": "solido"})
    programa, del_ciclo = _origen(_ctx(marca_es=marca))
    assert del_ciclo is True and _tipo(programa) == "solido"


def test_marca_estado_seguro_sin_programa_cae_al_ultimo_ciclo_incierto(tmp_path):
    marca = MarcaEstadoSeguro(tmp_path / "m.json")
    marca.marcar({"origen": "fallo"})
    ultimo = {"programa_json": json.dumps(_programa("solido").instantanea())}
    programa, del_ciclo = _origen(_ctx(marca_es=marca, ultimo=ultimo))
    assert del_ciclo is False


@pytest.mark.parametrize("contenido", [b"\x00\xff{", b"[]", b'{"programa": "x"}',
                                       b'{"programa": {"parameters": 5}}'])
def test_marca_estado_seguro_ilegible_es_incierta(tmp_path, contenido):
    ruta = tmp_path / "m.json"
    ruta.write_bytes(contenido)
    marca = MarcaEstadoSeguro(ruta)
    assert marca.presente() is True                   # la presencia sigue cerrada
    programa, del_ciclo = _origen(_ctx(marca_es=marca))
    assert del_ciclo is False


def test_leer_marca_ausente_es_none(tmp_path):
    assert MarcaEstadoSeguro(tmp_path / "no.json").leer() is None


# ── protocolo ───────────────────────────────────────────────────────────────

def test_protocolo_con_programa_incierto_omite_el_secado(monkeypatch):
    e = _Equipo(monkeypatch)
    e.protocolo.programa_incierto = True
    e.protocolo.ejecutar(abrir_valvulas=False, solo_lenta=True)
    assert e.resultado() == {"estado": "omitido", "motivo": "programa_incierto", "segundos": None}


@pytest.mark.parametrize("tipo", ["liquido", None, "SOLIDO", 3])
def test_instantanea_no_solida_o_ilegible_no_seca(monkeypatch, tipo):
    e = _Equipo(monkeypatch, tipo=tipo)
    e.protocolo.programa_incierto = False
    e.protocolo.ejecutar(abrir_valvulas=False, solo_lenta=True)
    assert e.resultado()["motivo"] == "carga_liquida"


def test_programa_incierto_en_motivos_y_ticket():
    assert "programa_incierto" in pf.MOTIVOS_SECADO
    for idioma, esperado in (("es", "incierto"), ("en", "uncertain")):
        aviso = tf.aviso_secado_tras_fallo({"estado": "omitido", "motivo": "programa_incierto",
                                            "segundos": None})
        linea = tf._linea_secado(aviso, SimpleNamespace(idioma=idioma))
        assert esperado in linea


# ── ControlLoop: recuperación y marca ───────────────────────────────────────

def _loop(monkeypatch, marca=None):
    from autoclave.services.domain.loop.control_loop import ControlLoop
    from autoclave.state_machine.alarms.alarm_manager import AlarmManager
    from tests.helpers.arranque_doble import evento_liberado
    monkeypatch.setattr(perfil_mod, "vacio_instalado", lambda profile: True)
    cm = MagicMock()
    cm.get_selected_cycle.return_value = None
    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(arranque_liberado=evento_liberado(), units=MagicMock(),
                           door_service=MagicMock(), doors=[], estado=EstadoAutoclave(),
                           link=MagicMock(), set_do=MagicMock(), alarm_manager=AlarmManager(),
                           cycle_manager=cm,
                           config_manager=_Config({"presion_admosferica": ATM,
                                                   "rango_presion_atm": 5.0,
                                                   "temp_max_apertura": 80.0,
                                                   "secado_tras_fallo_s": 60}),
                           profile=_perfil(), marca_estado_seguro=marca)
    loop.link.edad_ultima_ai.return_value = 0.1
    loop.estado.set_machine_state(GlobalState.PREPARACION)
    loop.estado.set_flag("PARO_EMERGENCIA", False)
    loop.estado.sensores_pres["pres_camara"] = 250.0
    loop.estado.sensores_temp["temp_camara"] = 125.0
    loop.estado.sensores_di["agua_bomba"] = 1
    return loop


@pytest.mark.parametrize("del_ciclo,tipo,esperado", [
    (True, "solido", ("pendiente", None)),
    (False, "solido", ("omitido", "programa_incierto")),
    (True, "liquido", ("omitido", "carga_liquida")),
])
def test_arranque_tras_ciclo_interrumpido(monkeypatch, del_ciclo, tipo, esperado):
    loop = _loop(monkeypatch)
    loop.recuperar_ciclo_interrumpido(_programa(tipo), interrumpido=True,
                                      programa_del_ciclo=del_ciclo)
    loop._procesar_recuperacion()
    prot = loop.estado_seguro._protocolo
    assert loop.estado_seguro.causa == "ciclo_interrumpido"
    r = prot.secado_resultado
    assert (r["estado"], r["motivo"]) == esperado


def test_recuperar_sin_decir_el_origen_es_incierto(monkeypatch):
    loop = _loop(monkeypatch)
    loop.recuperar_ciclo_interrumpido(_programa("solido"), interrumpido=True)
    loop._procesar_recuperacion()
    assert loop.estado_seguro._protocolo.secado_resultado["motivo"] == "programa_incierto"


def test_marca_guarda_el_programa_de_la_recuperacion_del_ciclo(monkeypatch, tmp_path):
    marca = MarcaEstadoSeguro(tmp_path / "m.json")
    loop = _loop(monkeypatch, marca)
    loop.recuperar_ciclo_interrumpido(_programa("solido"), interrumpido=True,
                                      programa_del_ciclo=True)
    loop._sincronizar_marca_estado_seguro()
    datos = marca.leer()
    assert datos["tipo_carga"] == "solido" and datos["programa"]["cycle_id"] == "p"


def test_marca_no_guarda_un_programa_incierto(monkeypatch, tmp_path):
    marca = MarcaEstadoSeguro(tmp_path / "m.json")
    loop = _loop(monkeypatch, marca)
    loop.recuperar_ciclo_interrumpido(_programa("solido"), interrumpido=True)
    loop._sincronizar_marca_estado_seguro()
    assert marca.presente() is True and "programa" not in marca.leer()
    # ni después, con el protocolo de arranque ya en el estado seguro
    loop._procesar_recuperacion()
    marca.borrar()
    loop._marca_es_sincronizada = None
    loop._sincronizar_marca_estado_seguro()
    assert marca.presente() is True and "programa" not in marca.leer()


def test_marca_del_estado_seguro_tras_un_fallo_y_arranque_siguiente(monkeypatch, tmp_path):
    """Fallo con carga sólida: la marca guarda el programa del protocolo; tras
    un corte, el arranque lo lee como del ciclo (aunque la definición actual
    haya cambiado) y el secado se arma."""
    marca = MarcaEstadoSeguro(tmp_path / "m.json")
    loop = _loop(monkeypatch, marca)
    programa = _programa("solido")
    prot = ProtocoloFallo(loop.estado, loop.set_do, programa, loop.config_manager)
    prot.profile = loop.profile
    prot.ejecutar()
    loop.estado_seguro.iniciar(prot, origen="fallo")
    loop._sincronizar_marca_estado_seguro()
    datos = marca.leer()
    assert datos["origen"] == "fallo" and datos["tipo_carga"] == "solido"
    # proceso nuevo: sin fila interrumpida (el ciclo FALLO se cerró), con la marca
    cambiado = _programa("liquido")                   # la definición actual ya no es sólida
    nuevo, del_ciclo = _origen(_ctx(marca_es=MarcaEstadoSeguro(tmp_path / "m.json"),
                                    cycles={"p": cambiado}))
    assert del_ciclo is True and _tipo(nuevo) == "solido"


def test_error_al_armar_el_programa_de_la_marca_no_la_impide(monkeypatch, tmp_path):
    marca = MarcaEstadoSeguro(tmp_path / "m.json")
    loop = _loop(monkeypatch, marca)
    roto = _programa("solido")
    roto.instantanea = lambda: (_ for _ in ()).throw(RuntimeError("x"))
    loop.recuperar_ciclo_interrumpido(roto, interrumpido=True, programa_del_ciclo=True)
    loop._sincronizar_marca_estado_seguro()
    assert marca.presente() is True and "programa" not in marca.leer()
