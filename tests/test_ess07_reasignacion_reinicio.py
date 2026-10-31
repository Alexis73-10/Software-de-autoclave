"""ESS-07 (§6.2 de planeacion_estado_seguro_silencioso.md): revisión de
seguridad de acb33873 (reasignación de E/S permitida en FALLA y con el
protocolo de estado seguro actuando).

Tras reasignar, el backend se reinicia (backend/reinicio.py): el lazo se
detiene bajo el lock con ALL_OFF y el proceso nuevo arranca con un
ControlLoop nuevo. Lo único que sobrevive del protocolo anterior es el
programa del último ciclo (BackendContext._programa_para_arranque) y la
lectura física de la cámara: el equivalente sin hardware del reinicio es
un ControlLoop recién construido que arranca con la cámara no segura (S9,
origen "arranque").

Escenarios del §6.2: reinicio con el protocolo activo y presión vigente,
con presión sin lectura y en FALLA con carga líquida. Las pruebas marcadas
xfail(strict=True) demuestran el comportamiento del protocolo de arranque
que origina el HALLAZGO H1.

Tanda 24 (RSB-01..03, decisión de Cristian del 29-oct, riesgo aceptado
HAZ-IO-05): la API ya NO rechaza la reasignación por sensores sin lectura,
Principal dañado, cámara no segura, paro activo, confirmación pendiente ni
estado seguro sobre carga líquida o sellada; solo en CICLO, fuera de
PREPARACION/PREPARADO/FALLA, en modo prueba o apagando. El camino H1 vuelve
a alcanzarse por una reasignación (mitigación: aviso `aviso_camara` con
verificación en el manómetro). Sección 6."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import autoclave.state_machine.cycle_phases.protocolo_fallo as modulo_protocolo
from autoclave.core.managers.cycle_manager import Cycle
from autoclave.core.runtime import asignacion_io as aio
from autoclave.core.runtime import camara_segura
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.devices.puertas.enum_doors import DoorState
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.cycle_phases.protocolo_fallo import (
    _DEBOUNCE_LECTURAS, ProtocoloFallo)
from autoclave.state_machine.machine.enum_global import GlobalState

# Fixtures de la API de reasignación (mismo arnés que R8)
from tests.test_r8_reasignacion_api import (  # noqa: F401
    CLAVE, _aplicar, _mapas_de_fabrica, api)

_CFG = {"presion_admosferica": 101.3, "rango_presion_atm": 10.0, "temp_max_apertura": 80.0}
_ASIG = {"temp_camara": "principal", "temp_2_camara": "no_en_uso", "temp_ref": "referencia"}
_VALVULAS_PELIGROSAS = {"descompresion_rapida_on", "descompresion_chaqueta_on",
                        "aire_comprimido_camara_on", "vapor_camara_on", "vapor_chaqueta_on"}


class _Config(dict):
    def get(self, k, d=None):
        return super().get(k, d)


def _programa(tipo="liquido", modo=4, timeout_min=1):
    params = {"descompresion": {"modo": {"value": modo},
                                f"modo_{modo}": {"temperatura_enfriamiento": {"value": 80.0},
                                                 "presion_camara_enfriamiento": {"value": 200},
                                                 "timeout": {"value": timeout_min}}},
              "finalizacion": {"temp_max_apertura": {"value": 80.0}}}
    if tipo is not None:
        params["globals"] = {"tipo_carga": {"value": tipo}}
    prog = Cycle("p", "p", params, number=1)
    prog.sensores = dict(_ASIG)
    return prog


def _loop_nuevo():
    """ControlLoop del proceso relanzado (mismo doble que S9)."""
    from autoclave.services.domain.loop.control_loop import ControlLoop
    cm = MagicMock()
    cm.get_selected_cycle.return_value = None
    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(units=MagicMock(), door_service=MagicMock(), doors=[],
                           estado=EstadoAutoclave(), link=MagicMock(), set_do=MagicMock(),
                           alarm_manager=AlarmManager(), cycle_manager=cm,
                           config_manager=_Config(_CFG))
    loop.cycle = None
    loop.set_do.reset_all_outputs.return_value = True
    loop.link.edad_ultima_ai.return_value = 0.1
    loop.estado.set_machine_state(GlobalState.PREPARACION)   # FALLA no sobrevive al reinicio
    loop.estado.set_flag("PARO_EMERGENCIA", False)
    return loop


def _reiniciar(programa, pres, temp, ref=None):
    """Proceso nuevo: recuperación con el programa del último ciclo y primer
    tick con datos vigentes."""
    loop = _loop_nuevo()
    loop.estado.sensores_pres["pres_camara"] = pres
    loop.estado.sensores_temp["temp_camara"] = temp
    loop.estado.sensores_temp["temp_ref"] = ref
    loop.recuperar_ciclo_interrumpido(programa)
    loop._procesar_recuperacion()
    return loop


def _ticks(loop, n=10):
    for _ in range(n):
        loop.estado_seguro.update(datos_vigentes=True)


def _abiertas(set_do):
    return {c[0] for c in set_do.method_calls if c[0].endswith("_on")}


def _no_abrir(loop):
    segura, _ = camara_segura.evaluar(loop.estado, loop.config_manager,
                                      loop.programas_para_seguridad(), None,
                                      temp_max_ciclo=loop.temp_max_tras_ciclo())
    return not segura


def _protocolo_previo(programa, pres, temp, ref):
    """Protocolo del proceso ANTES del reinicio (estado de referencia)."""
    estado = SimpleNamespace(sensores_pres={"pres_camara": pres},
                             sensores_temp={"temp_camara": temp, "temp_2_camara": None,
                                            "temp_ref": ref, "temp_drenaje": None})
    set_do = MagicMock()
    set_do.reset_all_outputs.return_value = True
    return ProtocoloFallo(estado, set_do, programa, _Config(_CFG)), estado, set_do


# ── 1. Reinicio con el protocolo activo y presión vigente ──────────────────

@pytest.mark.parametrize("tipo,modo", [("solido", 1), ("solido", 4), ("liquido", 4)])
def test_reinicio_presion_vigente_arranca_estado_seguro_solo_lenta(tipo, modo):
    loop = _reiniciar(_programa(tipo, modo), pres=250.0, temp=125.0, ref=125.0)
    es = loop.estado_seguro
    assert es.activo and es.causa == "arranque" and es.requiere_confirmacion is False
    assert es._protocolo.solo_lenta is True           # (a) enclavamiento conservado
    _ticks(loop)
    abiertas = _abiertas(loop.set_do)
    assert "descompresion_lenta_on" in abiertas
    assert not abiertas & _VALVULAS_PELIGROSAS
    assert _no_abrir(loop)


def test_reinicio_conserva_solo_lenta_aunque_el_sensor_vuelva_a_leer():
    """(a) Antes: solo_lenta enclavado por la presión de cámara perdida. La
    reasignación devuelve la lectura: el arranque sigue en solo la lenta."""
    previo, estado, _ = _protocolo_previo(_programa("solido", 1), 250.0, 125.0, 125.0)
    previo.ejecutar()
    estado.sensores_pres["pres_camara"] = None
    for _ in range(_DEBOUNCE_LECTURAS):
        previo.update()
    assert previo.solo_lenta is True
    loop = _reiniciar(_programa("solido", 1), pres=250.0, temp=125.0, ref=125.0)
    assert loop.estado_seguro._protocolo.solo_lenta is True
    _ticks(loop, 20)
    assert "descompresion_rapida_on" not in _abiertas(loop.set_do)


# ── 2. Reinicio con la presión sin lectura ──────────────────────────────────

def test_reinicio_sin_presion_no_abre_nada_y_mantiene_no_abrir():
    loop = _reiniciar(_programa("solido", 1), pres=None, temp=125.0, ref=125.0)
    es = loop.estado_seguro
    assert es.activo and es.causa == "arranque"
    _ticks(loop, 5)
    assert not _abiertas(loop.set_do)
    assert es._protocolo.presion_perdida is True
    assert "presión de cámara" in (es._protocolo.bloqueado_motivo or "")
    assert _no_abrir(loop)


def test_documenta_reinicio_sin_presion_corta_el_venteo_que_ya_corria():
    """Hallazgo Medio (HAZ-S9-02, DECISIÓN SIN CONFIRMAR): antes del reinicio
    la lenta seguía abierta con la presión perdida (D8-1.2); el ALL_OFF del
    reinicio la cierra y el arranque sin presión no la vuelve a abrir."""
    previo, estado, set_do = _protocolo_previo(_programa("solido", 2), 250.0, 125.0, 125.0)
    previo.ejecutar()
    previo.update()
    assert "descompresion_lenta_on" in _abiertas(set_do)
    loop = _reiniciar(_programa("solido", 2), pres=None, temp=125.0, ref=125.0)
    _ticks(loop, 10)
    assert "descompresion_lenta_on" not in _abiertas(loop.set_do)


# ── 3. Reinicio en FALLA con carga líquida ──────────────────────────────────

@pytest.mark.parametrize("modo", [1, 3, 4, 5])
def test_reinicio_liquido_caliente_nunca_la_rapida_aunque_venza_el_plazo(modo, monkeypatch):
    t = [1000.0]
    monkeypatch.setattr(modulo_protocolo.time, "monotonic", lambda: t[0])
    loop = _reiniciar(_programa("liquido", modo, timeout_min=1), pres=250.0, temp=118.0, ref=118.0)
    _ticks(loop, 3)
    t[0] += 3600.0                                      # plazo del modo vencido
    _ticks(loop, 10)
    abiertas = _abiertas(loop.set_do)
    assert not abiertas & {"descompresion_rapida_on", "descompresion_chaqueta_on"}
    assert _no_abrir(loop)


def _contexto_arranque(fila):
    from autoclave.backend.context import BackendContext
    falso = SimpleNamespace(_programa_del_ciclo_interrumpido=lambda: None,
                            db=SimpleNamespace(get_ciclos_recientes=lambda n: [fila] if fila else []))
    return BackendContext._programa_para_arranque(falso)


@pytest.mark.parametrize("tipo,esperado", [("liquido", True), (None, True), ("solido", False)])
def test_programa_del_arranque_conserva_el_tipo_de_carga(tipo, esperado):
    """Tras el reinicio el protocolo sabe que la carga era líquida (último
    ciclo registrado; sin tipo, líquido, SAF-05 de T6)."""
    fila = {"programa_json": json.dumps(_programa(tipo, 1).instantanea())}
    programa = _contexto_arranque(fila)
    prot, _, _ = _protocolo_previo(programa, 250.0, 118.0, 118.0)
    assert prot.es_liquido() is esperado


def test_programa_del_arranque_sin_ciclos_es_liquido():
    prot, _, _ = _protocolo_previo(_contexto_arranque(None), 250.0, 118.0, 118.0)
    assert prot.es_liquido() is True


@pytest.mark.parametrize("modo", [4, 5])
def test_referencia_previo_liquido_sin_principal_queda_sellado(modo):
    """Control: antes del reinicio, D8-2.10 sella la cámara."""
    previo, estado, set_do = _protocolo_previo(_programa("liquido", modo), 220.0, 118.0, 110.0)
    previo.ejecutar()
    previo.update()
    estado.sensores_temp["temp_camara"] = None
    for _ in range(_DEBOUNCE_LECTURAS + 5):
        previo.update()
    assert previo.sellado is True


@pytest.mark.xfail(strict=True, reason=(
    "HALLAZGO ESS07-H1 (Alto; riesgo aceptado HAZ-IO-05, tanda 24, sin 409 en la API): tras el reinicio el protocolo de arranque "
    "(control_loop.py:448-449, solo_lenta sin en_enfriamiento_contrapresion) "
    "no sella la cámara (D8-2.10) y ventea por la lenta una carga líquida "
    "caliente con la Referencia sobre temp_max_apertura"))
@pytest.mark.parametrize("modo", [4, 5])
def test_hallazgo_reinicio_liquido_sellado_no_debe_ventear(modo):
    loop = _reiniciar(_programa("liquido", modo), pres=220.0, temp=None, ref=110.0)
    assert loop.estado_seguro.activo
    _ticks(loop, 10)
    assert "descompresion_lenta_on" not in _abiertas(loop.set_do)


@pytest.mark.xfail(strict=True, reason=(
    "HALLAZGO ESS07-H1 (Alto, extensión; riesgo aceptado HAZ-IO-05, tanda 24): un líquido modo 4/5 que enfriaba "
    "con contrapresión pierde la contrapresión al reiniciar y se ventea por la "
    "lenta con la carga caliente (HAZ-S9-01 lo aceptó solo para el corte de "
    "energía; acb33873 lo vuelve un camino a pedido)"))
@pytest.mark.parametrize("modo", [4, 5])
def test_hallazgo_reinicio_liquido_en_contrapresion_no_debe_ventear_caliente(modo):
    loop = _reiniciar(_programa("liquido", modo), pres=220.0, temp=118.0, ref=118.0)
    _ticks(loop, 10)
    assert "descompresion_lenta_on" not in _abiertas(loop.set_do)


# ── 4. Ventana del reinicio: puertas ───────────────────────────────────────

def _servicio_puertas(estado_seguro_activo, presion_vigente, pres=250.0, temp=125.0):
    from autoclave.services.domain.puertas.ser_puertas import ServicioPuertas
    estado = EstadoAutoclave()
    estado.sensores_pres["pres_camara"] = pres
    estado.sensores_temp["temp_camara"] = temp
    for k in estado.estado_puertas:
        estado.estado_puertas[k] = DoorState.CERRADO
    estado.set_flag("PARO_EMERGENCIA", False)
    puerta = MagicMock()
    puerta.name = "Puerta 1"
    return ServicioPuertas([puerta], estado, None, _Config(_CFG),
                           estado_seguro_activo=estado_seguro_activo,
                           presion_vigente=presion_vigente)


def test_ventana_proceso_viejo_lazo_detenido_puerta_rechazada():
    # lazo detenido: estado seguro sigue activo y la presión deja de ser vigente
    ok, motivo = _servicio_puertas(lambda: True, lambda: False)._can_open_physical("Puerta 1")
    assert ok is False and motivo.codigo == "estado_seguro"


def test_ventana_proceso_nuevo_sin_datos_puerta_rechazada():
    # proceso nuevo antes de la primera trama: sin estado seguro todavía
    ok, motivo = _servicio_puertas(lambda: False, lambda: False,
                                   pres=101.3, temp=30.0)._can_open_physical("Puerta 1")
    assert ok is False and motivo.codigo == "sin_datos_vigentes"


def test_ventana_proceso_nuevo_con_datos_y_camara_presurizada_rechazada():
    ok, _ = _servicio_puertas(lambda: False, lambda: True)._can_open_physical("Puerta 1")
    assert ok is False


# ── 5. API: en FALLA con el protocolo actuando ─────────────────────────────

def test_reasignar_en_falla_detiene_el_lazo_y_deja_sen09_pendiente(api, monkeypatch):
    cliente, srv, ctx, cab, pedidos = api
    ctx.estado.get_machine_state.return_value = GlobalState.FALLA
    monkeypatch.setattr(srv, "_estado_seguro_en_marcha", lambda: True)
    r = _aplicar(cliente, cab(), {"vapor_camara": 27})
    assert r.status_code == 200, r.text
    # la ventana sin vigilancia empieza antes de responder: lazo detenido + ALL_OFF
    ctx.control_loop.iniciar_apagado.assert_called_once()
    assert pedidos
    # SEN-09: la función movida queda pendiente de verificar en el archivo
    _asig, datos = aio.vigente(ctx.asignacion_fabrica, ctx.archivo_asignacion)
    assert "vapor_camara" in datos["verificacion_pendiente"]


# ── 6. Tanda 24 (RSB-01..03): la reasignación no se bloquea ────────────────

def _estado_seguro_actuando(ctx, liquido=False, sellado=False, confirmar=False):
    es = ctx.control_loop.estado_seguro
    es.activo = True
    es.requiere_confirmacion = confirmar
    es._protocolo.sellado = sellado
    es._protocolo.es_liquido.return_value = liquido


def _aceptada(r):
    """Aceptada: 200, o 428/422 de la confirmación o la validación del
    cuerpo; nunca 409 por sensores, paro o estado seguro."""
    assert r.status_code in (200, 422, 428), r.text
    assert r.json().get("codigo") not in ("sensor_camara_no_segura", "estado_no_permitido")
    return r


def _sin_sondas(ctx):
    ctx.estado.sensores_pres = {"pres_camara": None}
    ctx.estado.sensores_temp = {"temp_camara": None, "temp_2_camara": None, "temp_ref": None}


@pytest.mark.req("RSB-01")
@pytest.mark.parametrize("preparar,cambios,aviso", [
    (lambda ctx: ctx.estado.sensores_pres.update(pres_camara=None), {"pres_camara": 13}, True),
    (lambda ctx: ctx.estado.sensores_temp.update(temp_camara=None), {"temp_camara": 4}, True),
    (_sin_sondas, {"pres_camara": 13}, True),
    (_sin_sondas, {"temp_camara": 4}, True),
    (lambda ctx: ctx.estado.sensores_temp.update(temp_camara=125.0), {"pres_camara": 13}, True),
    # sin programas rige temp_camara (fría): la Referencia caliente no cuenta
    # para camara_segura, así que no hay aviso; tampoco bloquea
    (lambda ctx: ctx.estado.sensores_temp.update(temp_ref=125.0), {"temp_camara": 4}, False),
    (lambda ctx: ctx.estado.sensores_pres.update(pres_camara=250.0), {"pres_camara": 13}, True),
    (lambda ctx: setattr(ctx.control_loop, "presion_vigente", False), {"pres_camara": 13}, True),
], ids=["presion_sin_lectura", "principal_sin_lectura", "ninguna_sonda_presion",
        "ninguna_sonda_principal", "sonda_caliente", "referencia_caliente",
        "camara_presurizada", "sin_datos_vigentes"])
def test_rsb01_sensores_no_bloquean(api, preparar, cambios, aviso):
    cliente, _srv, ctx, cab, pedidos = api
    preparar(ctx)
    g = cliente.get("/io/assignment", headers=cab()).json()
    assert g["editable"] is True and g["motivo"] == "" and g["aviso_camara"] is aviso
    r = _aceptada(_aplicar(cliente, cab(), cambios))
    assert r.status_code == 200 and pedidos
    # SEN-09: la función movida queda sin verificar (bloquea el inicio de ciclo)
    _asig, datos = aio.vigente(ctx.asignacion_fabrica, ctx.archivo_asignacion)
    assert set(cambios) <= set(datos["verificacion_pendiente"])
    ctx.control_loop.iniciar_apagado.assert_called_once()


@pytest.mark.req("RSB-01")
def test_rsb01_paro_activo_no_bloquea(api):
    cliente, _srv, ctx, cab, pedidos = api
    ctx.estado.get_flag.side_effect = lambda f: f == "PARO_EMERGENCIA"
    g = cliente.get("/io/assignment", headers=cab()).json()
    assert g["editable"] is True and g["aviso_camara"] is True
    assert _aceptada(_aplicar(cliente, cab(), {"pres_camara": 13})).status_code == 200
    assert pedidos


@pytest.mark.req("RSB-01")
@pytest.mark.parametrize("liquido,sellado,confirmar", [
    (False, False, True),          # confirmación «Confirmar y llevar a estado seguro» pendiente
    (True, False, False),          # estado seguro sobre carga líquida
    (False, True, False),          # cámara sellada
    (True, True, True),
])
def test_rsb01_estado_seguro_no_bloquea(api, liquido, sellado, confirmar):
    cliente, _srv, ctx, cab, pedidos = api
    ctx.estado.get_machine_state.return_value = GlobalState.FALLA
    _estado_seguro_actuando(ctx, liquido=liquido, sellado=sellado, confirmar=confirmar)
    g = cliente.get("/io/assignment", headers=cab()).json()
    assert g["editable"] is True and g["motivo"] == ""
    assert _aceptada(_aplicar(cliente, cab(), {"vapor_camara": 27})).status_code == 200
    assert pedidos


@pytest.mark.req("RSB-01")
def test_rsb01_tipo_de_carga_ilegible_no_bloquea(api):
    cliente, _srv, ctx, cab, pedidos = api
    _estado_seguro_actuando(ctx)
    ctx.control_loop.estado_seguro._protocolo.es_liquido.side_effect = RuntimeError("x")
    assert _aceptada(_aplicar(cliente, cab(), {"vapor_camara": 27})).status_code == 200


@pytest.mark.req("RSB-02")
def test_rsb02_428_y_422_siguen_rigiendo_sin_sensores(api):
    cliente, _srv, ctx, cab, pedidos = api
    _sin_sondas(ctx)
    r = cliente.post("/io/assignment", json={"cambios": {"pres_camara": 13}, "clave": CLAVE},
                     headers=cab())
    assert r.status_code == 428 and r.json()["codigo"] == "confirmacion_requerida"
    r = _aplicar(cliente, cab(), {"pres_camara": 99})
    assert r.status_code == 422 and r.json()["codigo"] == "puerto_inexistente"
    assert pedidos == [] and not ctx.archivo_asignacion.existe()


@pytest.mark.req("RSB-01")
def test_rsb01_restaurar_fabrica_y_verificar_no_bloquean(api):
    cliente, _srv, ctx, cab, pedidos = api
    aio.aplicar_en_memoria(aio.combinar(aio.fabrica_codigo(), {"pres_camara": 13}))
    _sin_sondas(ctx)
    ctx.estado.get_flag.side_effect = lambda f: f == "PARO_EMERGENCIA"
    r = cliente.post("/io/assignment/factory", json={"clave": CLAVE, "confirmar": True}, headers=cab())
    assert _aceptada(r).status_code == 200 and pedidos


@pytest.mark.req("RSB-02")
@pytest.mark.parametrize("preparar,motivo", [
    (lambda ctx: setattr(ctx.estado.get_machine_state, "return_value", GlobalState.CICLO), "ciclo"),
    (lambda ctx: setattr(ctx.estado.get_machine_state, "return_value", None), "estado"),
    (lambda ctx: setattr(ctx.control_loop, "test_mode_active", True), "modo_prueba"),
    (lambda ctx: setattr(ctx.control_loop, "apagando", True), "apagando"),
])
def test_rsb02_se_conservan_los_cuatro_bloqueos(api, preparar, motivo):
    cliente, _srv, ctx, cab, pedidos = api
    _sin_sondas(ctx)                         # aunque además falten los sensores
    preparar(ctx)
    g = cliente.get("/io/assignment", headers=cab()).json()
    assert g["editable"] is False and g["motivo"] == motivo
    for r in (_aplicar(cliente, cab(), {"vapor_camara": 27}),
              cliente.post("/io/assignment/factory", json={"clave": CLAVE, "confirmar": True},
                           headers=cab()),
              cliente.post("/io/assignment/verify", json={"funcion": "vapor_camara", "clave": CLAVE},
                           headers=cab())):
        assert r.status_code == 409, r.text
        assert r.json()["codigo"] == "estado_no_permitido" and r.json()["motivo"] == motivo
    assert pedidos == [] and not ctx.archivo_asignacion.existe()


@pytest.mark.req("RSB-02")
def test_rsb02_orden_de_los_bloqueos(api):
    cliente, _srv, ctx, cab, _p = api
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    ctx.control_loop.test_mode_active = True
    ctx.control_loop.apagando = True
    assert cliente.get("/io/assignment", headers=cab()).json()["motivo"] == "ciclo"
    ctx.estado.get_machine_state.return_value = GlobalState.FALLA
    assert cliente.get("/io/assignment", headers=cab()).json()["motivo"] == "modo_prueba"
    ctx.control_loop.test_mode_active = False
    assert cliente.get("/io/assignment", headers=cab()).json()["motivo"] == "apagando"


@pytest.mark.req("RSB-03")
def test_rsb03_aviso_camara_falso_con_la_camara_segura(api):
    cliente, _srv, _ctx, cab, _p = api
    assert cliente.get("/io/assignment", headers=cab()).json()["aviso_camara"] is False


@pytest.mark.req("RSB-03")
def test_rsb03_aviso_camara_ante_una_excepcion_es_verdadero(api, monkeypatch):
    cliente, _srv, ctx, cab, _p = api
    monkeypatch.setattr(camara_segura, "motivos", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    assert cliente.get("/io/assignment", headers=cab()).json()["aviso_camara"] is True
    ctx.programas_para_seguridad.side_effect = RuntimeError("y")
    assert cliente.get("/io/assignment", headers=cab()).json()["aviso_camara"] is True


@pytest.mark.req("RSB-03")
@pytest.mark.parametrize("sin_presion", [False, True])
def test_rsb03_aviso_camara_en_la_auditoria_del_reinicio(api, sin_presion):
    cliente, _srv, ctx, cab, _p = api
    if sin_presion:
        ctx.estado.sensores_pres["pres_camara"] = None
    assert _aplicar(cliente, cab(), {"vapor_camara": 27}).status_code == 200
    filas, _ = ctx.db.consultar_auditoria(evento="reinicio_control", limite=10)
    assert filas[0]["detalle"]["aviso_camara"] is sin_presion
