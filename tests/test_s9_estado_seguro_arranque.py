"""S9 (tanda 9, D9-1): bloqueos al arrancar y coherencia puerta-presión.

Hotfix ES (6-nov-2026): el protocolo de estado seguro al arrancar (D9-1.1,
D9-1.2 salvo el paro, D9-1.4) se retiró; sus pruebas se quitaron (lista en
docs/informes/hotfix_estado_seguro/R_informe.md) y lo nuevo está en
tests/test_hotfix_es_retiro.py. Quedan:
- D9-1.3: modo prueba y cambio de programa con la recuperación pendiente.
- D9-1.6: coherencia puerta-presión (SEN-10).
- Los ayudantes (_loop, _arrancar, _programa...) que usan otras pruebas.
"""

from tests.helpers.arranque_doble import evento_liberado  # H3 (tanda 26)
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
        loop = ControlLoop(arranque_liberado=evento_liberado(), units=MagicMock(), door_service=MagicMock(), doors=[],
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
        loop.estado_seguro.update()


def _abiertas(set_do):
    return {c[0] for c in set_do.method_calls if c[0].endswith("_on")}


# ── D9-1.1 / D9-1.2: el protocolo de arranque corre solo ───────────────────



# ── D9-1.4: sin presión de cámara ──────────────────────────────────────────



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



def test_modo_prueba_permitido_con_recuperacion_pendiente():
    loop = _loop()
    loop.estado.set_flag("PARO_EMERGENCIA", False)
    loop.recuperar_ciclo_interrumpido(_programa())
    ok, _ = loop.enter_test_mode()
    assert ok is True


@patch("autoclave.services.domain.loop.control_loop.StateMachine")
def test_cambio_de_programa_permitido_con_recuperacion_pendiente(_sm):
    loop = _loop()
    loop.recuperar_ciclo_interrumpido(_programa())
    assert loop.set_active_cycle(_programa("otro"))[0] is True


def test_programas_para_seguridad_en_ciclo_no_cambia():
    loop = _loop()
    loop.estado.set_machine_state(GlobalState.CICLO)
    loop.state_machine.ciclo.programa_en_curso = "copia"
    assert loop.programas_para_seguridad() == ["copia"]


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


