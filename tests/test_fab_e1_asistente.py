"""Modo fábrica, Etapa 1 (DF-02): el asistente de instalación deja el equipo en
FÁBRICA solo con un código de primera instalación (INS/INSA; SAF-04: un v1 ya no) sobre una
base sin uso; con REI/REIA, o con una base ya usada, queda en ENTREGADO. Un
error no deshace la instalación."""
import sys
from unittest.mock import MagicMock

import pytest

from autoclave.installation.activacion_v2 import ResultadoCodigo
from autoclave.services.domain.logging.db_manager import DbManager
from tests.helpers import codigo_doble

pytestmark = pytest.mark.req("DF-02", "FAB-03")

VALIDAS = {"clave_admin": "admin-nueva-1", "confirmacion_admin": "admin-nueva-1",
           "clave_ingeniero": "inge-nueva-1", "confirmacion_ingeniero": "inge-nueva-1"}


def _datos(**cambios):
    d = {"serial_number": "ab-123", "equipment_class": "piso_lab",
         "door_count": 2, "door_type": "advanced", "door_id": 2, "cooling_level": 2,
         "vapor_source": "generator", "supply_inputs": {}, "temperature_probes": {},
         "capacidad_litros": 45, "tipo_carga": "V", "contrasenas": VALIDAS}
    d.update(cambios)
    return d


@pytest.fixture
def pi(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.installation import storage
    from autoclave.ui_qml.bridge import puente_instalacion as modulo
    monkeypatch.setattr(storage, "INSTALLATION_FILE", tmp_path / "installation_profile.json")
    return modulo


def _instalar(pi, tmp_path, verificador):
    ruta = tmp_path / "autoclave.db"
    p = pi.PuenteInstalacion(verificar_codigo=verificador, abrir_bd=lambda: DbManager(ruta),
                             es_semilla=lambda _c: False)
    assert p.validarCodigo("ab-123", "X", "fabricacion", "", "") == ""
    assert p.instalar(_datos()) == {"ok": True, "error": ""}
    db = DbManager(ruta)
    try:
        return db.estado_fabrica(), [f["evento"] for f in db.get_auditoria(limite=50)]
    finally:
        db.close()


@pytest.mark.parametrize("resultado, esperado", [
    (ResultadoCodigo(ok=True, formato="v1"), False),     # corrección SAF-04
    (ResultadoCodigo(ok=True, formato="v2", tipo="INS"), True),
    (ResultadoCodigo(ok=True, formato="v2", tipo="INS", originales=("S", "M")), True),  # INSA
    (ResultadoCodigo(ok=True, formato="v2", tipo="REI"), False),
    (ResultadoCodigo(ok=True, formato="v2", tipo="REI", originales=("S", "M")), False),  # REIA
    (ResultadoCodigo(ok=False, motivo="etiqueta", formato="v2", tipo="INS"), False),
    (ResultadoCodigo(ok=True, formato="v2", tipo=None), False),
    (None, False),
])
def test_es_primera_instalacion(pi, resultado, esperado):
    assert pi.es_primera_instalacion(resultado) is esperado


def test_instalacion_con_ins_entra_en_fabrica(pi, tmp_path):
    estado, eventos = _instalar(pi, tmp_path, codigo_doble.acepta(tipo="INS"))
    assert estado == "FABRICA"
    assert eventos == ["equipo_instalado"]


def test_instalacion_con_v1_queda_entregado(pi, tmp_path):
    # corrección SAF-04 de la revisión de seguridad: un v1 no es primera instalación
    def v1(serial, codigo, modo=None, *a, hoy=None, **k):
        return ResultadoCodigo(ok=True, formato="v1")
    estado, eventos = _instalar(pi, tmp_path, v1)
    assert estado == "ENTREGADO" and eventos == ["equipo_instalado"]


def test_reinstalacion_con_rei_queda_entregado(pi, tmp_path):
    estado, eventos = _instalar(pi, tmp_path, codigo_doble.acepta(tipo="REI"))
    assert estado == "ENTREGADO"
    assert eventos == ["equipo_instalado"]


def test_base_con_ciclos_queda_entregado_aun_con_ins(pi, tmp_path):
    db = DbManager(tmp_path / "autoclave.db")
    try:
        db.crear_ciclo(1, "P", "P", 121.0, 15.0, "AE-45", "SN1", "x")
    finally:
        db.close()
    estado, eventos = _instalar(pi, tmp_path, codigo_doble.acepta(tipo="INS"))
    assert estado == "ENTREGADO" and eventos == ["equipo_instalado"]


def test_registrar_equipo_instalado_por_defecto_no_entra(pi, tmp_path):
    perfil = MagicMock(serial_number="S-1", model_id="AE-45", tipo_instalacion="fabricacion",
                      serial_original=None, modelo_original=None)
    ruta = tmp_path / "a.db"
    assert pi.registrar_equipo_instalado(perfil, abrir_bd=lambda: DbManager(ruta),
                                         zona=lambda: "Z") == "ENTREGADO"
    assert pi.registrar_equipo_instalado.__defaults__[-1] is False


def test_registrar_equipo_instalado_no_lanza_y_da_entregado(pi):
    def falla():
        raise RuntimeError("bd")
    perfil = MagicMock(serial_number="S", model_id="M", tipo_instalacion="fabricacion")
    assert pi.registrar_equipo_instalado(perfil, abrir_bd=falla, zona=lambda: "",
                                         primera_instalacion=True) == "ENTREGADO"


def test_error_al_entrar_no_deshace_la_instalacion(pi, tmp_path, monkeypatch):
    monkeypatch.setattr(DbManager, "entrar_modo_fabrica_e_instalar",
                        MagicMock(side_effect=RuntimeError("falla")))
    ruta = tmp_path / "autoclave.db"
    p = pi.PuenteInstalacion(verificar_codigo=codigo_doble.acepta(), abrir_bd=lambda: DbManager(ruta),
                             es_semilla=lambda _c: False)
    assert p.validarCodigo("ab-123", "X", "fabricacion", "", "") == ""
    assert p.instalar(_datos()) == {"ok": True, "error": ""}
    from autoclave.installation import storage
    assert storage.exists()
