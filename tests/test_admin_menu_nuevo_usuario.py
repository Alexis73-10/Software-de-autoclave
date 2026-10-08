# Punto de entrada de la pantalla Nuevo Usuario (planeacion_nuevo_usuario.md,
# F4): opción del menú de administración solo para admin (D-05, NU-05),
# corrección de NU-08 y alojamiento en MainWindowFluent con la bandera
# genérica que oculta encabezado y pie.

import sys

import pytest

ADMIN = {"id": 1, "nombre": "Administrador Uno", "usuario": "admin", "rol": "admin"}
TECNICO = {"id": 2, "nombre": "Tec Uno", "usuario": "tec1", "rol": "tecnico"}


@pytest.fixture(scope="session", autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture(autouse=True)
def sesion_limpia():
    from autoclave.ui_pyside.services.session_manager import SessionManager
    SessionManager.logout()
    yield
    SessionManager.logout()


def _menu(qapp, sesion=None):
    from autoclave.ui_pyside.services.session_manager import SessionManager
    from autoclave.ui_pyside.views.admin_menu import AdminMenuView
    if sesion:
        SessionManager.login(sesion)
    destinos = []
    menu = AdminMenuView(nav_callback=destinos.append)
    menu.show()
    qapp.processEvents()
    return menu, destinos


# ── admin_menu ────────────────────────────────────────────────────────────────

def test_opcion_visible_para_admin(qapp):
    menu, _ = _menu(qapp, ADMIN)
    assert menu._botones["Nuevo usuario"].isVisible()


@pytest.mark.parametrize("sesion", [None, TECNICO])
def test_opcion_oculta_sin_admin(qapp, sesion):
    menu, _ = _menu(qapp, sesion)
    assert not menu._botones["Nuevo usuario"].isVisible()


def test_opcion_navega_a_nuevo_usuario(qapp):
    menu, destinos = _menu(qapp, ADMIN)
    menu._botones["Nuevo usuario"].click()
    assert destinos == ["nuevo_usuario"]


def test_opcion_no_navega_sin_admin_aunque_se_invoque(qapp):
    menu, destinos = _menu(qapp, TECNICO)
    menu._option_clicked("Nuevo usuario")
    assert destinos == []


def test_nu08_muestra_nombre_de_la_sesion(qapp):
    menu, _ = _menu(qapp, ADMIN)
    assert menu._lbl_user.text() == "Administrador Uno"


def test_opciones_existentes_siguen_igual(qapp):
    menu, destinos = _menu(qapp, ADMIN)
    menu._option_clicked("Parámetros del ciclo")
    menu._option_clicked("Entradas / Salidas")
    assert destinos == ["params_ciclo", "io_menu"]


# ── main_window ───────────────────────────────────────────────────────────────

def test_navegar_a_nuevo_usuario_oculta_marco(qapp):
    from autoclave.ui_pyside.main_window import MainWindowFluent
    from autoclave.ui_pyside.services.session_manager import SessionManager
    SessionManager.login(ADMIN)
    win = MainWindowFluent()
    win.navigate_to("nuevo_usuario")
    assert win._stack.currentWidget() is win._nuevo_usuario
    assert win._header.isHidden()
    assert win._footer.isHidden()


def test_volver_a_otra_vista_muestra_marco(qapp):
    from autoclave.ui_pyside.main_window import MainWindowFluent
    win = MainWindowFluent()
    win.navigate_to("nuevo_usuario")
    win.navigate_to("admin_menu")
    assert not win._header.isHidden()
    assert not win._footer.isHidden()


def test_vistas_sin_bandera_conservan_marco(qapp):
    from autoclave.ui_pyside.main_window import MainWindowFluent
    win = MainWindowFluent()
    for vista in ("home", "login", "admin_menu", "params_ciclo"):
        win.navigate_to(vista)
        assert not win._header.isHidden(), vista
