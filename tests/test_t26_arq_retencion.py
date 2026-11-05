# Tanda 26 (ARQ): el backend no actúa hasta que la UI termina el arranque.
#
# - ARQ-D1: sin POST /arranque/iniciar no corre ninguna etapa; la ruta es
#   idempotente y pasa la compuerta.
# - ARQ-D2: desde la etapa 7 el ControlLoop existe pero está retenido: ninguna
#   salida ON (10 s simulados con la planta y el módulo "conectado"), la
#   máquina de estados quieta, el paro y las alarmas de sensores se publican.
# - ARQ-D3: se libera solo con (a) etapas sin fallo bloqueante y (b)
#   POST /arranque/interfaz-lista.
# - ARQ-D4: sin aviso nunca libera y aparece ARR_SIN_INTERFAZ a los 60 s.
# - ARQ-D7: AUTOCLAVE_ESPERA_INTERFAZ=0 se ignora con sys.frozen.
# - ARQ-D8: etapa 8 degradable.
# - Rutas actuadoras rechazadas (409 arranque_retenido) mientras dura.
# - Integración con el simulador M31: retenido sin escribir ninguna bobina en
#   ON, liberación con interfaz-lista.

import threading
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from autoclave.backend.arranque import retencion, secuencia
from autoclave.backend.arranque.registro import RegistroArranque
from autoclave.backend.arranque.secuencia import ErrorArranque, ejecutar_arranque
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.helpers.backend_doble import cargar_servidor
from tests.test_e1_ensayo_simulador import programas  # noqa: F401 (fixture)


# ── ARQ-D7: variable de entorno ─────────────────────────────────────────────

@pytest.mark.req("ARQ-D7")
@pytest.mark.parametrize("entorno, congelado, esperado", [
    ({}, False, True),
    ({"AUTOCLAVE_ESPERA_INTERFAZ": "1"}, False, True),
    ({"AUTOCLAVE_ESPERA_INTERFAZ": "0"}, False, False),
    ({"AUTOCLAVE_ESPERA_INTERFAZ": " 0 "}, False, False),
    ({"AUTOCLAVE_ESPERA_INTERFAZ": "0"}, True, True),     # compilado: se ignora
    ({}, True, True),
])
def test_espera_interfaz_activa(entorno, congelado, esperado):
    assert retencion.espera_interfaz_activa(entorno, congelado=congelado) is esperado


@pytest.mark.req("ARQ-D7")
def test_con_sys_frozen_la_variable_se_ignora(monkeypatch):
    monkeypatch.setenv("AUTOCLAVE_ESPERA_INTERFAZ", "0")
    monkeypatch.setattr(retencion.sys, "frozen", True, raising=False)
    assert retencion.espera_interfaz_activa() is True
    contexto = _Contexto()
    reg = RegistroArranque()
    detener = threading.Event()
    # la secuencia (sin esperar_interfaz explícito) espera a la UI: no libera
    _correr_hasta_detener(contexto, reg, detener)
    assert not contexto.arranque_liberado.is_set()


# ── secuencia con un contexto falso ──────────────────────────────────────────

class _Reloj:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class _Contexto:
    def __init__(self, fallos=None, sin_lectura=None):
        self.llamadas = []
        self.fallos = fallos or {}
        self.sin_lectura = list(sin_lectura or [])
        self.control_loop = None
        self.arranque_liberado = threading.Event()
        self.liberado_al_construir = None

    def _etapa(self, nombre):
        self.llamadas.append(nombre)
        if nombre in self.fallos:
            raise self.fallos[nombre]

    def verificar_instalacion(self):
        self._etapa("instalacion")

    def cargar_configuracion(self):
        self._etapa("configuracion")

    def verificar_calibracion(self):
        self._etapa("calibracion")

    def abrir_base_datos(self, intentos):
        self._etapa("bd")

    def construir_control(self, al_cancelar_prueba):
        self.liberado_al_construir = self.arranque_liberado.is_set()
        self._etapa("control")
        self.control_loop = MagicMock()

    def es_conectada(self):
        return True

    def sensores_arranque_sin_lectura(self):
        return list(self.sin_lectura)


def _etapas(reg):
    return {e["clave"]: (e["estado"], e["codigo"]) for e in reg.instantanea()["etapas"]}


