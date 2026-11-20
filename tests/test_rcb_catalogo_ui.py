"""RCB-08.1/08.2/08.3: Opciones › Catálogo de carga (ingeniero y admin).

- Controlador con un backend simulado: lista, filtro local, alta (OK, 409,
  422 y validación local), editar nombre, baja/reactivar, USB, vista previa y
  aplicar con la huella, csv_cambio y csv_invalido.
- Permisos: la sección solo para ingeniero y admin, editable en cualquier
  estado.
- Códigos de rechazo de /carga/catalogo reconocidos solo en esa ruta.
- QML offscreen: la pantalla carga sin avisos, el diálogo de alta captura una
  lectura del lector simulada con eventos de teclado (texto + Enter) y la
  sección aparece en Opciones.
"""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tests.helpers import opciones_qml_doble as doble
from tests.helpers.sesion_f6_controladores import SesionManual, app, conservar, r

from autoclave import i18n
from autoclave.ui_qml import sesion_backend as sb
from autoclave.ui_qml.controllers import catalogo_carga_controller as mod
from autoclave.ui_qml.controllers.catalogo_carga_controller import CatalogoCargaController
from autoclave.ui_qml.domain import permisos_opciones as permisos

pytestmark = pytest.mark.req("REQ-114")

RAIZ = Path(__file__).resolve().parents[1]
RUTA = "/carga/catalogo"
CATALOGO = {"elementos": [
    {"id": 1, "codigo": "CX-0102", "nombre": "Set de cirugía general", "activo": True},
    {"id": 2, "codigo": "GI-0410", "nombre": "Pinza Kelly curva", "activo": True},
    {"id": 3, "codigo": "OR-0040", "nombre": "Caja de ortopedia de cadera", "activo": False},
]}
USB = {"unidades": [{"ruta": "E:\\", "libre_bytes": 1, "archivos": [
    {"archivo": "catalogo.csv", "bytes": 2048}]}]}
VISTA = {"ok": True, "aplicado": False,
         "altas": [{"codigo": "A1", "nombre": "Uno"}, {"codigo": "A2", "nombre": "Dos"}],
         "cambios": [{"codigo": "CX-0102", "anterior": "x", "nombre": "y", "reactivado": False}],
         "reactivados": [], "sin_cambio": 4,
         "rechazadas": [{"linea": 7, "motivo": "caracter", "texto": "a|b;c"},
                        {"linea": 9, "motivo": "raro", "texto": "z"}],
         "huella": "abc123"}


@pytest.fixture(scope="module", autouse=True)
def _app():
    return app()


def _cargado():
    s = SesionManual()
    c = conservar(CatalogoCargaController(sesion=s))
    c.cargar()
    s.responder_ultimo("GET", RUTA, r(datos=CATALOGO))
    return c, s


# ── lista y filtro ─────────────────────────────────────────────────────

def test_lista_y_conteos():
    c, _ = _cargado()
    assert [e["codigo"] for e in c.elementos] == ["CX-0102", "GI-0410", "OR-0040"]
    assert (c.total, c.activos, c.deBaja) == (3, 2, 1)
    assert c.elementos[2]["claveEstado"] == "registro_carga.estado_baja"
    assert c.claveVacio == "" and not c.cargando


@pytest.mark.parametrize("texto,esperado", [
    ("cx", ["CX-0102"]), ("KELLY", ["GI-0410"]), ("  ortopedia ", ["OR-0040"]),
    ("", ["CX-0102", "GI-0410", "OR-0040"]), ("nada", []),
])
def test_filtro_por_codigo_o_nombre_sin_mayusculas(texto, esperado):
    c, _ = _cargado()
    c.filtro = texto
    assert [e["codigo"] for e in c.elementos] == esperado
    assert c.claveVacio == ("registro_carga.catalogo_sin_coincidencias" if not esperado else "")


def test_catalogo_vacio_y_error_conserva_la_lista():
    s = SesionManual()
    c = conservar(CatalogoCargaController(sesion=s))
    c.cargar()
    s.responder_ultimo("GET", RUTA, r(datos={"elementos": []}))
    assert c.claveVacio == "registro_carga.catalogo_vacio"
    c.cargar()
    s.responder_ultimo("GET", RUTA, r(datos=CATALOGO))
    c.cargar()
    s.responder_ultimo("GET", RUTA, r(sb.BACKEND_NO_RESPONDE, {}, None))
    assert c.total == 3 and c.mensaje == "opciones.err_sin_respuesta"


# ── alta ───────────────────────────────────────────────────────────────

