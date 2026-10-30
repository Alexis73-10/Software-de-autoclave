"""P1 (tanda 5): el modo prueba de Entradas / Salidas termina al cerrar su
ventana por cualquier camino, antes de que el token deje de valer.

- Cierre de sesión (botón, standby, suspensión, salida de la aplicación): la
  ventana de sesión avisa a los controladores en modo prueba ANTES del logout,
  con el token todavía válido, y ellos piden la salida normal (/io/test/exit).
- Otra pantalla encima (Menú principal) u Opciones destruida: la pantalla QML
  llama a la misma salida (onVisibleChanged / Component.onDestruction).
- Si la UI se cae o la salida falla, el respaldo es el plazo de inactividad
  del backend (keepalive), cubierto en test_io_momentaneas_keepalive.py.
"""

import os
import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QML = Path(__file__).resolve().parents[1] / "src/autoclave/ui_qml/qml/Pantallas"


def _app():
    from PySide6.QtCore import QCoreApplication
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


def _ventana(respuestas=None):
    _app()
    from autoclave.cliente.session_manager import SessionManager
    from autoclave.ui_qml import sesion_backend as sb
    llamadas = []

    def transporte(metodo, ruta, cuerpo, token, plazo):
        llamadas.append((metodo, ruta, token))
        return (respuestas or {}).get((metodo, ruta), (200, {}))

    s = sb.SesionVentana(transporte=transporte, ejecutar=lambda t: t())
    SessionManager.login({"nombre": "T", "usuario": "t", "rol": "tecnico"}, "TOK")
    return s, llamadas, SessionManager


def _ctrl_en_prueba(s):
    from autoclave.ui_qml.controllers.entradas_salidas_controller import (
        EntradasSalidasController)
    c = EntradasSalidasController(sesion=s)
    assert c.entrarModoPrueba()
    assert c.modoPrueba
    return c


@pytest.mark.parametrize("camino", ["boton", "standby", "salida_app"])
def test_cerrar_sesion_sale_del_modo_prueba_antes_del_logout(camino):
    s, llamadas, sm = _ventana()
    try:
        c = _ctrl_en_prueba(s)
        llamadas.clear()
        if camino == "salida_app":
            s.cerrar_al_salir(plazo_s=1.0)
        else:
            s.cerrar_sesion()
        rutas = [(m, r) for m, r, _ in llamadas]
        assert rutas.index(("POST", "/io/test/exit")) < rutas.index(("POST", "/auth/logout"))
        # la salida va con el token aún válido
        assert [t for m, r, t in llamadas if r == "/io/test/exit"] == ["TOK"]
        assert not c.modoPrueba
    finally:
        sm.logout()


def test_sin_modo_prueba_el_logout_no_llama_a_la_salida():
    s, llamadas, sm = _ventana()
    try:
        from autoclave.ui_qml.controllers.entradas_salidas_controller import (
            EntradasSalidasController)
        EntradasSalidasController(sesion=s)
        s.cerrar_sesion()
        assert ("POST", "/io/test/exit") not in [(m, r) for m, r, _ in llamadas]
    finally:
        sm.logout()


def test_tras_salir_normal_el_logout_no_repite_la_salida():
    s, llamadas, sm = _ventana()
    try:
        c = _ctrl_en_prueba(s)
        assert c.salirModoPrueba("salida solicitada")
        llamadas.clear()
        s.cerrar_sesion()
        assert ("POST", "/io/test/exit") not in [(m, r) for m, r, _ in llamadas]
    finally:
        sm.logout()


def test_fallo_de_la_salida_no_impide_el_logout():
    s, llamadas, sm = _ventana({("POST", "/io/test/exit"): (500, {"detail": "x"})})
    try:
        c = _ctrl_en_prueba(s)
        s.cerrar_sesion()
        rutas = [(m, r) for m, r, _ in llamadas]
        assert ("POST", "/io/test/exit") in rutas and ("POST", "/auth/logout") in rutas
        assert not sm.is_authenticated()
        # el respaldo es el vigilante del backend (sesión dueña cerrada, SAF-01)
        assert c is not None
    finally:
        sm.logout()


def test_un_aviso_que_lanza_no_impide_el_logout():
    s, llamadas, sm = _ventana()
    try:
        s.al_cerrar_sesion(lambda: 1 / 0)
        s.cerrar_sesion()
        assert ("POST", "/auth/logout") in [(m, r) for m, r, _ in llamadas]
    finally:
        sm.logout()


def test_qml_sale_al_quedar_tapada_o_destruida():
    texto = (QML / "OpcionesEntradasSalidas.qml").read_text(encoding="utf-8")
    assert "Component.onDestruction: cerrarModoPrueba(" in texto
    # otra pantalla encima (Menú principal desde el engranaje): StackView la oculta
    assert re.search(r"onVisibleChanged:\s*\{?\s*if \(!visible\)\s*cerrarModoPrueba\(", texto)
    # cambio de segmento
    assert 'if (segmento !== "salidas") cerrarModoPrueba(' in texto


def test_opciones_sale_del_modo_prueba_en_toda_salida():
    texto = (QML / "Opciones.qml").read_text(encoding="utf-8")
    cuerpo = texto[texto.index("function _salirCon"):]
    cuerpo = cuerpo[:cuerpo.index("\n    }\n")]
    assert "cerrarModoPrueba(" in cuerpo
    # Atrás, Inicio y Cerrar sesión pasan por _salirCon
    assert "function cerrarSesion() { _salirCon(cerrarSesionPulsado) }" in texto
    assert "_salirCon(atrasPulsado)" in texto


def test_cierre_sin_token_olvida_los_avisos():
    s, llamadas, sm = _ventana()
    try:
        c = _ctrl_en_prueba(s)
        s.cerrar_local()
        sm.login({"nombre": "O", "usuario": "otro", "rol": "tecnico"}, "TOK2")
        llamadas.clear()
        s.cerrar_sesion()
        assert ("POST", "/io/test/exit") not in [(m, r) for m, r, _ in llamadas]
        assert c is not None
    finally:
        sm.logout()


def test_el_aviso_de_cierre_usa_plazo_corto_y_no_cierra_local_ante_401():
    from autoclave.ui_qml import sesion_backend as sb
    s, llamadas, sm = _ventana({("POST", "/io/test/exit"): (401, {"detail": "x"})})
    try:
        c = _ctrl_en_prueba(s)
        plazos = []
        orig = s._llamar_con_plazo
        s._llamar_con_plazo = lambda *a, plazo_s=None: (plazos.append(plazo_s), orig(*a, plazo_s=plazo_s))[1]
        s.cerrar_sesion()
        assert sb.PLAZO_AVISO_CIERRE_S in plazos and sb.PLAZO_AVISO_CIERRE_S <= 1.0
        assert not c.modoPrueba
    finally:
        sm.logout()
