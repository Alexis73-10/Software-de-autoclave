# tests/test_ui_bridge.py
#
# UiBridge (ui_qml/bridge/ui_bridge.py): puente de solo lectura entre el caché
# de UIServiceBackend y QML. Backend simulado con MagicMock; el QTimer no se
# arranca (iniciar=False) y cada "tick" se simula llamando refrescar().

import os
import sys
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication, QModelIndex
from PySide6.QtTest import QSignalSpy

from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
from autoclave.ui_qml.bridge.ui_bridge import AlarmListModel, UiBridge, prioridad_de
from autoclave.ui_qml.domain.pantalla_ciclo import SIN_DATO


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


def _servicio(connected=True, estado="PREPARADO", puertas=None, alarmas=None,
              ciclo=None, temp=None, pres=None, listo=False):
    """UIServiceBackend simulado: solo los getters de caché que usa el puente."""
    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = connected
    ui.get_estado_global.return_value = estado
    ui.get_estado_flag.side_effect = lambda flag: listo if flag == "LISTO_PARA_CICLO" else None
    puertas = {"Puerta 1": "CERRADO", "Puerta 2": "ABIERTO"} if puertas is None else puertas
    ui.get_estado_puerta.side_effect = lambda nombre: puertas.get(nombre)
    ui.get_alarmas.return_value = [] if alarmas is None else alarmas
    ui.get_cycle.return_value = {} if ciclo is None else ciclo
    ui.get_sensores_temp.return_value = {"temp_camara": temp}
    ui.get_sensores_pres.return_value = {"pres_camara": pres}
    return ui


def _alarma(id_="CHAQUETA_FRIA", level="FALLA", description="Chaqueta fría", source_state="PREPARADO"):
    return {"id": id_, "level": level, "description": description, "source_state": source_state}


def _filas(modelo: AlarmListModel):
    roles = modelo.roleNames()
    return [
        {bytes(nombre).decode(): modelo.data(modelo.index(r, 0), rol) for rol, nombre in roles.items()}
        for r in range(modelo.rowCount())
    ]


# ── estado inicial y temporizador ─────────────────────────────────────────

def test_estado_inicial_sin_leer_cache():
    puente = UiBridge(_servicio(), door=1, iniciar=False)
    assert puente.connected is False
    assert puente.machineState == "DESCONOCIDO"
    assert puente.doorState == "DESCONOCIDO"
    assert puente.alarms.count == 0
    assert puente.programa == SIN_DATO


def test_temporizador_de_500_ms_en_el_hilo_de_la_gui():
    puente = UiBridge(_servicio(), door=1)
    try:
        assert puente._timer.interval() == 500
        assert puente._timer.isActive()
        assert puente._timer.thread() is QCoreApplication.instance().thread()
    finally:
        puente.detener()


def test_primer_refresco_publica_el_cache():
    ui = _servicio(temp=134.2, pres=304.0,
                   ciclo={"name": "Bowie", "parameters": {
                       "esterilizacion": {"temperatura_esterilizacion": {"value": 134},
                                          "tiempo_esterilizacion": {"value": 3.5}},
                       "secado": {"tiempo_secado": {"value": 15}}}})
    puente = UiBridge(ui, door=1, iniciar=False)
    puente.refrescar()
    assert puente.connected is True
    assert puente.machineState == "PREPARADO"
    assert puente.doorState == "CERRADO"
    assert puente.programa == "BOWIE"
    assert puente.tempEsterilizacion == "134,0"
    assert puente.tiempoEsterilizacion == "3,5"
    assert puente.tiempoSecado == "15"
    assert puente.tempCamara == "134,2"
    assert puente.presionCamara == "304,0"


# ── conexión perdida / recuperada ─────────────────────────────────────────

def test_conexion_perdida_y_recuperada_emite_solo_en_cada_cambio():
    ui = _servicio(connected=True)
    puente = UiBridge(ui, door=1, iniciar=False)
    espia = QSignalSpy(puente.connectedChanged)

    puente.refrescar()
    puente.refrescar()                      # sin cambio: no re-emite
    assert puente.connected is True
    assert espia.count() == 1

    ui.connected = False                    # conexión perdida
    puente.refrescar()
    assert puente.connected is False
    assert espia.count() == 2

    ui.connected = True                     # conexión recuperada
    puente.refrescar()
    assert puente.connected is True
    assert espia.count() == 3