def test_alta_ok_normaliza_envia_y_relee():
    c, s = _cargado()
    res = []
    c.altaResuelta.connect(lambda ok, m: res.append((ok, m)))
    assert c.alta("  TX-0007 ", "Paquete   de ropa") is True
    i = s.ultimo("POST", RUTA)
    assert s.envios[i]["cuerpo"] == {"codigo": "TX-0007", "nombre": "Paquete de ropa"}
    assert c.enviando
    antes = s.cuenta("GET", RUTA)
    s.responder(i, r(datos={"ok": True, "codigo": "TX-0007", "nombre": "Paquete de ropa",
                            "reactivado": False}))
    assert res == [(True, "")] and not c.enviando
    assert c.mensaje == "registro_carga.guardado" and c.mensajeExito
    assert s.cuenta("GET", RUTA) == antes + 1


@pytest.mark.parametrize("causa,estado,clave", [
    ("codigo_existe", 409, "registro_carga.err_codigo_existe"),
    ("validacion", 422, "registro_carga.err_validacion"),
    ("rol_sin_permiso", 403, "registro_carga.err_rol"),
    (sb.ERROR_GENERICO, 500, "registro_carga.err_generico"),
])
def test_alta_rechazada(causa, estado, clave):
    c, s = _cargado()
    res = []
    c.altaResuelta.connect(lambda ok, m: res.append((ok, m)))
    c.alta("TX-0007", "Paquete")
    s.responder_ultimo("POST", RUTA, r(causa, {"errores": [{"campo": "codigo", "codigo": "largo"}]},
                                       estado))
    assert res == [(False, clave)] and c.mensaje == clave and not c.mensajeExito
    assert i18n.existe(clave, "es") and i18n.existe(clave, "en")


@pytest.mark.parametrize("codigo,nombre", [
    ("", "Nombre"), ("a|b", "Nombre"), ("x" * 65, "Nombre"), ("ÁRBOL", "Nombre"),
    ("ok", ""), ("ok", "x" * 61), ("ok", "con | barra"),
])
def test_alta_invalida_no_sale(codigo, nombre):
    c, s = _cargado()
    assert c.alta(codigo, nombre) is False
    assert s.cuenta("POST", RUTA) == 0
    assert c.mensaje == "registro_carga.err_validacion"


def test_validaciones_para_la_pantalla():
    c, _ = _cargado()
    assert c.validarCodigo(" CX-01 ") == "" and c.normalizarCodigo(" CX-01 ") == "CX-01"
    assert c.validarCodigo("a|b") == "registro_carga.lectura_invalida"
    assert c.validarNombre("Pinza") == "" and c.validarNombre("") != ""
    assert (c.largoCodigo, c.largoNombre) == (64, 60)


# ── editar, baja y reactivar ─────────────────────────────────────────

def test_editar_nombre_envia_patch_y_relee():
    c, s = _cargado()
    res = []
    c.edicionResuelta.connect(lambda *a: res.append(a))
    assert c.editarNombre(2, " Pinza  Kelly ") is True
    i = s.ultimo("PATCH", f"{RUTA}/2")
    assert s.envios[i]["cuerpo"] == {"nombre": "Pinza Kelly"}
    s.responder(i, r(datos={"ok": True, "elemento": {}}))
    assert res == [(2, True, "")] and c.mensaje == "registro_carga.guardado"
    assert s.cuenta("GET", RUTA) == 2


def test_editar_invalido_o_inexistente_no_sale():
    c, s = _cargado()
    assert c.editarNombre(2, "") is False
    assert c.editarNombre(99, "Otro") is False
    assert c.fijarActivo(99, False) is False
    assert s.cuenta("PATCH", f"{RUTA}/2") == 0 and s.cuenta("PATCH", f"{RUTA}/99") == 0


@pytest.mark.parametrize("id_,activo", [(1, False), (3, True)])
def test_baja_y_reactivar(id_, activo):
    c, s = _cargado()
    assert c.fijarActivo(id_, activo) is True
    i = s.ultimo("PATCH", f"{RUTA}/{id_}")
    assert s.envios[i]["cuerpo"] == {"activo": activo}
    s.responder(i, r(datos={"ok": True}))
    assert c.mensaje == "registro_carga.guardado"


def test_no_existe_relee_y_avisa():
    c, s = _cargado()
    res = []
    c.edicionResuelta.connect(lambda *a: res.append(a))
    c.fijarActivo(1, False)
    s.responder_ultimo("PATCH", f"{RUTA}/1", r("no_existe", {}, 404))
    assert res == [(1, False, "registro_carga.err_generico")]
    assert s.cuenta("GET", RUTA) == 2


