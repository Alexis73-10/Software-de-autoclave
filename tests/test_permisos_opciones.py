# tests/test_permisos_opciones.py
#
# puedeVer de OPCIONES (planeacion_opciones_parametros_ciclo.md, U-7 y §8): una
# prueba por rol y por entrada, orden de la navegación lateral y estados en que
# la edición se permite (U-8).

import pytest

from tests.opciones_qml_doble import COMUNES_T6

from autoclave.ui_pyside.services.roles import VALORES_ROL
from autoclave.ui_qml.domain.permisos_opciones import (
    SECCIONES, edicion_permitida, puede_ver, secciones_visibles,
)

_TECNICAS = ["parametros_ciclo", "parametros_sistema", "entradas_salidas",
             "mantenimiento", "opciones_avanzadas"]
_ADMIN = ["usuarios", "conectividad", *COMUNES_T6]

_ESPERADO = {
    "admin":     ["parametros_sistema"] + _ADMIN,   # C1b (tanda 6): solo lectura
    # Conectividad también para técnico e ingeniero (tanda 2026-10-14 §1.6)
    # O2b (tanda 6, decisión 1.9): el técnico ve Usuarios con los controles deshabilitados
    # C9 (tanda 9, D9-10): Opciones avanzadas para técnico e ingeniero (Manejo
    # de ciclos); la reasignación de E/S, solo el ingeniero (puede_reasignar_io)
    "tecnico":   _TECNICAS + _ADMIN + ["respaldo"],
    "biomedico": [],      # rol eliminado (planeacion_backend_autenticacion.md, decisión 25)
    # Usuarios también para el ingeniero (Cristian, 2026-10-08; T-8, R3-5)
    "ingeniero": _TECNICAS + _ADMIN + ["respaldo"],   # O2h
    "operador":  [],      # defecto de la tabla usuarios, fuera de roles.py
    "":          [],
    None:        [],
}


def test_orden_de_la_navegacion():
    # U-2: las cinco de AdminMenuView._OPTIONS en su orden; al final las de admin
    assert [s.clave for s in SECCIONES] == _TECNICAS + _ADMIN + ["respaldo"]


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
    ("CICLO", False), ("FALLA", True), ("EMERGENCIA", False),   # P-8: estado retirado
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


# C9 (tanda 9, D9-10): dentro de Opciones avanzadas, Manejo de ciclos para
# técnico e ingeniero y la reasignación de E/S solo para el ingeniero
@pytest.mark.parametrize("rol,manejo,reasignar", [
    ("tecnico", True, False), ("ingeniero", True, True), ("admin", False, False),
    ("operador", False, False), ("", False, False), (None, False, False)])
def test_subsecciones_de_opciones_avanzadas(rol, manejo, reasignar):
    from autoclave.ui_qml.domain.permisos_opciones import puede_manejar_ciclos, puede_reasignar_io
    assert puede_manejar_ciclos(rol) is manejo
    assert puede_reasignar_io(rol) is reasignar


@pytest.mark.parametrize("estado,esperado", [("PREPARACION", True), ("PREPARADO", True),
                                             ("FALLA", True), ("CICLO", False), ("", False)])
@pytest.mark.parametrize("rol", ["tecnico", "ingeniero"])
def test_manejo_de_ciclos_solo_fuera_de_ciclo(rol, estado, esperado):
    # el ingeniero tampoco en CICLO (a diferencia de los parámetros)
    from autoclave.ui_qml.domain.permisos_opciones import motivo_manejo_ciclos
    assert (motivo_manejo_ciclos(rol, estado) == "") is esperado
    if estado == "CICLO":
        assert motivo_manejo_ciclos(rol, estado) == "ciclo"
    assert motivo_manejo_ciclos("admin", "PREPARADO") == "rol"