def test_sin_conexion_conserva_los_ultimos_valores():
    ui = _servicio(connected=True, alarmas=[_alarma()], temp=134.0)
    puente = UiBridge(ui, door=1, iniciar=False)
    puente.refrescar()

    # UIServiceBackend conserva el último /status al perder la conexión
    ui.connected = False
    puente.refrescar()
    assert puente.connected is False
    assert puente.doorState == "CERRADO"
    assert puente.tempCamara == "134,0"
    assert puente.alarms.count == 1


# ── puerta ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("door, esperado", [(1, "CERRADO"), (2, "ABIERTO")])
def test_door_state_es_el_de_la_puerta_de_esta_ventana(door, esperado):
    ui = _servicio()
    puente = UiBridge(ui, door=door, iniciar=False)
    puente.refrescar()
    assert puente.door == door
    assert puente.doorState == esperado
    ui.get_estado_puerta.assert_called_with(f"Puerta {door}")


def test_cambio_de_puerta_emite_una_vez_por_cambio():
    puertas = {"Puerta 1": "CERRADO"}
    puente = UiBridge(_servicio(puertas=puertas), door=1, iniciar=False)
    espia = QSignalSpy(puente.doorStateChanged)

    puente.refrescar()
    puertas["Puerta 1"] = "ABRIENDO"
    puente.refrescar()
    puertas["Puerta 1"] = "ABIERTO"
    puente.refrescar()
    puente.refrescar()

    assert puente.doorState == "ABIERTO"
    assert espia.count() == 3


def test_puerta_ausente_en_cache_es_desconocido():
    puente = UiBridge(_servicio(puertas={}), door=2, iniciar=False)
    puente.refrescar()
    assert puente.doorState == "DESCONOCIDO"


def test_cambio_de_machine_state():
    ui = _servicio(estado="PREPARACION")
    puente = UiBridge(ui, door=1, iniciar=False)
    espia = QSignalSpy(puente.machineStateChanged)
    puente.refrescar()
    ui.get_estado_global.return_value = "PREPARADO"
    puente.refrescar()
    puente.refrescar()
    assert puente.machineState == "PREPARADO"
    assert espia.count() == 2


# ── alarmas ───────────────────────────────────────────────────────────────

def test_modelo_de_alarmas_expone_los_roles_pedidos():
    ui = _servicio(alarmas=[_alarma()])
    puente = UiBridge(ui, door=1, iniciar=False)
    puente.refrescar()
    assert _filas(puente.alarms) == [{
        "id": "CHAQUETA_FRIA", "level": "FALLA", "description": "Chaqueta fría",
        "source_state": "PREPARADO", "priority": "media",
    }]


def test_cambio_de_alarmas_reinicia_el_modelo_solo_si_cambian():
    ui = _servicio(alarmas=[])
    puente = UiBridge(ui, door=1, iniciar=False)
    reinicios = QSignalSpy(puente.alarms.modelReset)
    conteo = QSignalSpy(puente.alarms.countChanged)

    puente.refrescar()
    assert reinicios.count() == 0          # [] -> []: sin cambio

    ui.get_alarmas.return_value = [_alarma(), _alarma("PARO_EMERGENCIA", "EMERGENCIA", "Paro")]
    puente.refrescar()
    puente.refrescar()
    assert puente.alarms.count == 2
    assert reinicios.count() == 1
    assert conteo.count() == 1

    ui.get_alarmas.return_value = [_alarma(description="Otra descripción"), _alarma("PARO_EMERGENCIA", "EMERGENCIA", "Paro")]
    puente.refrescar()
    assert reinicios.count() == 2
    assert conteo.count() == 1             # mismo número de filas

    ui.get_alarmas.return_value = []
    puente.refrescar()
    assert puente.alarms.count == 0
    assert conteo.count() == 2