def test_un_envio_a_la_vez():
    c, s = _cargado()
    assert c.alta("A1", "Uno") is True
    assert c.alta("A2", "Dos") is False
    assert c.fijarActivo(1, False) is False
    assert s.cuenta("POST", RUTA) == 1


# ── importación ────────────────────────────────────────────────────────

def _con_vista():
    c, s = _cargado()
    c.cargarUsb()
    s.responder_ultimo("GET", mod.RUTA_USB, r(datos=USB))
    assert c.archivosUsb == [{"unidad": "E:\\", "archivo": "catalogo.csv", "tamano": "2.0 KB"}]
    assert c.verVistaPrevia("E:\\", "catalogo.csv") is True
    i = s.ultimo("POST", mod.RUTA_IMPORTAR)
    assert s.envios[i]["cuerpo"] == {"unidad": "E:\\", "archivo": "catalogo.csv", "aplicar": False}
    s.responder(i, r(datos=VISTA))
    return c, s


def test_vista_previa_con_conteos_y_rechazadas():
    c, _ = _con_vista()
    assert c.hayVistaPrevia and c.aplicable
    assert c.vistaPrevia == {"archivo": "catalogo.csv", "altas": 2, "cambios": 1,
                             "reactivados": 0, "sinCambio": 4, "rechazadas": 2}
    assert c.lineasRechazadas == [
        {"linea": 7, "motivo": "registro_carga.motivo_caracter", "texto": "a|b;c"},
        {"linea": 9, "motivo": "registro_carga.motivo_tipo", "texto": "z"}]
    for f in c.lineasRechazadas:
        assert i18n.existe(f["motivo"], "es") and i18n.existe(f["motivo"], "en")


def test_aplicar_envia_la_huella_y_relee():
    c, s = _con_vista()
    res = []
    c.importacionResuelta.connect(lambda *a: res.append(a))
    assert c.aplicarImportacion() is True
    i = s.ultimo("POST", mod.RUTA_IMPORTAR)
    assert s.envios[i]["cuerpo"] == {"unidad": "E:\\", "archivo": "catalogo.csv",
                                     "aplicar": True, "huella": "abc123"}
    s.responder(i, r(datos={"ok": True, "aplicado": True, "altas": 2, "cambios": 1,
                            "reactivados": 0, "rechazadas": VISTA["rechazadas"]}))
    assert res == [(True, "registro_carga.importado")]
    assert c.mensaje == "registro_carga.importado" and c.mensajeExito
    assert c.mensajeArgs == {"altas": 2, "cambios": 1, "reactivados": 0}
    assert not c.hayVistaPrevia
    assert s.cuenta("GET", RUTA) == 2


def test_csv_cambio_descarta_la_vista_previa():
    c, s = _con_vista()
    res = []
    c.importacionResuelta.connect(lambda *a: res.append(a))
    c.aplicarImportacion()
    s.responder_ultimo("POST", mod.RUTA_IMPORTAR, r("csv_cambio", {}, 409))
    assert res == [(False, "registro_carga.err_csv_cambio")]
    assert c.mensaje == "registro_carga.err_csv_cambio" and not c.hayVistaPrevia
    assert c.aplicarImportacion() is False


@pytest.mark.parametrize("motivo", ["codificacion", "sin_encabezado", "muchas_filas",
                                    "muy_grande", "ilegible"])
def test_csv_invalido_lleva_el_motivo(motivo):
    c, s = _cargado()
    c.verVistaPrevia("E:\\", "x.csv")
    s.responder_ultimo("POST", mod.RUTA_IMPORTAR, r("csv_invalido", {"motivo": motivo}, 422))
    assert c.mensaje == "registro_carga.err_csv"
    assert c.mensajeMotivo == f"registro_carga.motivo_{motivo}"
    assert not c.hayVistaPrevia
    assert i18n.existe(c.mensajeMotivo, "es") and i18n.existe(c.mensajeMotivo, "en")


@pytest.mark.parametrize("causa", ["usb_no_detectada", "archivo_no_encontrado"])
def test_sin_usb_o_archivo(causa):
    c, s = _cargado()
    c.verVistaPrevia("E:\\", "x.csv")
    s.responder_ultimo("POST", mod.RUTA_IMPORTAR, r(causa, {}, 404))
    assert c.mensaje == "registro_carga.err_usb"


def test_vista_sin_nada_que_aplicar():
    c, s = _cargado()
    c.verVistaPrevia("E:\\", "x.csv")
    s.responder_ultimo("POST", mod.RUTA_IMPORTAR, r(datos={
        "ok": True, "aplicado": False, "altas": [], "cambios": [], "reactivados": [],
        "sin_cambio": 3, "rechazadas": [], "huella": "h"}))
    assert c.hayVistaPrevia and not c.aplicable


