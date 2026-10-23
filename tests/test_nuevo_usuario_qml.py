# tests/test_nuevo_usuario_qml.py
#
# Pantalla Nuevo Usuario (planeacion_nuevo_usuario.md, F3 y sección 10):
# la vista PySide real (QQuickWidget con NuevoUsuarioHost.qml) con un backend
# falso (POST /usuarios por la sesión de la ventana, T-20 y T-8), en
# subproceso para tener un QApplication propio y offscreen.
# Cubre: confirmación de descarte solo con datos capturados (Cancelar, "<",
# Salir, Inicio), ojo independiente por campo y su efecto en el teclado,
# errores por campo sin llamar al backend, éxito (limpia y navega a
# admin_menu), retorno al menú sin sesión que pueda crear y la BarraSuperior.

import json
import os
import subprocess
import sys
import textwrap

import pytest

pytest.importorskip("PySide6")

_SCRIPT = textwrap.dedent(r"""
    import json, sys, tempfile, pathlib
    from PySide6.QtCore import Q_ARG, QMetaObject, QObject, Qt
    from PySide6.QtWidgets import QApplication
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Software)
    qapp = QApplication([])

    from autoclave.ui.service_ui.session_manager import SessionManager
    from autoclave.ui_pyside.views.nuevo_usuario.vista import NuevoUsuarioView

    from autoclave.ui_qml.sesion_backend import SesionVentana

    enviados = []   # POST /usuarios que llegarían al backend
    def transporte(metodo, ruta, cuerpo, token, plazo):
        enviados.append({"ruta": ruta, "cuerpo": cuerpo, "token": token})
        return 200, {"ok": True}
    destinos = []
    r = {}

    def proc():
        qapp.processEvents()
        qapp.processEvents()

    def nueva_vista():
        v = NuevoUsuarioView(nav_callback=destinos.append,
                             sesion=SesionVentana(transporte=transporte, ejecutar=lambda t: t()))
        v.resize(600, 960)
        return v

    SessionManager.login({"id": 1, "nombre": "Administrador", "usuario": "admin", "rol": "admin",
                          "token": "tok-admin"})
    vista = nueva_vista()
    avisos = [e.toString() for e in vista.errors()]
    vista.show(); proc()
    raiz = vista.rootObject()
    p = raiz.findChild(QObject, "nuevoUsuario")
    dialogo = raiz.findChild(QObject, "dialogoDescartar")
    panel = raiz.findChild(QObject, "panelTeclado")
    alfa = raiz.findChild(QObject, "tecladoAlfanumerico")
    barra = raiz.findChild(QObject, "barraSuperior")
    r["avisos"] = avisos
    r["cargo"] = p is not None and dialogo is not None
    r["iconos_barra"] = barra.property("mostrarIconos")
    r["campos"] = sorted(o.objectName() for o in raiz.findChildren(QObject)
                         if o.objectName().startswith("campo"))

    def llamar(nombre):
        QMetaObject.invokeMethod(p, nombre)
        proc()

    def accion_con_datos(boton, cambio):
        destinos.clear()
        p.setProperty(*cambio); proc()
        llamar(boton)
        pidio = dialogo.property("visible")
        sin_nav = destinos == []
        QMetaObject.invokeMethod(dialogo, "confirmar"); proc()
        return {"pidio": pidio, "sin_nav": sin_nav, "destino": list(destinos),
                "limpio": p.property("nombre") == "" and p.property("rol") == ""
                          and p.property("activo") is True}

    def accion_sin_datos(boton):
        destinos.clear()
        llamar(boton)
        return {"pidio": dialogo.property("visible"), "destino": list(destinos)}

    for boton in ("pulsarCancelar", "pulsarAtras", "pulsarInicio"):
        r["vacio_" + boton] = accion_sin_datos(boton)
    r["datos_cancelar"] = accion_con_datos("pulsarCancelar", ("nombre", "Ana"))
    r["datos_atras"] = accion_con_datos("pulsarAtras", ("rol", "tecnico"))
    r["datos_inicio"] = accion_con_datos("pulsarInicio", ("activo", False))

    # seguir editando: el diálogo se cierra y los datos quedan
    destinos.clear()
    p.setProperty("usuario", "anar"); proc()
    llamar("pulsarCancelar")
    QMetaObject.invokeMethod(dialogo, "cerrar"); proc()
    r["seguir_editando"] = {"destino": list(destinos), "usuario": p.property("usuario"),
                            "visible": dialogo.property("visible")}
    llamar("limpiar")

    # ojo independiente por campo
    llamar("alternarOjoClave")
    r["ojo"] = {"clave": p.property("verClave"), "confirmacion": p.property("verConfirmacion")}
    llamar("alternarOjoClave")

    # ojo y teclado (NU-02): visible al abrir -> sin puntos; apagar el ojo
    # con el teclado abierto lo reabre oculto, conservando lo escrito
    llamar("alternarOjoClave")                       # mostrar
    QMetaObject.invokeMethod(p, "editar", Q_ARG("QVariant", "clave")); proc()
    r["teclado_visible_sin_puntos"] = alfa.property("ocultarTexto")
    from autoclave.ui_qml.controllers.teclado_alfanumerico_controller import TecladoAlfanumericoController
    ctrl = alfa.findChildren(TecladoAlfanumericoController)[0]
    for ch in "abc":
        ctrl.presionarCaracter(ch)
    proc()
    llamar("alternarOjoClave")                       # ocultar con el teclado abierto
    r["teclado_reabierto_oculto"] = {"abierto": panel.property("abierto"),
                                     "ocultar": alfa.property("ocultarTexto"),
                                     "clave": p.property("clave")}
    QMetaObject.invokeMethod(panel, "cerrar"); proc()
    llamar("limpiar")

    # errores: todos a la vez, nada en la BD, sin navegar
    destinos.clear()
    p.setProperty("nombre", "Ana Ruiz"); p.setProperty("usuario", "ana r"); proc()
    llamar("pulsarGuardar")
    errores = p.property("errores")
    errores = errores.toVariant() if hasattr(errores, "toVariant") else errores
    r["errores"] = {"campos": sorted(errores), "destino": list(destinos),
                    "enviados": len(enviados),
                    "texto_usuario": raiz.findChild(QObject, "errorUsuario").property("text"),
                    "teclado_en": p.property("campoActivo")}
    QMetaObject.invokeMethod(panel, "cerrar"); proc()
    llamar("limpiar")

    # éxito
    destinos.clear()
    for k, v in (("nombre", "Ana Ruiz"), ("usuario", "anar"), ("clave", "clave1234"),
                 ("confirmacion", "clave1234"), ("rol", "tecnico")):
        p.setProperty(k, v)
    proc()
    llamar("pulsarGuardar")
    envio = enviados[-1] if enviados else {}
    r["exito"] = {"destino": list(destinos), "ruta": envio.get("ruta"),
                  "usuario": envio.get("cuerpo", {}).get("usuario"),
                  "rol": envio.get("cuerpo", {}).get("rol"), "token": envio.get("token"),
                  "limpio": p.property("clave") == ""
                  and p.property("usuario") == ""}

    # sin sesión admin: al mostrarse vuelve al menú
    vista.hide(); proc()
    SessionManager.login({"id": 2, "nombre": "Tec", "usuario": "tec1", "rol": "tecnico",
                          "token": "tok-tec"})
    destinos.clear()
    vista.show(); proc()
    r["no_admin"] = list(destinos)

    print("RESULTADO=" + json.dumps(r))
""")


