"""T2 / P-5 (tanda 6): COM-02 y COM-03 NO se resuelven al salir de FALLA
(resolver_todas_por_reinicio); requieren despeje manual: el reconocimiento
explícito del operador (/alarms/{clave}/acknowledge). Reconocida fuera de
CICLO se resuelve en el acto; reconocida durante el ciclo, la resuelve el
reinicio siguiente. Las demás alarmas siguen como antes."""

from types import SimpleNamespace

import pytest

from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import CIC_03, COM_02, COM_03, SEN_02
from autoclave.state_machine.machine.enum_global import GlobalState


def _am(estado_maquina=GlobalState.FALLA):
    estado = SimpleNamespace(get_machine_state=lambda: estado_maquina[0])
    maquina = [estado_maquina]
    estado.get_machine_state = lambda: maquina[0]
    am = AlarmManager(estado)
    return am, maquina


def _activar_com(am):
    am.activar(COM_02, segundos=5.0, fase="Esterilización")
    am.activar(COM_03, causa="TARJETA_WATCHDOG", motivo="WD.", fase="Esterilización")


def _activas(am):
    return sorted(i.codigo for i in am.activas() if i.estado.name == "ACTIVA")


def test_reinicio_no_resuelve_com_02_ni_com_03_sin_reconocer():
    am, _ = _am()
    _activar_com(am)
    am.activar(CIC_03, motivo="x")
    am.resolver_todas_por_reinicio()
    assert _activas(am) == [COM_02, COM_03]
    assert am.has_blocking_alarm() is True             # con P-4 impiden iniciar


def test_reconocer_fuera_de_ciclo_las_despeja():
    am, _ = _am(GlobalState.PREPARACION)
    _activar_com(am)
    assert am.reconocer(COM_02, "operador") is True
    assert am.reconocer(COM_03, "operador") is True
    assert _activas(am) == []
    assert am.obtener(COM_02) is None and am.obtener(COM_03) is None
    assert am.has_blocking_alarm() is False


def test_reconocida_en_ciclo_no_se_despeja_hasta_el_reinicio():
    am, maquina = _am(GlobalState.CICLO)
    _activar_com(am)
    am.reconocer(COM_03, "operador")
    assert _activas(am) == [COM_02, COM_03]            # en CICLO sigue activa
    maquina[0] = GlobalState.FALLA
    am.resolver_todas_por_reinicio()
    assert _activas(am) == [COM_02]                    # COM-03 ya reconocida: se resuelve


@pytest.mark.parametrize("codigo,valores", [(SEN_02, {"sensores": "s", "fase": "f"}),
                                            (CIC_03, {"motivo": "m"})])
def test_las_demas_alarmas_siguen_resolviendose_por_reinicio(codigo, valores):
    am, _ = _am()
    am.activar(codigo, **valores)
    am.resolver_todas_por_reinicio()
    assert _activas(am) == []


def test_reconocer_otra_alarma_no_la_resuelve():
    am, _ = _am(GlobalState.PREPARACION)
    am.activar(CIC_03, motivo="m")
    am.reconocer(CIC_03, "operador")
    assert _activas(am) == [CIC_03]


def test_sin_estado_reconocer_despeja():
    am = AlarmManager()
    _activar_com(am)
    am.reconocer(COM_02, "operador")
    assert am.obtener(COM_02) is None


# ── Puente QML y cliente: botón DESPEJAR del panel de notificaciones ──────

def test_comandos_sistema_despejar_alarma_envia_el_reconocimiento():
    from unittest.mock import MagicMock
    from autoclave.ui_qml.bridge.comandos_sistema import ComandosSistema
    puente = MagicMock()
    puente.connected = True
    ui = MagicMock()
    ui.reconocer_alarma.return_value = (True, "")
    c = ComandosSistema(puente, ui, 1, ejecutar=lambda tarea: tarea())
    c.despejarAlarma("COM-03|TARJETA_WATCHDOG")
    ui.reconocer_alarma.assert_called_once_with("COM-03|TARJETA_WATCHDOG", "operador")
    c.despejarAlarma("")
    assert ui.reconocer_alarma.call_count == 1


def test_cliente_codifica_la_clave_en_la_ruta():
    from unittest.mock import MagicMock
    from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
    ui = UIServiceBackend.__new__(UIServiceBackend)
    ui.backend = MagicMock()
    assert ui.reconocer_alarma("COM-03|X", "operador") == (True, "")
    ui.backend.post.assert_called_once_with(path="/alarms/COM-03%7CX/acknowledge",
                                            body={"usuario": "operador"})


def test_panel_notificaciones_marca_despejables():
    texto = (__import__("pathlib").Path(__file__).resolve().parents[1] / "src" / "autoclave"
             / "ui_qml" / "qml" / "Componentes" / "PanelNotificaciones.qml").read_text(encoding="utf-8")
    assert 'startsWith("COM-02")' in texto and 'startsWith("COM-03")' in texto
    assert "despejarAlarma(model.id)" in texto
