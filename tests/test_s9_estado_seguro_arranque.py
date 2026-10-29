"""S9 (tanda 9, D9-1): estado seguro al arrancar y bloqueos.

- D9-1.1: al arrancar con la cámara no segura el protocolo corre solo, sin
  confirmación: con presión sobre atm + brecha solo la lenta; con vacío, aire
  atmosférico.
- D9-1.2: la confirmación se exige solo tras un paro real visto en este
  encendido; la causa publicada distingue paro liberado / arranque / fallo.
- D9-1.3: con el estado seguro activo se permiten modo prueba (el protocolo se
  pausa y se reanuda), apagado y cambio de programa; el inicio sigue
  bloqueado y la seguridad sigue usando el programa del protocolo.
- D9-1.4: sin presión de cámara, CIC-10 (estado seguro detenido) + SEN-06.
- D9-1.6: coherencia puerta-presión (SEN-10).
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from autoclave.core.managers.cycle_manager import Cycle
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.devices.puertas.enum_doors import DoorState
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.instancia import EstadoInstancia
from autoclave.state_machine.alarms.catalogo import CATALOGO, CIC_10, Nivel, SEN_10, nombre_legible
from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo
from autoclave.state_machine.estado_seguro import ProtocoloEstadoSeguro
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.helpers.backend_doble import modulo_backend

_CFG = {"presion_admosferica": 101.3, "rango_presion_atm": 5.0, "temp_max_apertura": 80.0}


class _Config(dict):
    def get(self, k, d=None):
        return super().get(k, d)


def _programa(pid="p", principal="temp_camara", temp_max=80.0, tipo="solido", modo=1):
    prog = Cycle(pid, pid, {"globals": {"tipo_carga": {"value": tipo}},
                            "descompresion": {"modo": {"value": modo}},
                            "finalizacion": {"temp_max_apertura": {"value": temp_max}}},
                 number=1)
    prog.sensores = {s: ("principal" if s == principal else "no_en_uso")
                     for s in ("temp_camara", "temp_2_camara", "temp_ref")}
    return prog


def _loop(alarmas=None):
    from autoclave.services.domain.loop.control_loop import ControlLoop
    cm = MagicMock()
    cm.get_selected_cycle.return_value = None
    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(units=MagicMock(), door_service=MagicMock(), doors=[],
                           estado=EstadoAutoclave(), link=MagicMock(), set_do=MagicMock(),
                           alarm_manager=alarmas or AlarmManager(), cycle_manager=cm,
                           config_manager=_Config(_CFG))
    loop.cycle = None
    loop.set_do.reset_all_outputs.return_value = True
    # revisión ★ TMG-02: la recuperación y el estado seguro exigen la trama
    # AI vigente (un doble sin edad cuenta como AI vencida)
    loop.link.edad_ultima_ai.return_value = 0.1
    loop.estado.set_machine_state(GlobalState.PREPARACION)
    loop.estado.set_flag("PARO_EMERGENCIA", False)     # EmergencyStop arranca en paro
    return loop


def _arrancar(loop, pres, temp=120.0, programa=None):
    loop.estado.sensores_pres["pres_camara"] = pres
    loop.estado.sensores_temp["temp_camara"] = temp
    loop.recuperar_ciclo_interrumpido(programa or _programa())
    loop._procesar_recuperacion()


def _tick_es(loop, n=1):
    for _ in range(n):
        loop.estado_seguro.update(datos_vigentes=True)


def _abiertas(set_do):
    return {c[0] for c in set_do.method_calls if c[0].endswith("_on")}


# ── D9-1.1 / D9-1.2: el protocolo de arranque corre solo ───────────────────

def test_arranque_presurizado_sin_confirmacion_y_solo_la_lenta():
    loop = _loop()
    _arrancar(loop, pres=250.0, programa=_programa(modo=1))        # el modo 1 usaría la rápida
    es = loop.estado_seguro
    assert es.activo and es.requiere_confirmacion is False
    assert es.causa == "arranque"
    _tick_es(loop, 5)
    abiertas = _abiertas(loop.set_do)
    assert "descompresion_lenta_on" in abiertas
    assert not abiertas & {"descompresion_rapida_on", "descompresion_chaqueta_on",
                           "aire_admosferico_camara_on", "aire_comprimido_camara_on"}


def test_arranque_en_vacio_abre_aire_atmosferico_y_no_la_lenta():
    loop = _loop()
    _arrancar(loop, pres=20.0, temp=30.0)
    assert loop.estado_seguro.requiere_confirmacion is False
    _tick_es(loop, 3)
    abiertas = _abiertas(loop.set_do)
    assert "aire_admosferico_camara_on" in abiertas
    assert not abiertas & {"descompresion_lenta_on", "descompresion_rapida_on"}


def test_arranque_con_camara_segura_no_inicia_protocolo():
    loop = _loop()
    for _ in range(3):
        _arrancar(loop, pres=101.3, temp=30.0) if _ == 0 else loop._procesar_recuperacion()
    assert not loop.estado_seguro.activo and loop._recuperacion_pendiente is None


def test_paro_real_en_este_encendido_si_exige_confirmacion():
    loop = _loop()
    _arrancar(loop, pres=250.0)
    _tick_es(loop)
    loop.estado.set_flag("PARO_EMERGENCIA", True)
    loop.estado.set_flag("PARO_REAL", True)
    _tick_es(loop)
    loop.estado.set_flag("PARO_EMERGENCIA", False)
    loop.estado.set_flag("PARO_REAL", False)
    _tick_es(loop)
    assert loop.estado_seguro.requiere_confirmacion is True
    assert loop.estado_seguro.causa == "paro_liberado"
    assert loop.confirmar_estado_seguro() is True
    assert loop.estado_seguro.causa == "arranque"


def test_sin_datos_de_la_tarjeta_no_exige_confirmacion():
    """PARO_EMERGENCIA sin PARO_REAL (sin tramas): no es un paro real."""
    loop = _loop()
    _arrancar(loop, pres=250.0)
    loop.estado.set_flag("PARO_EMERGENCIA", True)
    _tick_es(loop)
    loop.estado.set_flag("PARO_EMERGENCIA", False)
    _tick_es(loop)
    assert loop.estado_seguro.requiere_confirmacion is False
    assert loop.estado_seguro.causa == "arranque"


@pytest.mark.parametrize("origen", ["fallo", "cancelado", "completado"])
def test_causa_del_fin_de_ciclo(origen):
    estado = EstadoAutoclave()
    es = ProtocoloEstadoSeguro(estado, _Config(_CFG), programas_seguridad=lambda: [])
    prot = MagicMock(ejecutado=True, cycle=None, bloqueado_motivo=None)
    es.iniciar(prot, origen=origen)
    assert es.causa == origen


def test_causa_sin_protocolo_es_none():
    es = ProtocoloEstadoSeguro(EstadoAutoclave(), _Config(_CFG))
    assert es.causa is None


def test_iniciar_sin_origen_es_fallo_de_ciclo():
    es = ProtocoloEstadoSeguro(EstadoAutoclave(), _Config(_CFG))
    es.iniciar(MagicMock(ejecutado=True, cycle=None, bloqueado_motivo=None))
    assert es.causa == "fallo"


# ── D9-1.4: sin presión de cámara ──────────────────────────────────────────

def test_arranque_sin_presion_no_abre_nada_y_activa_cic10():
    alarmas = AlarmManager()
    loop = _loop(alarmas)
    _arrancar(loop, pres=None, temp=30.0)
    es = loop.estado_seguro
    assert es.activo and es.requiere_confirmacion is False and es.causa == "arranque"
    _tick_es(loop, 2)
    assert not any(i.codigo == CIC_10 for i in alarmas.activas())     # debounce: 3 lecturas
    _tick_es(loop)
    # Tanda 17 (ESG-01, decisión de Cristian): sin presión de cámara no se
    # activa CIC-10 (solo la alarma del sensor); el protocolo sigue detenido
    assert not any(i.codigo == CIC_10 for i in alarmas.activas())
    assert es.detenido_sin_presion is True
    assert "presión de cámara" in es.bloqueado_motivo
    assert not _abiertas(loop.set_do)            # sin presión no se abre ninguna válvula


def test_arranque_sin_ningun_sensor_cic10_por_la_presion():
    """Equipo de pruebas sin sensores (H1): el motivo es la presión, no el
    Principal (sin presión nada puede terminar)."""
    alarmas = AlarmManager()
    loop = _loop(alarmas)
    _arrancar(loop, pres=None, temp=None)
    _tick_es(loop, 3)
    assert loop.estado_seguro.bloqueado_motivo.startswith("Sensor de presión de cámara")
    assert loop.estado_seguro.requiere_confirmacion is False
    assert not _abiertas(loop.set_do)


def test_cic10_por_presion_se_despeja_con_tres_lecturas():
    alarmas = AlarmManager()
    loop = _loop(alarmas)
    # ESS (SAF-07): la alarma del Principal a la vista
    alarmas.activar("SEN-03", origen=nombre_legible("temp_camara"), sensor=nombre_legible("temp_camara"), valor="—")
    _arrancar(loop, pres=None, temp=None)
    _tick_es(loop, 3)
    # Tanda 17 (ESG-01) y ESS-03 (28-oct): ni la presión ni el Principal sin
    # lectura dan CIC-10 (solo la alarma de cada sensor); el protocolo sigue
    # detenido
    cic10 = [i for i in alarmas.activas()
             if i.codigo == CIC_10 and i.estado is EstadoInstancia.ACTIVA]
    assert not cic10
    assert "Principal" in (loop.estado_seguro.bloqueado_motivo_sin_presion or "")
    assert loop.estado_seguro.detenido_sin_presion is True
    loop.estado.sensores_pres["pres_camara"] = 250.0
    loop.estado.sensores_temp["temp_camara"] = 120.0
    _tick_es(loop, 2)
    assert "presión de cámara" in (loop.estado_seguro.bloqueado_motivo or "")
    _tick_es(loop)
    assert "presión de cámara" not in (loop.estado_seguro.bloqueado_motivo or "")
    # con presión, el protocolo sigue solo por la lenta
    assert "descompresion_lenta_on" in _abiertas(loop.set_do)


def test_presion_perdida_con_el_protocolo_en_marcha_tambien_activa_cic10():
    estado = EstadoAutoclave()
    estado.sensores_pres["pres_camara"] = 250.0
    estado.sensores_temp["temp_camara"] = 120.0
    set_do = MagicMock()
    set_do.reset_all_outputs.return_value = True
    prot = ProtocoloFallo(estado, set_do, _programa(modo=2), _Config(_CFG))
    prot.ejecutar()
    estado.sensores_pres["pres_camara"] = None
    for _ in range(3):
        prot.update()
    assert prot.bloqueado_motivo.startswith("Sensor de presión de cámara sin lectura")


def test_motivo_de_presion_tiene_clave_i18n():
    from autoclave.core.runtime.alarmas_i18n import clave_motivo_bloqueo
    from autoclave import i18n
    estado = EstadoAutoclave()
    set_do = MagicMock()
    prot = ProtocoloFallo(estado, set_do, _programa(), _Config(_CFG))
    prot.ejecutar(abrir_valvulas=False, solo_lenta=True)
    for _ in range(3):
        prot.update()
    clave = clave_motivo_bloqueo(prot.bloqueado_motivo)
    assert clave == "estado_seguro_motivos.sin_presion_camara"
    assert i18n.existe(clave, "es") and i18n.existe(clave, "en")


# ── D9-1.3: modo prueba, cambio de programa y apagado permitidos ───────────

def test_modo_prueba_permitido_con_estado_seguro_y_lo_pausa():
    loop = _loop()
    _arrancar(loop, pres=250.0)
    _tick_es(loop)
    eventos = []
    loop.al_evento_seguridad = lambda e, d: eventos.append(e)
    ok, motivo = loop.enter_test_mode()
    assert ok is True, motivo
    assert loop.estado_seguro.activo                 # sigue activo (pausado)
    assert "estado_seguro_pausado" in eventos
    prot = loop.estado_seguro._protocolo
    prot.reanudar = MagicMock(wraps=prot.reanudar)
    loop.exit_test_mode()
    _tick_es(loop)
    prot.reanudar.assert_called_once()               # pulsos y plazos desde cero


def test_modo_prueba_permitido_con_recuperacion_pendiente():
    loop = _loop()
    loop.estado.set_flag("PARO_EMERGENCIA", False)
    loop.recuperar_ciclo_interrumpido(_programa())
    ok, _ = loop.enter_test_mode()
    assert ok is True


@patch("autoclave.services.domain.loop.control_loop.StateMachine")
def test_cambio_de_programa_permitido_con_estado_seguro(_sm):
    loop = _loop()
    _arrancar(loop, pres=250.0)
    nuevo = _programa("otro")
    assert loop.set_active_cycle(nuevo) == (True, "")
    assert loop.cycle is nuevo and loop.estado_seguro.activo


@patch("autoclave.services.domain.loop.control_loop.StateMachine")
def test_cambio_de_programa_permitido_con_recuperacion_pendiente(_sm):
    loop = _loop()
    loop.recuperar_ciclo_interrumpido(_programa())
    assert loop.set_active_cycle(_programa("otro"))[0] is True


@patch("autoclave.services.domain.loop.control_loop.StateMachine")
def test_cambio_de_programa_durante_el_protocolo_no_relaja_la_seguridad(_sm):
    """El programa nuevo tiene un Principal frío y una temperatura de apertura
    alta; el del protocolo (Principal caliente, apertura 60 °C) sigue mandando."""
    loop = _loop()
    del_protocolo = _programa("prot", principal="temp_camara", temp_max=60.0)
    _arrancar(loop, pres=250.0, temp=100.0, programa=del_protocolo)
    # el último ciclo se olvida (p. ej. reasignación); el protocolo sigue
    loop._programa_ultimo_ciclo = None
    nuevo = _programa("nuevo", principal="temp_ref", temp_max=120.0)
    assert loop.set_active_cycle(nuevo)[0] is True
    programas = loop.programas_para_seguridad()
    assert del_protocolo in programas and nuevo in programas
    assert loop.temp_max_tras_ciclo() == 60.0
    # cámara a presión atmosférica, Principal del protocolo en 70 °C, Referencia fría
    loop.estado.sensores_pres["pres_camara"] = 101.3
    loop.estado.sensores_temp.update({"temp_camara": 70.0, "temp_ref": 40.0})
    from autoclave.core.runtime import camara_segura
    segura, _ = camara_segura.evaluar(loop.estado, loop.config_manager,
                                      loop.programas_para_seguridad(), None,
                                      temp_max_ciclo=loop.temp_max_tras_ciclo())
    assert segura is False                     # 70 °C > 60 °C del protocolo
    _tick_es(loop, 5)
    assert loop.estado_seguro.activo           # no termina con el programa nuevo


def test_programas_para_seguridad_en_ciclo_no_cambia():
    loop = _loop()
    loop.estado.set_machine_state(GlobalState.CICLO)
    loop.state_machine.ciclo.programa_en_curso = "copia"
    assert loop.programas_para_seguridad() == ["copia"]


def test_inicio_sigue_bloqueado_con_estado_seguro():
    from tests.test_adenda_estados import _make
    from autoclave.state_machine.states.preparado import preparado_state
    obj, am, set_do = _make(preparado_state, None, pres_camara=101.3)
    obj.estado_seguro_activo = lambda: True
    assert obj.run() is False


# ── D9-1.6: coherencia puerta-presión ──────────────────────────────────────

def test_sen10_en_el_catalogo():
    d = CATALOGO[SEN_10]
    assert d.nivel is Nivel.ALARMA and d.bloquea_inicio is True
    assert "puerta" in d.titulo.lower() and "presión" in d.titulo.lower()
    for palabra in ("calibración", "presión atmosférica", "sensor de puerta"):
        assert palabra in d.accion


def _coherencia(alarmas=None):
    from autoclave.core.runtime.coherencia_puerta_presion import VigilanciaCoherenciaPuertaPresion
    alarmas = alarmas or AlarmManager()
    return VigilanciaCoherenciaPuertaPresion(alarmas, _Config(_CFG)), alarmas


def _estado_puerta(abierta=True, pres=150.0):
    estado = EstadoAutoclave()
    estado.sensores_pres["pres_camara"] = pres
    for k in estado.estado_puertas:
        estado.estado_puertas[k] = DoorState.CERRADO
    primera = next(iter(estado.estado_puertas))
    estado.estado_puertas[primera] = DoorState.ABIERTO if abierta else DoorState.CERRADO
    return estado


def _sen10(alarmas):
    """SEN-10 ACTIVA (resuelta sin reconocer ya no bloquea ni cuenta)."""
    from autoclave.state_machine.alarms.instancia import EstadoInstancia
    return any(i.codigo == SEN_10 and i.estado is EstadoInstancia.ACTIVA
               for i in alarmas.activas())


def test_coherencia_dispara_con_tres_lecturas():
    v, alarmas = _coherencia()
    estado = _estado_puerta(pres=150.0)
    v.update(estado); v.update(estado)
    assert not _sen10(alarmas)
    v.update(estado)
    assert _sen10(alarmas)


def test_coherencia_en_vacio_tambien_dispara():
    v, alarmas = _coherencia()
    estado = _estado_puerta(pres=60.0)
    for _ in range(3):
        v.update(estado)
    assert _sen10(alarmas)


def test_coherencia_despeja_con_tres_lecturas_coherentes():
    v, alarmas = _coherencia()
    estado = _estado_puerta(pres=150.0)
    for _ in range(3):
        v.update(estado)
    estado.sensores_pres["pres_camara"] = 101.0
    v.update(estado); v.update(estado)
    assert _sen10(alarmas)
    v.update(estado)
    assert not _sen10(alarmas)


def test_coherencia_una_lectura_coherente_reinicia_el_conteo():
    v, alarmas = _coherencia()
    estado = _estado_puerta(pres=150.0)
    v.update(estado); v.update(estado)
    estado.sensores_pres["pres_camara"] = 101.0
    v.update(estado)
    estado.sensores_pres["pres_camara"] = 150.0
    v.update(estado); v.update(estado)
    assert not _sen10(alarmas)


def test_coherencia_puerta_cerrada_no_dispara():
    v, alarmas = _coherencia()
    estado = _estado_puerta(abierta=False, pres=250.0)
    for _ in range(5):
        v.update(estado)
    assert not _sen10(alarmas)


def test_coherencia_dentro_de_la_banda_no_dispara():
    v, alarmas = _coherencia()
    estado = _estado_puerta(pres=105.0)          # atm 101.3 ± 5
    for _ in range(5):
        v.update(estado)
    assert not _sen10(alarmas)


def test_coherencia_sin_presion_no_se_evalua():
    v, alarmas = _coherencia()
    estado = _estado_puerta(pres=None)
    for _ in range(5):
        v.update(estado)
    assert not _sen10(alarmas)


def test_coherencia_no_actua_en_ciclo():
    v, alarmas = _coherencia()
    estado = _estado_puerta(pres=150.0)
    estado.set_machine_state(GlobalState.CICLO)
    for _ in range(5):
        v.update(estado)
    assert not _sen10(alarmas)
    # al salir de CICLO el conteo empieza de cero
    estado.set_machine_state(GlobalState.PREPARADO)
    v.update(estado); v.update(estado)
    assert not _sen10(alarmas)
    v.update(estado)
    assert _sen10(alarmas)


def test_coherencia_sin_datos_vigentes_no_cuenta():
    v, alarmas = _coherencia()
    estado = _estado_puerta(pres=150.0)
    for _ in range(5):
        v.update(estado, vigentes=False)
    assert not _sen10(alarmas)


def test_coherencia_reactiva_tras_reinicio_de_alarmas():
    """El reconocimiento de una FALLA resuelve todas las alarmas; si la
    incoherencia sigue, SEN-10 vuelve a aparecer."""
    v, alarmas = _coherencia()
    estado = _estado_puerta(pres=150.0)
    for _ in range(3):
        v.update(estado)
    alarmas.resolver_todas_por_reinicio()
    v.update(estado)
    assert _sen10(alarmas)


def test_coherencia_bloquea_el_inicio():
    v, alarmas = _coherencia()
    estado = _estado_puerta(pres=150.0)
    for _ in range(3):
        v.update(estado)
    assert alarmas.has_blocking_alarm() is True


def test_control_loop_evalua_la_coherencia_fuera_de_ciclo():
    alarmas = AlarmManager()
    loop = _loop(alarmas)
    loop.link.is_connected.return_value = True
    loop.link.edad_ultima_di.return_value = 0.1
    loop.units.get_all.return_value = {}
    loop.link.edad_ultima_ai.return_value = 0.1
    loop.estado.sensores_di["paro_emergencia"] = 1
    loop.estado.sensores_pres["pres_camara"] = 150.0
    primera = next(iter(loop.estado.estado_puertas))
    loop.estado.estado_puertas[primera] = DoorState.ABIERTO
    loop.estado.set_machine_state(GlobalState.PREPARADO)
    for _ in range(4):
        loop._tick()
    assert _sen10(alarmas)


def test_control_loop_no_evalua_la_coherencia_en_ciclo():
    alarmas = AlarmManager()
    loop = _loop(alarmas)
    loop.link.is_connected.return_value = True
    loop.link.edad_ultima_di.return_value = 0.1
    loop.units.get_all.return_value = {}
    loop.link.edad_ultima_ai.return_value = 0.1
    loop.estado.sensores_di["paro_emergencia"] = 1
    loop.estado.sensores_pres["pres_camara"] = 150.0
    primera = next(iter(loop.estado.estado_puertas))
    loop.estado.estado_puertas[primera] = DoorState.ABIERTO
    loop.estado.set_machine_state(GlobalState.CICLO)
    for _ in range(5):
        loop._tick()
    assert not _sen10(alarmas)


# ── D9-1.2: la causa llega a la UI ─────────────────────────────────────────

@pytest.mark.parametrize("causa", ["paro_liberado", "arranque", "fallo", "cancelado",
                                   "completado"])
def test_puente_publica_la_causa(causa):
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    d = UiBridge._seguridad_de({"estado_seguro": {"activo": True, "causa": causa}})
    assert d["es_causa"] == causa


def test_puente_causa_desconocida_o_ausente_es_vacia():
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    assert UiBridge._seguridad_de({})["es_causa"] == ""
    assert UiBridge._seguridad_de({"estado_seguro": {"causa": "otra"}})["es_causa"] == ""


@pytest.mark.parametrize("causa", ["arranque", "fallo", "cancelado", "completado"])
def test_textos_de_causa_en_los_dos_idiomas(causa):
    from autoclave import i18n
    for idioma in ("es", "en"):
        assert i18n.existe(f"sistema.estado_seguro_causa_{causa}", idioma)
    # nunca "paro liberado" si no hubo paro
    assert "liber" not in i18n.t(f"sistema.estado_seguro_causa_{causa}", "es").lower()


def test_status_publica_la_causa_y_sin_confirmacion():
    from tests.helpers.backend_doble import cargar_servidor
    ctx = MagicMock()
    loop = _loop()
    _arrancar(loop, pres=250.0)
    ctx.control_loop.estado_seguro = loop.estado_seguro
    srv, _ = cargar_servidor(ctx)
    d = modulo_backend("rutas.sistema")._estado_seguro_status()
    assert d["activo"] is True and d["causa"] == "arranque"
    assert d["requiere_confirmacion"] is False