def test_todos_los_mensajes_existen():
    for clave in set(mod._MENSAJES.values()) | mod.EXITOS:
        assert i18n.existe(clave, "es") and i18n.existe(clave, "en"), clave


# ── códigos de la ruta y permisos ────────────────────────────────────

@pytest.mark.parametrize("codigo", sorted(sb._CODIGOS_CATALOGO_CARGA))
def test_codigos_pasan_solo_en_el_catalogo(codigo):
    for ruta in (RUTA, RUTA + "/5", RUTA + "/importar", RUTA + "?activos=true"):
        assert sb.interpretar(409, {"codigo": codigo}, ruta).causa == codigo
    assert codigo not in sb.codigos_conocidos("")          # no son globales
    for otra in ("/carga/catalogoX", "/status", "/usuarios"):
        assert sb.interpretar(409, {"codigo": codigo}, otra).causa == sb.ERROR_GENERICO
    assert codigo in mod._MENSAJES


@pytest.mark.parametrize("rol,ve", [("ingeniero", True), ("admin", True), ("tecnico", False),
                                    ("operador", False), ("", False), (None, False)])
def test_seccion_solo_ingeniero_y_admin(rol, ve):
    assert permisos.puede_ver("catalogo_carga", rol) is ve
    assert ("catalogo_carga" in [s.clave for s in permisos.secciones_visibles(rol)]) is ve


@pytest.mark.parametrize("estado", ["PREPARACION", "PREPARADO", "FALLA", "CICLO", ""])
@pytest.mark.parametrize("rol", ["ingeniero", "admin"])
def test_edicion_en_cualquier_estado(rol, estado):
    assert permisos.edicion_permitida(estado, rol, "catalogo_carga") is True
    assert permisos.edicion_permitida(estado, "tecnico", "catalogo_carga") is False


def test_rotulo_de_la_seccion():
    for idioma in ("es", "en"):
        assert i18n.existe("opciones.secciones.catalogo_carga", idioma)


# ── QML offscreen ──────────────────────────────────────────────────────

_SCRIPT = textwrap.dedent(r"""
    import json, os, sys
    from PySide6.QtCore import QObject, QUrl, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml import sesion_backend
    from autoclave.ui_qml.sesion_backend import Resultado
    from autoclave.cliente.session_manager import SessionManager

    cfg = json.loads(sys.argv[1])
    enviados = []

    class Falsa:
        def enviar(self, metodo, ruta, cuerpo=None):
            enviados.append([metodo, ruta, cuerpo])
            base = ruta.split("?")[0]
            if metodo == "GET":
                return Resultado("ok", cfg["get"].get(base, {}), 200)
            return Resultado("ok", {"ok": True}, 200)
    sesion_backend.ventana = lambda: Falsa()
    SessionManager.login({"id": 1, "nombre": "Prueba", "usuario": "yo", "rol": "ingeniero"})

    QML = '''
    import QtQuick
    import Tema
    import "Pantallas"
    import "Componentes"
    Window {
        width: 1200; height: 1920; visible: true
        Binding { target: Escala; property: "factor"; value: 1 }
        PanelTeclado { id: tecladoFalso; objectName: "teclado"; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; z: 10 }
        OpcionesCatalogoCarga { objectName: "pantalla"; anchors.fill: parent; anchors.margins: 40
                                teclado: tecladoFalso; edicionPermitida: true }
    }
    '''
    ruta = f"{QML_DIR}/_prueba_rcb_catalogo_{os.getpid()}.qml"
    open(ruta, "w", encoding="utf-8").write(QML)
    try:
        qapp = QGuiApplication([])
        _cargar_fuentes()
        engine = QQmlApplicationEngine()
        avisos = []
        engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
        engine.addImportPath(QML_DIR)
        engine.load(QUrl.fromLocalFile(ruta))
    finally:
        os.remove(ruta)
    w = engine.rootObjects()[0]
    w.show()
    w.requestActivate()
    QTest.qWait(400)
    b = lambda n: w.findChild(QObject, n)
    out = {}
    out["filas"] = b("listaCatalogo").property("count")
    textos = []
    def rec(it):
        for h in it.childItems():
            if h.property("visible"):
                if h.inherits("QQuickText"):
                    textos.append(h.property("text"))
                rec(h)
    rec(w.findChild(QQuickItem, "pantalla"))
    out["textos"] = list(textos)
    out["captura_fuera"] = b("capturaLector").property("activeFocus")
    # abrir el alta y leer con el «lector» (eventos de teclado + Enter)
    from PySide6.QtCore import QMetaObject, QEvent
    from PySide6.QtGui import QKeyEvent

    def teclear(texto):
        # el lector USB HID llega como pulsaciones de teclado a la ventana
        for ch in texto:
            for tipo in (QEvent.KeyPress, QEvent.KeyRelease):
                QGuiApplication.sendEvent(w, QKeyEvent(tipo, 0, Qt.NoModifier, ch))

    def tecla(clave):
        for tipo in (QEvent.KeyPress, QEvent.KeyRelease):
            QGuiApplication.sendEvent(w, QKeyEvent(tipo, clave, Qt.NoModifier, chr(13)))
    QMetaObject.invokeMethod(b("dialogoAlta"), "abrir")
    QTest.qWait(200)
    out["captura_dentro"] = b("capturaLector").property("activeFocus")
    teclear("TX-0007")
    tecla(Qt.Key_Return)
    QTest.qWait(100)
    out["codigo"] = b("codigoAlta").property("text")
    teclear("a|b")
    tecla(Qt.Key_Enter)
    QTest.qWait(100)
    out["codigo_tras_invalida"] = b("codigoAlta").property("text")
    out["aviso"] = b("avisoAlta").property("text")
    b("dialogoAlta").setProperty("nombre", "Paquete de ropa")
    QTest.qWait(100)
    out["guardar_habilitado"] = b("guardarAlta").property("habilitado")
    QMetaObject.invokeMethod(b("guardarAlta"), "pulsado")
    QTest.qWait(200)
    out["alta_cerrada"] = not b("dialogoAlta").property("visible")
    out["captura_tras_cerrar"] = b("capturaLector").property("activeFocus")
    # importación: lista de CSV y vista previa
    QMetaObject.invokeMethod(b("dialogoImportar"), "abrir")
    QTest.qWait(200)
    textos.clear()
    rec(w.findChild(QQuickItem, "pantalla"))
    out["csv"] = any("catalogo.csv" in t for t in textos)
    QMetaObject.invokeMethod(b("dialogoImportar"), "cerrar")
    QTest.qWait(100)
    print("RESULTADO=" + json.dumps({"avisos": avisos, "out": out, "enviados": enviados},
                                    ensure_ascii=False, default=str))
""")


