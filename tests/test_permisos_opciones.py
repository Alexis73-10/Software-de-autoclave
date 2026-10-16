# tests/test_permisos_opciones.py
#
# puedeVer de OPCIONES (planeacion_opciones_parametros_ciclo.md, U-7 y §8): una
# prueba por rol y por entrada, orden de la navegación lateral y estados en que
# la edición se permite (U-8).

import pytest

from autoclave.ui_pyside.services.roles import VALORES_ROL
from autoclave.ui_qml.domain.permisos_opciones import (
    SECCIONES, edicion_permitida, puede_ver, secciones_visibles,
)

_TECNICAS = ["parametros_ciclo", "parametros_sistema", "entradas_salidas",
             "mantenimiento", "opciones_avanzadas"]
_ADMIN = ["usuarios", "conectividad"]

_ESPERADO = {
    "admin":     _ADMIN,
    # Conectividad también para técnico e ingeniero (tanda 2026-10-14 §1.6)
    "tecnico":   _TECNICAS + ["conectividad"],
    "biomedico": [],      # rol eliminado (planeacion_backend_autenticacion.md, decisión 25)
    # Usuarios también para el ingeniero (Cristian, 2026-10-08; T-8, R3-5)
    "ingeniero": _TECNICAS + _ADMIN,
    "operador":  [],      # defecto de la tabla usuarios, fuera de roles.py
    "":          [],
    None:        [],
}


def test_orden_de_la_navegacion():
    # U-2: las cinco de AdminMenuView._OPTIONS en su orden; al final las de admin
    assert [s.clave for s in SECCIONES] == _TECNICAS + _ADMIN


def test_los_roles_de_la_politica_existen():
    for s in SECCIONES:
        assert s.roles <= VALORES_ROL


@pytest.mark.parametrize("rol", list(_ESPERADO))
@pytest.mark.parametrize("seccion", _TECNICAS + _ADMIN)
def test_puede_ver_por_rol_y_entrada(rol, seccion):
    assert puede_ver(seccion, rol) is (seccion in _ESPERADO[rol])


@pytest.mark.parametrize("rol", list(_ESPERADO))
def test_secciones_visibles(rol):
    assert [s.clave for s in secciones_visibles(rol)] == _ESPERADO[rol]


def test_seccion_desconocida_no_se_ve():
    assert puede_ver("general", "tecnico") is False


# Tanda 2026-10-14 §1.6: técnico en cualquier estado distinto de CICLO,
# alineado con el guard DISTINTO_DE_CICLO del backend
@pytest.mark.parametrize("estado,permitida", [
    ("PREPARACION", True), ("PREPARADO", True),
    ("CICLO", False), ("FALLA", True), ("EMERGENCIA", True),
    ("DESCONOCIDO", False), ("", False), (None, False),
])
def test_edicion_permitida(estado, permitida):
    assert edicion_permitida(estado) is permitida


# Excepción (Cristian, 2026-10-07): el ingeniero modifica cualquier sección en
# cualquier estado; técnico y admin solo en PREPARACION / PREPARADO.
@pytest.mark.parametrize("estado,rol,seccion,permitida", [
    ("CICLO", "ingeniero", "parametros_ciclo", True),
    ("CICLO", "ingeniero", "parametros_sistema", True),
    ("FALLA", "ingeniero", "mantenimiento", True),
    ("EMERGENCIA", "ingeniero", "parametros_ciclo", True),
    ("CICLO", "tecnico", "parametros_ciclo", False),
    ("CICLO", "admin", "usuarios", False),
    ("PREPARADO", "tecnico", "parametros_sistema", True),
])
def test_edicion_permitida_por_rol(estado, rol, seccion, permitida):
    assert edicion_permitida(estado, rol, seccion) is permitida