def _correr_hasta_detener(contexto, reg, detener, max_s=200.0, al_dormir=None, **kw):
    """Corre la secuencia con un reloj simulado; detiene a los `max_s`."""
    reloj = _Reloj()

    def dormir(s):
        reloj.t += s
        if al_dormir is not None:
            al_dormir(reloj.t)
        if reloj.t >= max_s:
            detener.set()
    ejecutar_arranque(contexto, reg, al_cancelar_prueba=lambda: None, al_operable=lambda: None,
                      detener=detener, reloj=reloj, dormir=dormir, **kw)
    return reloj


@pytest.mark.req("ARQ-D3")
def test_el_control_nace_retenido_y_se_libera_solo_con_la_interfaz():
    contexto = _Contexto()
    reg = RegistroArranque()
    vistos = []

    def al_dormir(t):
        if t >= 5 and not vistos:
            vistos.append((reg.terminado, contexto.arranque_liberado.is_set(),
                           _etapas(reg)["preparando_interfaz"]))
            reg.marcar_interfaz_lista()
    _correr_hasta_detener(contexto, reg, threading.Event(), al_dormir=al_dormir,
                          esperar_interfaz=True)
    assert contexto.liberado_al_construir is False      # construido retenido
    # (a) cumplida y (b) aún no: retenido, etapa de la UI en curso
    assert vistos == [(True, False, ("en_curso", None))]
    assert contexto.arranque_liberado.is_set()
    assert reg.instantanea()["liberado"] is False        # sin vincular aquí
    assert _etapas(reg)["preparando_interfaz"] == ("ok", None)


@pytest.mark.req("ARQ-D3")
def test_interfaz_lista_temprana_libera_al_terminar_las_etapas():
    contexto = _Contexto()
    reg = RegistroArranque()
    reg.marcar_interfaz_lista()          # (b) antes que (a)
    _correr_hasta_detener(contexto, reg, threading.Event(), esperar_interfaz=True)
    assert contexto.arranque_liberado.is_set()
    assert reg.terminado is True


@pytest.mark.req("ARQ-D3")
@pytest.mark.parametrize("etapa, codigo", [
    ("configuracion", "ARR_CONFIG_ILEGIBLE"),
    ("calibracion", "ARR_CALIBRACION"),
])
def test_fallo_bloqueante_nunca_libera(etapa, codigo):
    contexto = _Contexto(fallos={etapa: ErrorArranque(codigo)})
    reg = RegistroArranque()
    reg.marcar_interfaz_lista()
    _correr_hasta_detener(contexto, reg, threading.Event(), esperar_interfaz=True)
    assert reg.fallo_bloqueante is True
    assert "control" not in contexto.llamadas
    assert not contexto.arranque_liberado.is_set()


@pytest.mark.req("ARQ-D3")
def test_error_al_construir_el_control_no_libera():
    contexto = _Contexto(fallos={"control": RuntimeError("x")})
    reg = RegistroArranque()
    reg.marcar_interfaz_lista()
    _correr_hasta_detener(contexto, reg, threading.Event(), esperar_interfaz=True)
    assert _etapas(reg)["conectando_modulos_es"] == ("fallo", "ARR_ERROR_INTERNO")
    assert not contexto.arranque_liberado.is_set()


@pytest.mark.req("ARQ-D4")
def test_sin_aviso_nunca_libera_y_anota_arr_sin_interfaz_a_los_60_s():
    contexto = _Contexto()
    reg = RegistroArranque()
    vistos = {}

    def al_dormir(t):
        if 59.0 <= t < 59.2:
            vistos["antes"] = _etapas(reg)["preparando_interfaz"]
        if 61.0 <= t < 61.2:
            vistos["despues"] = _etapas(reg)["preparando_interfaz"]
    detener = threading.Event()
    _correr_hasta_detener(contexto, reg, detener, max_s=600.0, al_dormir=al_dormir,
                          esperar_interfaz=True)
    assert vistos["antes"] == ("en_curso", None)
    assert vistos["despues"] == ("en_curso", "ARR_SIN_INTERFAZ")
    # 10 minutos simulados sin aviso: sigue retenido (sin tope) hasta el apagado
    assert not contexto.arranque_liberado.is_set()
    assert reg.instantanea()["etapaActual"] is None and reg.terminado is True
    # el aviso tardío todavía libera
    contexto2 = _Contexto()
    reg2 = RegistroArranque()
    _correr_hasta_detener(contexto2, reg2, threading.Event(), max_s=10**6,
                          al_dormir=lambda t: reg2.marcar_interfaz_lista() if t > 300 else None,
                          esperar_interfaz=True)
    assert contexto2.arranque_liberado.is_set()
    assert _etapas(reg2)["preparando_interfaz"] == ("ok", "ARR_SIN_INTERFAZ")