def test_alarmas_mal_formadas_se_descartan_o_completan():
    modelo = AlarmListModel()
    modelo.establecer([None, "texto", {"id": "X"}])
    assert _filas(modelo) == [{"id": "X", "level": "", "description": "",
                               "source_state": "", "priority": "alta"}]
    assert modelo.establecer("no es lista") is True
    assert modelo.count == 0


def test_data_fuera_de_rango_devuelve_none():
    modelo = AlarmListModel()
    modelo.establecer([_alarma()])
    assert modelo.data(modelo.index(5, 0), AlarmListModel.IdRole) is None
    assert modelo.rowCount(modelo.index(0, 0)) == 0
    assert modelo.rowCount(QModelIndex()) == 1


@pytest.mark.parametrize("nivel, prioridad", [
    ("EMERGENCIA", "alta"), ("FALLA", "media"), ("ALERTA", "baja"),
    ("DESCONOCIDO", "alta"), ("", "alta"), (None, "alta"),
])
def test_prioridad_iec_60601_1_8(nivel, prioridad):
    assert prioridad_de(nivel) == prioridad


# ── solo lectura ──────────────────────────────────────────────────────────

def test_el_puente_no_envia_comandos_ni_hace_red():
    ui = _servicio(alarmas=[_alarma()])
    puente = UiBridge(ui, door=1, iniciar=False)
    for _ in range(3):
        puente.refrescar()
    usados = {c[0] for c in ui.method_calls}
    assert usados <= {"get_estado_global", "get_estado_puerta", "get_estado_flag", "get_alarmas",
                      "get_cycle", "get_sensores_temp", "get_sensores_pres"}


# ── número de ciclo, puerta abierta y estado del equipo ───────────────────

@pytest.mark.parametrize("ciclo, esperado", [
    ({"name": "Bowe", "number": 1}, "01"),
    ({"name": "X", "number": 12}, "12"),
    ({"name": "Sin número"}, SIN_DATO),
    ({"name": "Repetido", "number": None}, SIN_DATO),
    ({}, SIN_DATO),
])
def test_ciclo_activo_es_el_numero_del_ciclo(ciclo, esperado):
    puente = UiBridge(_servicio(ciclo=ciclo), door=1, iniciar=False)
    puente.refrescar()
    assert puente.cicloActivo == esperado


@pytest.mark.parametrize("estado, abierta", [
    ("ABIERTO", True), ("ABRIENDO", True),
    ("CERRADO", False), ("CERRANDO", False), ("ATRAPADA", False),
    ("ERROR", False), ("DESCONOCIDO", False),
])
def test_door_open_sigue_la_regla_del_boton(estado, abierta):
    puente = UiBridge(_servicio(puertas={"Puerta 1": estado}), door=1, iniciar=False)
    puente.refrescar()
    assert puente.doorOpen is abierta


@pytest.mark.parametrize("machine_state, listo, clave", [
    ("CICLO", False, "ejecutando"),
    ("FALLA", False, "fallo"),
    ("PREPARADO", True, "listo"),
    ("PREPARADO", False, "no_preparado"),
    ("PREPARACION", True, "no_preparado"),
    ("EMERGENCIA", False, "no_preparado"),
    ("DESCONOCIDO", False, "no_preparado"),
])
def test_estado_equipo(machine_state, listo, clave):
    puente = UiBridge(_servicio(estado=machine_state, listo=listo), door=1, iniciar=False)
    espia = QSignalSpy(puente.estadoEquipoChanged)
    puente.refrescar()
    assert puente.estadoEquipo == clave
    assert espia.count() == (0 if clave == "no_preparado" else 1)


def test_listo_para_ciclo_sigue_la_bandera_del_backend():
    ui = _servicio(listo=False)
    puente = UiBridge(ui, door=1, iniciar=False)
    espia = QSignalSpy(puente.listoParaCicloChanged)
    puente.refrescar()
    assert puente.listoParaCiclo is False
    ui.get_estado_flag.side_effect = lambda flag: flag == "LISTO_PARA_CICLO"
    puente.refrescar()
    puente.refrescar()
    assert puente.listoParaCiclo is True
    assert espia.count() == 1
