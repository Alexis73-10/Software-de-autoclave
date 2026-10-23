# tests/test_opciones_controller.py
#
# OpcionesController (planeacion_opciones_parametros_ciclo.md, Fase 1): expone
# la identidad de la sesión de SessionManager, las secciones visibles por rol,
# el cierre de sesión y edicionPermitida según el estado global.

import pytest

from tests.opciones_qml_doble import COMUNES_T6

pytest.importorskip("PySide6")

from autoclave.ui.service_ui.session_manager import SessionManager
from autoclave.ui_qml.controllers.opciones_controller import OpcionesController


def _usuario(rol):
    return {"id": 1, "nombre": "Ana Ruiz", "usuario": "anar", "rol": rol}


@pytest.fixture(autouse=True)
def _sin_sesion():
    SessionManager.logout()
    yield
    SessionManager.logout()


def test_sin_sesion():
    c = OpcionesController()
    assert c.sesionActiva is False
    assert (c.usuario, c.nombre, c.rol) == ("", "", "")
    assert c.secciones == []


def test_identidad_y_secciones_de_un_tecnico():
    SessionManager.login(_usuario("tecnico"))
    c = OpcionesController()
    assert c.sesionActiva is True
    assert (c.usuario, c.nombre, c.rol) == ("anar", "Ana Ruiz", "tecnico")
    assert [s["clave"] for s in c.secciones][0] == "parametros_ciclo"
    # C9 (tanda 9, D9-10): Opciones avanzadas vuelve al técnico (Manejo de
    # ciclos); la reasignación de E/S sigue solo para el ingeniero
    assert len(c.secciones) == 7 + len(COMUNES_T6) + 1   # cinco técnicas + Usuarios + Conectividad + O2c–O2e + Respaldo (O2h)
    assert "opciones_avanzadas" in [s["clave"] for s in c.secciones]
    assert c.puedeReasignarIo is False
    assert all(s["icono"].endswith(".svg") for s in c.secciones)


def test_refrescar_detecta_la_sesion_nueva_y_notifica():
    c = OpcionesController()
    avisos = []
    c.sesionChanged.connect(lambda: avisos.append(1))
    SessionManager.login(_usuario("admin"))
    c.refrescar()
    assert c.sesionActiva is True
    assert [s["clave"] for s in c.secciones] == ["parametros_sistema", "usuarios", "conectividad", *COMUNES_T6]
    assert avisos == [1]
    c.refrescar()   # sin cambios: no vuelve a notificar
    assert avisos == [1]


def test_cerrar_sesion():
    SessionManager.login(_usuario("ingeniero"))
    c = OpcionesController()
    c.cerrarSesion()
    assert SessionManager.is_authenticated() is False
    assert c.sesionActiva is False
    assert c.secciones == []


def test_edicion_permitida_sigue_al_estado():
    c = OpcionesController()
    avisos = []
    c.estadoMaquinaChanged.connect(lambda: avisos.append(1))
    assert c.edicionPermitida is False
    c.estadoMaquina = "PREPARADO"
    assert c.edicionPermitida is True
    c.estadoMaquina = "CICLO"
    assert c.edicionPermitida is False
    assert avisos == [1, 1]


def test_ingeniero_edita_en_cualquier_estado_y_seccion():
    SessionManager.login(_usuario("ingeniero"))
    c = OpcionesController()
    for estado in ("CICLO", "FALLA", "PREPARADO"):
        c.estadoMaquina = estado
        for seccion in ("parametros_ciclo", "mantenimiento"):
            c.seccion = seccion
            assert c.edicionPermitida is True


def test_edicion_cambia_con_la_sesion():
    c = OpcionesController()
    avisos = []
    c.edicionChanged.connect(lambda: avisos.append(1))
    c.estadoMaquina = "CICLO"
    assert c.edicionPermitida is False
    SessionManager.login(_usuario("ingeniero"))
    c.refrescar()
    assert c.edicionPermitida is True
    assert len(avisos) == 2
