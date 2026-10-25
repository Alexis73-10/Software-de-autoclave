"""T7 (E5, tanda 2026-10-14): NO ABRIR, paro, estado seguro y modo prueba en
el puente QML; comandos "Confirmar y llevar a estado seguro" y "Apagar equipo"."""

import os
import sys
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication

from autoclave.cliente.ui_service_backend import UIServiceBackend
from autoclave.ui_qml.bridge.comandos_sistema import ComandosSistema
from autoclave.ui_qml.bridge.ui_bridge import UiBridge


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


def _servicio(connected=True, status=None, paro=False):
    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = connected
    ui.get_estado_global.return_value = "PREPARADO"
    ui.get_estado_flag.side_effect = lambda f: paro if f in ("PARO_EMERGENCIA", "PARO_REAL") else None  # U4: paro real
    ui.get_estado_puerta.return_value = "CERRADO"
    ui.get_alarmas.return_value = []
    ui.get_cycle.return_value = {}
    ui.get_sensores_temp.return_value = {}
    ui.get_sensores_pres.return_value = {}
    status = status or {}
    ui.get_campo.side_effect = lambda k, d=None: status.get(k, d)
    return ui


def _puente(**kw):
    p = UiBridge(_servicio(**kw), door=1, iniciar=False)
    p.refrescar()
    return p


def test_camara_segura_sin_no_abrir():
    p = _puente(status={"no_abrir": False, "camara_segura_motivo": ""})
    assert p.noAbrir is False and p.noAbrirMotivo == ""


def test_no_abrir_con_motivo():
    p = _puente(status={"no_abrir": True, "camara_segura_motivo": "Temperatura demasiado alta (95 °C)"})
    assert p.noAbrir is True and "95" in p.noAbrirMotivo


@pytest.mark.parametrize("status", [{}, {"no_abrir": None}])
def test_sin_dato_es_no_abrir(status):
    assert _puente(status=status).noAbrir is True


def test_sin_conexion_es_no_abrir():
    assert _puente(connected=False, status={"no_abrir": False}).noAbrir is True


def test_modo_prueba_paro_y_estado_seguro():
    p = _puente(paro=True, status={"test_mode_active": True,
                                   "estado_seguro": {"activo": True, "requiere_confirmacion": True}})
    assert p.modoPrueba and p.paroActivo
    assert p.estadoSeguroActivo and p.estadoSeguroRequiereConfirmacion


# ── ComandosSistema ─────────────────────────────────────────────────────────

def _comandos(door=1, requiere=True):
    puente = MagicMock()
    puente.connected = True
    puente.estadoSeguroRequiereConfirmacion = requiere
    ui = MagicMock()
    ui.confirmar_estado_seguro.return_value = True
    ui.apagar_equipo.return_value = (False, "Temperatura demasiado alta (95 °C)")
    return ComandosSistema(puente, ui, door, ejecutar=lambda tarea: tarea()), ui


def test_confirmar_estado_seguro_llama_al_backend():
    c, ui = _comandos()
    c.confirmarEstadoSeguro()
    ui.confirmar_estado_seguro.assert_called_once()
    assert c.ocupado is False


def test_confirmar_no_hace_nada_si_no_hace_falta():
    c, ui = _comandos(requiere=False)
    c.confirmarEstadoSeguro()
    ui.confirmar_estado_seguro.assert_not_called()


def test_apagar_solo_desde_la_ventana_principal():
    c, ui = _comandos(door=2)
    assert c.ventanaPrincipal is False
    c.apagarEquipo()
    ui.apagar_equipo.assert_not_called()


def test_apagar_rechazado_muestra_el_motivo():
    c, ui = _comandos()
    c.apagarEquipo()
    ui.apagar_equipo.assert_called_once_with("principal")
    assert "95" in c.mensaje


def test_apagado_aceptado_deja_el_boton_deshabilitado():
    """TMG-06 de T7: tras un apagado aceptado no se puede volver a pulsar."""
    c, ui = _comandos()
    ui.apagar_equipo.return_value = (True, "")
    c.apagarEquipo()
    assert c.ocupado is True
    c.apagarEquipo()
    ui.apagar_equipo.assert_called_once()


# ── A1 (tanda 3): aviso de cámara no segura y apagado en cualquier estado ──

def test_camara_no_segura_sigue_al_puente():
    c, _ = _comandos()
    c._puente.noAbrir = True
    assert c.camaraNoSegura is True
    c._puente.noAbrir = False
    assert c.camaraNoSegura is False


def test_camara_no_segura_falla_cerrada_sin_dato():
    c, _ = _comandos()
    c._puente.noAbrir = None
    assert c.camaraNoSegura is True


def test_apagar_se_envia_aunque_la_camara_no_sea_segura():
    c, ui = _comandos()
    c._puente.noAbrir = True
    ui.apagar_equipo.return_value = (True, "")
    c.apagarEquipo()
    ui.apagar_equipo.assert_called_once_with("principal")
