# tests/test_comandos_puerta.py
#
# ComandosPuerta (ui_qml/bridge/comandos_puerta.py): botón de puerta de la UI
# QML. DoorCommandService simulado; el "hilo" se inyecta para controlar cuándo
# termina la petición.

import os
import sys
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QSignalSpy

from autoclave.services.domain.puertas.door_command_service import DoorCommandService
from autoclave.ui_qml.bridge.comandos_puerta import ComandosPuerta


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


class _Puente:
    def __init__(self, door=1, abierta=False, connected=True):
        self.door = door
        self.doorOpen = abierta
        self.doorState = "ABIERTO" if abierta else "CERRADO"
        self.connected = connected


class _EjecutorManual:
    """Guarda la tarea; correr() simula que el hilo de trabajo termina."""
    def __init__(self):
        self.tareas = []

    def __call__(self, tarea):
        self.tareas.append(tarea)

    def correr(self):
        self.tareas.pop(0)()
        QCoreApplication.processEvents()


def _comandos(respuesta=(True, "")):
    cmd = MagicMock(spec=DoorCommandService)
    cmd.open.return_value = respuesta
    cmd.close.return_value = respuesta
    return cmd


def test_puerta_cerrada_envia_abrir_a_la_puerta_de_esta_ventana():
    cmd, ejecutor = _comandos(), _EjecutorManual()
    comandos = ComandosPuerta(_Puente(door=2, abierta=False), cmd, ejecutar=ejecutor)
    comandos.alternar()
    ejecutor.correr()
    cmd.open.assert_called_once_with("Puerta 2")
    cmd.close.assert_not_called()


def test_puerta_abierta_envia_cerrar():
    cmd, ejecutor = _comandos(), _EjecutorManual()
    comandos = ComandosPuerta(_Puente(door=1, abierta=True), cmd, ejecutar=ejecutor)
    comandos.alternar()
    ejecutor.correr()
    cmd.close.assert_called_once_with("Puerta 1")
    cmd.open.assert_not_called()


def test_ocupado_mientras_el_comando_esta_en_curso_e_ignora_otro_toque():
    cmd, ejecutor = _comandos(), _EjecutorManual()
    comandos = ComandosPuerta(_Puente(), cmd, ejecutar=ejecutor)
    espia = QSignalSpy(comandos.ocupadoChanged)

    comandos.alternar()
    assert comandos.ocupado is True
    comandos.alternar()                    # segundo toque: se ignora
    assert len(ejecutor.tareas) == 1

    ejecutor.correr()
    assert comandos.ocupado is False
    assert espia.count() == 2
    assert cmd.open.call_count == 1


def test_sin_conexion_no_envia_nada():
    cmd, ejecutor = _comandos(), _EjecutorManual()
    comandos = ComandosPuerta(_Puente(connected=False), cmd, ejecutar=ejecutor)
    comandos.alternar()
    assert ejecutor.tareas == []
    assert comandos.ocupado is False


def test_rechazo_publica_el_motivo_y_se_borra_solo():
    cmd, ejecutor = _comandos((False, "Ciclo en curso")), _EjecutorManual()
    comandos = ComandosPuerta(_Puente(), cmd, ejecutar=ejecutor, duracion_mensaje_ms=10)
    comandos.alternar()
    ejecutor.correr()
    assert comandos.mensaje == "Ciclo en curso"
    assert comandos._timer_mensaje.isActive()

    comandos._timer_mensaje.timeout.emit()
    assert comandos.mensaje == ""


def test_nuevo_comando_borra_el_mensaje_anterior():
    cmd, ejecutor = _comandos((False, "Rechazado")), _EjecutorManual()
    comandos = ComandosPuerta(_Puente(), cmd, ejecutar=ejecutor)
    comandos.alternar()
    ejecutor.correr()
    assert comandos.mensaje == "Rechazado"

    cmd.open.return_value = (True, "")
    comandos.alternar()
    assert comandos.mensaje == ""
    ejecutor.correr()
    assert comandos.mensaje == ""


def test_excepcion_del_servicio_se_trata_como_rechazo():
    cmd, ejecutor = _comandos(), _EjecutorManual()
    cmd.open.side_effect = RuntimeError("fallo inesperado")
    comandos = ComandosPuerta(_Puente(), cmd, ejecutar=ejecutor)
    comandos.alternar()
    ejecutor.correr()
    assert comandos.ocupado is False
    assert comandos.mensaje == "fallo inesperado"


def test_hilo_real_devuelve_el_resultado_al_hilo_de_la_gui():
    cmd = _comandos((False, "Puerta bloqueada"))
    comandos = ComandosPuerta(_Puente(), cmd)   # ejecutor por defecto: threading.Thread
    espia = QSignalSpy(comandos.ocupadoChanged)
    comandos.alternar()
    assert espia.wait(2000) or espia.count() >= 2
    for _ in range(50):
        if not comandos.ocupado:
            break
        espia.wait(20)
    assert comandos.ocupado is False
    assert comandos.mensaje == "Puerta bloqueada"
