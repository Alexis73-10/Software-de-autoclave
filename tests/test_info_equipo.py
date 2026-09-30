# tests/test_info_equipo.py
#
# InfoEquipo (ui_qml/bridge/info_equipo.py): modelo/serie del perfil de
# instalación y filas del panel "Información del equipo".

import os
import sys
from datetime import datetime
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QSignalSpy

from autoclave.devices.puertas.door_type import DoorType
from autoclave.installation.equipment import EquipmentClass
from autoclave.installation.profile import InstallationProfile, Role
from autoclave.ui_qml.bridge import info_equipo as mod
from autoclave.ui_qml.bridge.info_equipo import InfoEquipo, filas_equipo


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


def _perfil():
    return InstallationProfile(
        machine_id="ACV-2026-SN1", model_id="SPK-AVH-450", serial_number="SN1",
        equipment_class=list(EquipmentClass)[0], door_count=2, door_type=list(DoorType)[0],
        cooling_level=3, door_id=1, role=Role.OPERATOR_FRONT,
        created_at=datetime(2026, 5, 25, 5, 49), locked=True,
    )


def _por_clave(filas):
    return {f["clave"]: f for f in filas}


def test_filas_con_perfil_e_historial():
    ultimo = {"numero_ciclo": 79, "fecha_inicio": "2026-08-06T10:22:00", "resultado": "COMPLETADO"}
    f = _por_clave(filas_equipo(_perfil(), 2, "0.5.0", [ultimo]))
    assert f["modelo"]["valor"] == "SPK-AVH-450"
    assert f["serie"]["valor"] == "SN1"
    assert f["id_maquina"]["valor"] == "ACV-2026-SN1"
    assert f["puertas"]["valor"] == "2"
    assert f["puerta_pantalla"]["valor"] == "2"
    assert f["enfriamiento"]["valor"] == "3"
    assert f["fecha_instalacion"]["valor"] == "2026-05-25"
    assert f["ciclos_realizados"]["valor"] == "79"
    assert f["ultimo_ciclo"]["valor"] == "2026-08-06 10:22  COMPLETADO"
    assert f["version_software"]["valor"] == "0.5.0"


def test_sin_fuente_en_el_software_se_marca_no_disponible():
    f = _por_clave(filas_equipo(_perfil(), 1, "0.5.0", []))
    assert f["ultimo_mantenimiento"]["disponible"] is False
    assert f["version_tarjeta"]["disponible"] is False
    assert all(v["disponible"] for k, v in f.items()
               if k not in ("ultimo_mantenimiento", "version_tarjeta"))


def test_historial_vacio_y_desconocido():
    f = _por_clave(filas_equipo(_perfil(), 1, "0.5.0", []))
    assert f["ciclos_realizados"]["valor"] == "0"
    assert f["ultimo_ciclo"]["valor"] is None
    f = _por_clave(filas_equipo(_perfil(), 1, "0.5.0", None))
    assert f["ciclos_realizados"]["valor"] is None


def test_sin_perfil_los_datos_quedan_desconocidos():
    f = _por_clave(filas_equipo(None, 1, None, None))
    assert f["modelo"]["valor"] is None
    assert f["version_software"]["valor"] is None
    assert f["puerta_pantalla"]["valor"] == "1"


def test_modelo_y_serie_del_perfil():
    info = InfoEquipo(_perfil(), 1, MagicMock(), "0.5.0")
    assert (info.modelo, info.serie) == ("SPK-AVH-450", "SN1")
    vacio = InfoEquipo(None, 1, MagicMock(), None)
    assert (vacio.modelo, vacio.serie) == ("", "")


def test_actualizar_consulta_el_historial_y_emite():
    backend = MagicMock()
    backend.get.return_value = [{"numero_ciclo": 5, "fecha_inicio": "x", "resultado": "FALLO"}]
    info = InfoEquipo(_perfil(), 1, backend, "0.5.0", ejecutar=lambda t: t())
    espia = QSignalSpy(info.filasChanged)
    info.actualizar()
    QCoreApplication.processEvents()
    backend.get.assert_called_once_with("/cycle/history", params={"limite": 1})
    assert _por_clave(info.filas)["ciclos_realizados"]["valor"] == "5"
    assert espia.count() == 1


def test_fallo_de_red_conserva_el_ultimo_historial():
    backend = MagicMock()
    backend.get.return_value = [{"numero_ciclo": 5, "fecha_inicio": "", "resultado": ""}]
    info = InfoEquipo(_perfil(), 1, backend, "0.5.0", ejecutar=lambda t: t())
    info.actualizar()
    QCoreApplication.processEvents()
    backend.get.side_effect = ConnectionError("sin backend")
    info.actualizar()
    QCoreApplication.processEvents()
    assert _por_clave(info.filas)["ciclos_realizados"]["valor"] == "5"


def test_cargar_perfil_tolera_errores(monkeypatch):
    from autoclave.installation import storage
    monkeypatch.setattr(storage, "exists", lambda: True)
    monkeypatch.setattr(storage, "load", lambda: (_ for _ in ()).throw(ValueError("corrupto")))
    assert mod.cargar_perfil() is None
    monkeypatch.setattr(storage, "exists", lambda: False)
    assert mod.cargar_perfil() is None