def test_detener_corta_la_espera_de_la_interfaz():
    """La espera no bloquea el apagado (_detener_arranque)."""
    contexto = _Contexto()
    reg = RegistroArranque()
    detener = threading.Event()
    hilo = threading.Thread(target=ejecutar_arranque, args=(contexto, reg), kwargs={
        "al_cancelar_prueba": lambda: None, "al_operable": lambda: None,
        "detener": detener, "esperar_interfaz": True, "plazo_sensores_s": 0.1}, daemon=True)
    hilo.start()
    t0 = time.monotonic()
    while _etapas(reg)["preparando_interfaz"][0] != "en_curso" and time.monotonic() - t0 < 5:
        time.sleep(0.01)
    assert hilo.is_alive()
    detener.set()
    hilo.join(2)
    assert not hilo.is_alive()
    assert not contexto.arranque_liberado.is_set()


@pytest.mark.req("ARQ-D7")
def test_sin_espera_el_control_nace_liberado():
    contexto = _Contexto()
    reg = RegistroArranque()
    _correr_hasta_detener(contexto, reg, threading.Event(), esperar_interfaz=False)
    assert contexto.liberado_al_construir is True
    assert _etapas(reg)["preparando_interfaz"] == ("pendiente", None)


# ── ARQ-D8: etapa 8 ─────────────────────────────────────────────────────────

@pytest.mark.req("ARQ-D8")
def test_sensores_con_lectura_dejan_la_etapa_ok():
    contexto = _Contexto()
    reg = RegistroArranque()
    reg.marcar_interfaz_lista()
    _correr_hasta_detener(contexto, reg, threading.Event(), esperar_interfaz=True)
    assert _etapas(reg)["verificando_sensores"] == ("ok", None)


@pytest.mark.req("ARQ-D8")
def test_sensores_sin_lectura_degradan_sin_bloquear_y_se_libera():
    contexto = _Contexto(sin_lectura=["pres_camara"])
    reg = RegistroArranque()
    reloj = _correr_hasta_detener(contexto, reg, threading.Event(), esperar_interfaz=True,
                                  al_dormir=lambda t: reg.marcar_interfaz_lista()
                                  if t > 20 else None)
    assert _etapas(reg)["verificando_sensores"] == ("degradado", "ARR_SENSORES")
    assert reg.fallo_bloqueante is False and reg.terminado is True
    assert contexto.arranque_liberado.is_set()
    assert reloj.t >= secuencia.PLAZO_SENSORES_S


@pytest.mark.req("ARQ-D8")
def test_sensores_que_llegan_dentro_del_plazo():
    contexto = _Contexto(sin_lectura=["temp_camara"])
    reg = RegistroArranque()
    reg.marcar_interfaz_lista()

    def al_dormir(t):
        if t > 3:
            contexto.sin_lectura = []
    _correr_hasta_detener(contexto, reg, threading.Event(), al_dormir=al_dormir,
                          esperar_interfaz=True)
    assert _etapas(reg)["verificando_sensores"] == ("ok", None)


@pytest.mark.req("ARQ-D8")
def test_error_al_verificar_degrada_y_no_retiene_para_siempre():
    contexto = _Contexto()
    contexto.sensores_arranque_sin_lectura = MagicMock(side_effect=RuntimeError("x"))
    reg = RegistroArranque()
    reg.marcar_interfaz_lista()
    _correr_hasta_detener(contexto, reg, threading.Event(), esperar_interfaz=True)
    assert _etapas(reg)["verificando_sensores"] == ("degradado", "ARR_SENSORES")
    assert contexto.arranque_liberado.is_set()


# ── ARQ-D1: rutas, compuerta y main ─────────────────────────────────────────