def _correr_qml():
    cfg = {"get": {RUTA: CATALOGO, mod.RUTA_USB: USB}}
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, json.dumps(cfg, ensure_ascii=False)],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ, timeout=120)
    linea = next((x for x in p.stdout.splitlines() if x.startswith("RESULTADO=")), None)
    assert linea, p.stdout[-3000:] + p.stderr[-3000:]
    return json.loads(linea[len("RESULTADO="):])


@pytest.fixture(scope="module")
def qml():
    return _correr_qml()


def test_qml_carga_sin_avisos_y_muestra_la_lista(qml):
    assert qml["avisos"] == []
    assert qml["out"]["filas"] == 3
    for t in ("CX-0102", "Set de cirugía general", "OR-0040", "Activo", "De baja"):
        assert t in qml["out"]["textos"], t
    assert qml["out"]["csv"] is True


def test_qml_lector_solo_en_el_alta_y_enter_entrega_el_codigo(qml):
    o = qml["out"]
    assert o["captura_fuera"] is False          # sin diálogo, sin captura
    assert o["captura_dentro"] is True
    assert o["codigo"] == "TX-0007"
    assert o["codigo_tras_invalida"] == "TX-0007"   # una lectura inválida no reemplaza
    assert o["aviso"] == i18n.t("registro_carga.lectura_invalida", "es")
    assert o["guardar_habilitado"] is True
    assert ["POST", RUTA, {"codigo": "TX-0007", "nombre": "Paquete de ropa"}] in qml["enviados"]
    assert o["alta_cerrada"] is True and o["captura_tras_cerrar"] is False


@pytest.mark.parametrize("rol", ["ingeniero", "admin"])
def test_seccion_en_opciones(rol):
    res = doble.correr("catalogo_carga", rol, {RUTA: CATALOGO},
                       [{"leer": [("cargadorCatalogoCarga", "visible"),
                                  ("textoProximamente", "visible")]}],
                       estado="CICLO")
    assert res["avisos"] == []
    p = res["pasos"][0]
    assert p["props"]["cargadorCatalogoCarga.visible"] is True
    assert p["props"]["textoProximamente.visible"] is False
    assert "Set de cirugía general" in p["textos"]
    assert i18n.t("opciones.edicion_bloqueada", "es") not in p["textos"]