@pytest.fixture(scope="module")
def resultado():
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": "src"}
    proc = subprocess.run([sys.executable, "-c", _SCRIPT], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, timeout=120)
    lineas = [l for l in proc.stdout.splitlines() if l.startswith("RESULTADO=")]
    assert lineas, proc.stdout + proc.stderr
    return json.loads(lineas[0][len("RESULTADO="):])


def test_carga_sin_avisos(resultado):
    assert resultado["cargo"]
    assert resultado["avisos"] == []


def test_campos_conformes_al_mockup(resultado):
    # D-01/D-02: sin Nivel de acceso; Código eliminado (mockup nuevo_usuario_sin_codigo.png)
    assert resultado["campos"] == sorted([
        "campoNombre", "campoUsuario", "campoClave", "campoConfirmacion", "campoRol",
    ])


def test_barra_superior_con_iconos(resultado):
    assert resultado["iconos_barra"] is True


@pytest.mark.parametrize("boton,destino", [
    ("pulsarCancelar", "admin_menu"), ("pulsarAtras", "admin_menu"), ("pulsarInicio", "home"),
])
def test_sin_datos_actua_de_inmediato(resultado, boton, destino):
    assert resultado["vacio_" + boton] == {"pidio": False, "destino": [destino]}


@pytest.mark.parametrize("clave,destino", [
    ("datos_cancelar", "admin_menu"), ("datos_atras", "admin_menu"), ("datos_inicio", "home"),
])
def test_con_datos_pide_confirmacion(resultado, clave, destino):
    r = resultado[clave]
    assert r["pidio"] is True
    assert r["sin_nav"] is True
    assert r["destino"] == [destino]
    assert r["limpio"] is True


def test_seguir_editando_conserva_datos(resultado):
    assert resultado["seguir_editando"] == {"destino": [], "usuario": "anar", "visible": False}


def test_ojo_independiente_por_campo(resultado):
    assert resultado["ojo"] == {"clave": True, "confirmacion": False}


def test_ojo_visible_teclado_sin_puntos(resultado):
    assert resultado["teclado_visible_sin_puntos"] is False


def test_ojo_apagado_reabre_teclado_oculto(resultado):
    assert resultado["teclado_reabierto_oculto"] == {"abierto": True, "ocultar": True, "clave": "Abc"}  # Aa inicial de un solo uso


def test_errores_no_escriben_ni_navegan(resultado):
    e = resultado["errores"]
    assert e["campos"] == ["confirmacion", "password", "rol", "usuario"]
    assert e["destino"] == []
    assert e["enviados"] == 0
    assert e["texto_usuario"] == "Solo letras, números y . _ -, de 3 a 30 caracteres"   # U11 SAF-01
    assert e["teclado_en"] == "usuario"   # se enfoca el primero con error


def test_exito_guarda_limpia_y_navega(resultado):
    assert resultado["exito"] == {"destino": ["admin_menu"], "ruta": "/usuarios",
                                  "usuario": "anar", "rol": "tecnico", "token": "tok-admin",
                                  "limpio": True}


def test_sin_admin_vuelve_al_menu(resultado):
    assert resultado["no_admin"] == ["admin_menu"]