@pytest.fixture
def servidor():
    ctx = MagicMock()
    ctx.arranque_liberado = threading.Event()
    srv, ctx = cargar_servidor(ctx)
    return srv, ctx, TestClient(srv.app)


@pytest.mark.req("ARQ-D1")
def test_sin_iniciar_no_corre_ninguna_etapa(servidor, monkeypatch):
    srv, _, client = servidor
    srv.preparar_arranque()
    llamadas = []
    monkeypatch.setattr(srv, "ejecutar_arranque", lambda *a, **k: llamadas.append(1))
    cuerpo = client.get("/arranque").json()
    assert cuerpo["esperandoIniciar"] is True and cuerpo["liberado"] is False
    assert {e["estado"] for e in cuerpo["etapas"]} == {"pendiente"}
    assert srv._hilo_arranque is None and llamadas == []
    instancia = cuerpo["instancia"]
    for _ in range(3):     # idempotente; sin token, con la compuerta 503 activa
        r = client.post("/arranque/iniciar")
        assert r.status_code == 200 and r.json() == {"ok": True, "instancia": instancia}
    srv._hilo_arranque.join(2)
    assert llamadas == [1]
    assert client.get("/arranque").json()["esperandoIniciar"] is False


@pytest.mark.req("ARQ-D1")
def test_iniciar_concurrente_lanza_un_solo_hilo(servidor, monkeypatch):
    srv, _, _ = servidor
    llamadas = []
    monkeypatch.setattr(srv, "ejecutar_arranque", lambda *a, **k: llamadas.append(1))
    hilos = [threading.Thread(target=srv.iniciar_arranque) for _ in range(8)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(2)
    srv._hilo_arranque.join(2)
    assert llamadas == [1]


@pytest.mark.req("ARQ-D1")
def test_main_con_espera_no_arranca_al_escuchar(monkeypatch):
    from autoclave.backend import main
    monkeypatch.delenv("AUTOCLAVE_ESPERA_INTERFAZ", raising=False)
    srv = MagicMock()
    servidor = MagicMock()
    import sys
    with patch.dict(sys.modules, {"autoclave.backend.server": srv}), \
            patch("autoclave.backend.server", srv, create=True), \
            patch.object(main.uvicorn, "Server", return_value=servidor), \
            patch.object(main.threading, "Thread") as hilo:
        main.main()
    destinos = [c.kwargs.get("target") for c in hilo.call_args_list]
    assert main.arrancar_cuando_escuche not in destinos
    assert main.latido_y_ticket in destinos      # el latido no espera a la UI


@pytest.mark.req("ARQ-D2")
@pytest.mark.parametrize("metodo, ruta", [
    ("post", "/doors/Puerta 1/open"),
    ("post", "/doors/Puerta 1/close"),
    ("post", "/cycle/start"),
    ("post", "/io/test/enter"),
    ("post", "/safe-state/confirm"),
    ("post", "/fault/reset"),
    ("patch", "/io/test/output/vapor_camara"),
])
def test_rutas_actuadoras_rechazadas_mientras_esta_retenido(servidor, metodo, ruta):
    srv, ctx, client = servidor
    srv.preparar_arranque()
    srv._contexto_operable.set()
    r = getattr(client, metodo)(ruta, json={})
    assert r.status_code == 409 and r.json()["codigo"] == "arranque_retenido"
    ctx.estado.set_flag.assert_not_called()
    ctx.control_loop.enter_test_mode.assert_not_called()
    ctx.control_loop.confirmar_estado_seguro.assert_not_called()
    ctx.setdo.set_output.assert_not_called()
    ctx.arranque_liberado.set()
    r = getattr(client, metodo)(ruta, json={})
    assert r.json().get("codigo") != "arranque_retenido"


@pytest.mark.req("ARQ-D2")
def test_lecturas_y_apagado_no_se_retienen(servidor):
    srv, _, client = servidor
    srv.preparar_arranque()
    srv._contexto_operable.set()
    assert client.post("/ui/activity").status_code == 200
    # H7 (revisión ARQ): interfaz-lista exige el arranque ya iniciado
    srv.registro_arranque.marcar_iniciado()
    assert client.post("/arranque/interfaz-lista").status_code == 200
    for metodo, ruta in (("POST", "/system/shutdown"), ("POST", "/auth/login"),
                         ("GET", "/status"), ("POST", "/outputs/reset"),
                         ("POST", "/cycle/abort")):
        assert retencion.ruta_actuadora(metodo, ruta) is False


@pytest.mark.req("ARQ-D2")
def test_sin_evento_fijado_de_verdad_cuenta_como_retenido(servidor):
    """Falla cerrada en la compuerta: is_set() que no devuelve True."""
    srv, ctx, client = servidor
    ctx.arranque_liberado = MagicMock()
    srv.preparar_arranque()
    srv._contexto_operable.set()
    assert client.post("/cycle/start").json()["codigo"] == "arranque_retenido"


# ── ARQ-D2: el ControlLoop real con la planta simulada ─────────────────────

@pytest.fixture
def equipo(monkeypatch, programas):   # noqa: F811
    from tests import test_s9_planta_simulada as s9
    a = s9._equipo(programas[1], monkeypatch, programas)
    a["loop"].arranque_liberado = threading.Event()      # como lo construye el backend
    return a, s9


def _encendidas(a):
    return sorted(c for c, v in a["modulo_es"].do.items() if v)


@pytest.mark.req("ARQ-D2")
def test_retenido_10_s_sin_ninguna_salida_on_aunque_la_camara_este_a_presion(equipo):
    a, s9 = equipo
    s9._caliente_a_presion(a["planta"])
    s9._arrancar(a)                       # ciclo interrumpido: estado seguro pendiente
    encendidas = set()
    for _ in range(int(10.0 / s9.TICK_S) + 1):     # 10 s simulados
        s9._tick(a)
        encendidas |= set(_encendidas(a))
    assert encendidas == set()
    assert a["estado"].get_machine_state() == GlobalState.PREPARACION
    assert a["loop"].state_machine.prev_state is None          # la máquina no corrió
    assert a["loop"].estado_seguro.activo is False
    assert a["loop"]._recuperacion_pendiente is not None       # diferida, no perdida
    assert a["loop"]._retencion_apagado is True                 # ALL_OFF de la retención
    # al liberar, el mismo tick procesa la recuperación (estado seguro, solo la lenta)
    a["loop"].arranque_liberado.set()
    for _ in range(4):
        s9._tick(a)
    assert a["loop"].estado_seguro.activo is True
    assert a["modulo_es"].on("descompresion_lenta")


@pytest.mark.req("ARQ-D2")
def test_retenido_publica_el_paro_y_las_alarmas_de_sensores(equipo):
    a, s9 = equipo
    original = a["publicar"]

    def publicar(estado):
        original(estado)
        estado.sensores_pres["pres_camara"] = None
        estado.sensores_di["paro_emergencia"] = 0       # paro pulsado (NC abierto)
    a["publicar"] = publicar
    for _ in range(6):
        s9._tick(a)
    assert a["estado"].get_flag("PARO_EMERGENCIA") is True
    assert "SEN-06" in s9._activas(a)        # presión de cámara sin lectura
    assert _encendidas(a) == []


@pytest.mark.req("ARQ-D2")
def test_retenido_el_buzzer_y_las_puertas_no_se_actualizan(monkeypatch):
    from autoclave.services.domain.loop.control_loop import ControlLoop
    estado = MagicMock()
    estado.get_machine_state.return_value = GlobalState.PREPARACION
    estado.get_flag.return_value = False
    estado.sensores_di = {"paro_emergencia": 1}
    link = MagicMock()
    link.is_connected.return_value = True
    link.edad_ultima_di.return_value = 0.1
    link.expansor_fuera_de_linea.return_value = False
    link.tomar_eventos.return_value = []
    puerta = MagicMock()
    set_do = MagicMock()
    with patch("autoclave.services.domain.loop.control_loop.StateMachine") as sm:
        loop = ControlLoop(units=MagicMock(), door_service=MagicMock(), doors=[puerta],
                           estado=estado, link=link, set_do=set_do,
                           alarm_manager=MagicMock(), cycle_manager=MagicMock(),
                           config_manager=MagicMock(), arranque_liberado=threading.Event())
        loop._conectado_desde = time.monotonic() - 10
        for _ in range(3):
            loop._tick()
        sm.return_value.update.assert_not_called()
        puerta.update.assert_not_called()
        set_do.buzer.update.assert_not_called()
        set_do.reset_all_outputs.assert_called_once()        # una vez por conexión
        assert not any(c.args[1:] == (True,) for c in set_do.set_output.call_args_list)
        loop.arranque_liberado.set()
        loop._tick()
        sm.return_value.update.assert_called_once()
        puerta.update.assert_called_once()
        set_do.buzer.update.assert_called_once()


# ── integración con el simulador M31 ───────────────────────────────────────

@pytest.fixture
def planta_m31(monkeypatch, tmp_path):
    from autoclave.backend import context as ctx_mod
    from autoclave.backend.context import BackendContext
    from autoclave.core.runtime.status import EstadoAutoclave
    from autoclave.protocols import modbus_link
    from autoclave.services.domain.logging.db_manager import DbManager
    from autoclave.services.domain.logging.sensor_calibration_audit import \
        SensorCalibrationAuditDB
    from tests.helpers.m31_simulado import M31Simulado, config_para
    from tests.test_t20_integracion import MAC_BANCO, _perfil
    sim = M31Simulado()
    sim.fijar_mac(MAC_BANCO)
    sim.precargar_configuracion()
    sim.iniciar()
    sim.di[EstadoAutoclave.map_di["paro_emergencia"]] = True
    sim.temperaturas[0] = 1342
    sim.corrientes[0] = 12000
    monkeypatch.setattr(modbus_link, "cargar_config", lambda *a, **k: config_para(sim))
    monkeypatch.setattr(ctx_mod, "get_installation_profile", _perfil)
    monkeypatch.setattr(ctx_mod, "DbManager", lambda: DbManager(tmp_path / "autoclave.db"))
    monkeypatch.setattr(ctx_mod, "SensorCalibrationAuditDB",
                        lambda: SensorCalibrationAuditDB(tmp_path / "calibracion.db"))
    monkeypatch.setattr(ctx_mod, "RealtimePrinter", MagicMock)
    ctx = BackendContext()
    srv, _ = cargar_servidor(ctx)
    srv.preparar_arranque()
    # la secuencia con la espera de la interfaz explícita (como el compilado)
    monkeypatch.setattr(srv, "ejecutar_arranque", lambda *a, **k: ejecutar_arranque(
        *a, **k, esperar_interfaz=True, plazo_es_s=10.0, pausa_es_s=0.05,
        plazo_sensores_s=2.0))
    yield sim, srv, ctx, TestClient(srv.app)
    srv._detener_arranque.set()
    if srv._hilo_arranque is not None:
        srv._hilo_arranque.join(3)
    if ctx.control_loop is not None:
        ctx.control_loop.stop()
    if ctx.serial is not None:
        ctx.serial.stop()
    sim.detener()


def _esperar(condicion, timeout=20.0):
    fin = time.monotonic() + timeout
    while time.monotonic() < fin:
        if condicion():
            return True
        time.sleep(0.05)
    return condicion()


def _alguna_bobina_on(sim):
    return [w for w in sim.escrituras_bobinas() if any(bool(v) for v in w[2])]


@pytest.mark.req("ARQ-D2")
@pytest.mark.req("ARQ-D3")
def test_simulador_retenido_sin_bobinas_on_y_libera_con_interfaz_lista(planta_m31):
    sim, srv, ctx, client = planta_m31
    time.sleep(0.5)
    assert ctx.serial is None and sim.escrituras_bobinas() == []      # sin iniciar: nada
    assert client.post("/arranque/iniciar").status_code == 200
    assert _esperar(lambda: client.get("/arranque").json()["terminado"] is True, 30)
    assert client.get("/status").json()["card_connected"] is True
    t0 = time.monotonic()
    while time.monotonic() - t0 < 3.0:                     # retenido con el módulo conectado
        assert not any(sim.bobinas)
        time.sleep(0.05)
    assert _alguna_bobina_on(sim) == []
    assert client.get("/arranque").json()["liberado"] is False
    assert ctx.control_loop.state_machine.prev_state is None
    assert client.post("/cycle/start").json()["codigo"] == "arranque_retenido"
    assert client.post("/arranque/interfaz-lista").status_code == 200
    assert _esperar(lambda: client.get("/arranque").json()["liberado"] is True, 5)
    assert _esperar(lambda: ctx.control_loop.state_machine.prev_state is not None, 5)
