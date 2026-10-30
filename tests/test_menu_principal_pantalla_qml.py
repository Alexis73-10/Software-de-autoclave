# tests/test_menu_principal_pantalla_qml.py
#
# Carga real del Menú Principal en su arnés (qml/Pruebas/PruebaMenuPrincipal.qml,
# Fase 3 de planeacion_menu_principal_ui_qml.md) con el puente ResumenSistema
# real y un backend simulado: datos en pantalla, estados de las tarjetas (D-12,
# D-13, D-20, MP-14), aviso sin conexión (D-16), barra anclada abajo a 1196x1917
# y a 9:16, señales, ventanas flotantes (D-21) con la curva pedida solo al abrir,
# y cero avisos del motor QML. En subproceso para tener un QGuiApplication propio.
# Offscreen: MultiEffect (IconoColor) no se dibuja; se comprueba geometría y
# comportamiento, no color.

import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

_RAIZ = Path(__file__).resolve().parents[1]
_QML = _RAIZ / "src" / "autoclave" / "ui_qml" / "qml"

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from unittest.mock import MagicMock
    from PySide6.QtCore import Property, QObject, Qt, QUrl, Signal, Slot
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtCore import QMetaObject
    from PySide6.QtTest import QSignalSpy, QTest
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from datetime import date
    from autoclave.ui_qml.bridge.acciones_ciclos import AccionesCiclos
    from autoclave.ui_qml.bridge.ciclos_historial import CiclosHistorial
    from autoclave.ui_qml.bridge.reporte_resumen import ReporteResumen
    from autoclave.ui_qml.bridge.resumen_sistema import ResumenSistema
    from autoclave.ui_qml.exportacion.config_correo import ConfigCorreo
    from autoclave.ui_qml.exportacion.correo import ResultadoEnvio

    ancho, alto, falla = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3] == "falla"

    RESUMEN = {"ciclos_totales": 1248, "ciclos_hoy": 5, "ultimo_ciclo": {
        "id": 42, "numero_ciclo": 1248, "fecha_inicio": "2026-10-12T14:25:00",
        "fecha_fin": "2026-10-12T15:00:00", "programa_id": "instrumental_134",
        "programa_nombre": "Instrumental 134", "programa_numero": 2,
        "resultado": "FALLO_CALENTAMIENTO", "operador": None}}
    GRAFICA = {"ciclo_db_id": 42, "lecturas": [
        {"id": i, "t_s": float(i), "fase": "CALENTAMIENTO", "fase_ui": "calentamiento",
         "temp_camara": 40.0 + i, "temp_ref": 39.0 + i, "pres_camara": 100.0} for i in range(1, 61)]}
    def fila(i, resultado):
        return {"id": i, "numero_ciclo": i, "fecha_inicio": "2026-10-12T0%d:00:00" % (i % 10),
                "fecha_fin": "2026-10-12T0%d:40:00" % (i % 10), "programa_id": "instrumental_134",
                "programa_nombre": "Instrumental 134", "programa_numero": 2,
                "resultado": resultado, "operador": None}
    LISTA = {"truncado": False, "ciclos": [fila(91, "COMPLETADO"), fila(90, "FALLO_SECADO")]}
    RESUMEN_PERIODO = {"desde": "2026-10-12", "hasta": "2026-10-12", "serie": "S", "modelo": "M",
        "totales": {"total": 4, "completados": 3, "fallos": 1, "cancelados": 0, "sin_cierre": 0},
        "por_programa": [{"programa_id": "instrumental_134", "programa_nombre": "Instrumental 134",
                          "programa_numero": 2, "total": 4, "completados": 3, "fallos": 1,
                          "cancelados": 0, "sin_cierre": 0}],
        "causas_fallo": [{"causa": "FALLO_SECADO", "cantidad": 1}]}
    pedidos = []
    listas = []

    def get(ruta, params=None):
        pedidos.append(ruta)
        if ruta == "/cycle/list":
            listas.append(dict(params))
        if falla:
            raise ConnectionError("sin backend")
        if ruta == "/cycle/list":
            return {**LISTA, "periodo": params["periodo"]}
        if ruta == "/report/summary":
            return {**RESUMEN_PERIODO, "periodo": params["periodo"]}
        if ruta == "/report/failures":     # D8-5.6 (tanda 8)
            return {"periodo": params["periodo"], "causa": params["causa"], "total": 1,
                    "pagina": 1, "paginas": 1, "por_pagina": 20,
                    "ciclos": [{**fila(90, "FALLO_SECADO"), "operador": "Ana Pérez"}]}
        if ruta.endswith("/ticket"):
            i = int(ruta.split("/")[3])
            return {"ciclo": {**fila(i, "COMPLETADO"), "nombre_ciclo": "Instrumental 134",
                              "serie": "S", "modelo": "M", "version_sw": "1",
                              "tipo_ciclo": "instrumental_134", "temp_esterilizacion": 134,
                              "tiempo_esterilizacion": 4}, "lecturas": []}
        return RESUMEN if ruta == "/cycle/summary" else GRAFICA

    backend = MagicMock()
    backend.get.side_effect = get

    app = QGuiApplication([])
    _cargar_fuentes()
    resumen = ResumenSistema(backend, ejecutar=lambda t: t())
    historial = CiclosHistorial(backend, ejecutar=lambda t: t(), hoy=lambda: date(2026, 10, 12))
    reporte = ReporteResumen(backend, ejecutar=lambda t: t(), hoy=lambda: date(2026, 10, 12))
    impresos, correos = [], []
    backend.post.side_effect = lambda ruta, body: (impresos.append((ruta, body)),
                                                   {"ok": True, "impresos": len(body.get("ids", []))})[1]
    config = ConfigCorreo("equipo@x.com", "smtp.x.com", 587,
                          [{"nombre": "Mantenimiento", "correo": "mant@x.com"}], "clave")
    acciones = AccionesCiclos(backend, cargar_config=lambda: config,
                              ejecutar=lambda t: t(),
                              generar_pdf=lambda ruta, *a: open(ruta, "wb").write(b"%PDF"),
                              generar_pdf_resumen=lambda ruta, *a: open(ruta, "wb").write(b"%PDF"),
                              generar_pdf_consolidado=lambda ruta, *a, **k: (
                                  open(ruta, "wb").write(b"%PDF"), [])[1],
                              # C2 (tanda 7): el relay simulado acepta al destinatario
                              enviar=lambda c, m: (correos.append(m["To"]), ResultadoEnvio(
                                  (m["To"],), {}))[1])

    class InfoEquipo(QObject):          # misma interfaz que bridge/info_equipo.py
        filasChanged = Signal()
        def __init__(self):
            super().__init__(); self.actualizaciones = 0
        @Slot()
        def actualizar(self): self.actualizaciones += 1
        @Property("QVariantList", notify=filasChanged)
        def filas(self):
            return [{"clave": "modelo", "valor": "SPK-AVH-450", "disponible": True}]
    info = InfoEquipo()
    engine = QQmlApplicationEngine()
    avisos = []
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    engine.addImportPath(QML_DIR)
    engine.setInitialProperties({"resumen": resumen,
                                 "infoEquipo": info, "historial": historial,
                                 "acciones": acciones, "reporte": reporte})
    engine.load(QUrl.fromLocalFile(f"{QML_DIR}/Pruebas/PruebaMenuPrincipal.qml"))
    w = engine.rootObjects()[0]
    w.setWidth(ancho); w.setHeight(alto); w.show()
    QTest.qWait(300)

    def obj(nombre):
        return w.findChild(QObject, nombre)

    def geo(o):
        r = o.mapRectToScene(o.boundingRect())
        return [round(r.x(), 1), round(r.y(), 1), round(r.width(), 1), round(r.height(), 1)]

    def tocar(o, punto=None):
        c = o.mapToScene(o.boundingRect().center() if punto is None else punto).toPoint()
        QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, c)
        QTest.qWait(30)

    def item(o, nombre):            # por el árbol visual (los delegados de Repeater no son hijos QObject)
        for h in o.childItems():
            if h.objectName() == nombre:
                return h
            encontrado = item(h, nombre)
            if encontrado is not None:
                return encontrado
        return None

    def textos(o):
        for h in o.childItems():
            if h.inherits("QQuickText") and h.isVisible():
                yield h.property("text")
            yield from textos(h)

    menu = obj("menuPrincipal")
    def espia(o, firma):
        mo = o.metaObject()
        return QSignalSpy(o, mo.method(mo.indexOfSignal(firma)))

    r = {"avisos": avisos, "sondeando": resumen.property("sondeando")}
    tarjetas = ["tarjetaIniciarSesion", "tarjetaHistorial", "tarjetaReportes",
                "tarjetaInformacion", "resumenCiclosTotales",
                "resumenMantenimiento", "resumenCiclosHoy", "resumenUltimoCiclo"]
    r["habilitadas"] = {n: obj(n).property("enabled") for n in tarjetas}
    r["interactivas"] = {n: obj(n).property("interactiva") for n in
                         ("resumenCiclosTotales", "resumenCiclosHoy")}
    r["geo"] = {n: geo(obj(n)) for n in tarjetas + ["barraInferiorMenu", "encabezadoMenu",
                                                     "tituloMenu", "tituloResumen"]}
    r["escena"] = [w.contentItem().width(), w.contentItem().height()]
    r["aviso_visible"] = obj("avisoSinConexion").property("visible")
    r["textos_resumen"] = {n: list(textos(obj(n))) for n in
                           ("resumenCiclosTotales", "resumenCiclosHoy", "resumenUltimoCiclo",
                            "resumenMantenimiento")}

    def ventanas_abiertas():
        return sorted(n for n in ("ventanaUltimoCiclo", "ventanaMantenimiento",
                                  "ventanaCiclosHoy", "ventanaHistorial", "ventanaReportes")
                      if obj(n).property("visible"))

    # señales: Iniciar sesión emite. Sin engranaje en el menú.
    s_sesion = espia(menu, "iniciarSesionPulsado()")
    tocar(obj("tarjetaIniciarSesion"))
    r["senales"] = {"sesion": s_sesion.count()}
    r["sin_engranaje"] = obj("zonaEngranaje") is None and \
        menu.metaObject().indexOfSignal("ajustesPulsado()") == -1

    # Ciclos totales: solo informativa (no emite ni abre nada)
    s_tot = espia(menu, "ciclosTotalesPulsado()")
    tocar(obj("resumenCiclosTotales"))
    r["totales"] = {"senal": s_tot.count(), "ventanas": ventanas_abiertas()}

    # Último ciclo: abre y pide la curva solo al abrir
    r["pedidos_antes"] = list(pedidos)
    tocar(obj("resumenUltimoCiclo"))
    v = obj("ventanaUltimoCiclo")
    r["ultimo_abierta"] = v.property("visible")
    r["pedidos_despues"] = list(pedidos)
    r["grafica_no_disponible"] = v.findChild(QObject, "graficaNoDisponible").property("visible")
    r["textos_ventana"] = list(textos(v))
    tocar(v.findChild(QObject, "botonCerrarVentana"))
    r["ultimo_cerrada"] = not v.property("visible")
    tocar(obj("resumenMantenimiento"))
    vm = obj("ventanaMantenimiento")
    r["mant_abierta"] = vm.property("visible")
    r["textos_mant"] = list(textos(vm))
    QMetaObject.invokeMethod(vm, "cerrar")

    # Ciclos hoy: listado de terminados hoy; tocar una fila muestra su gráfica y datos
    tocar(obj("resumenCiclosHoy"))
    vh = obj("ventanaCiclosHoy")
    r["hoy_abierta"] = vh.property("visible")
    r["hoy_pedido"] = listas[-1] if listas else None
    lista_hoy = vh.findChild(QObject, "listaCiclosHoy")
    r["hoy_textos_lista"] = list(textos(lista_hoy))
    vista = lista_hoy.findChild(QObject, "vistaListaCiclos")
    alto_fila = lista_hoy.property("altoFila")
    from PySide6.QtCore import QPointF
    tocar(vista, QPointF(vista.width() / 2, alto_fila * 1.5))   # segunda fila: ciclo 90
    r["hoy_titulo"] = vh.property("titulo")
    r["hoy_pedidos_grafica"] = [p for p in pedidos if p.startswith("/cycle/history/")]
    detalle = vh.findChild(QObject, "detalleCicloHoy")
    r["hoy_detalle_visible"] = detalle.isVisible()
    r["hoy_textos_detalle"] = list(textos(detalle))
    r["hoy_grafica_disponible"] = historial.property("graficaDisponible")
    tocar(vh.findChild(QObject, "botonVolverListado"))
    r["hoy_volvio"] = lista_hoy.isVisible() and not detalle.isVisible()
    r["hoy_grafica_tras_volver"] = historial.property("graficaDisponible")
    QMetaObject.invokeMethod(vh, "cerrar")

    # Historial: periodo de calendario con flechas, casillas, imprimir y correo,
    # y el detalle del ciclo tocado con sus propias acciones
    tocar(obj("tarjetaHistorial"))
    vhi = obj("ventanaHistorial")
    r["hist_abierta"] = vhi.property("visible")
    pedidos_hist = [dict(listas[-1])]
    for f in ("filtro_semana", "filtro_mes"):
        tocar(item(vhi, f))
        pedidos_hist.append(dict(listas[-1]))
    r["hist_pedidos"] = pedidos_hist
    r["hist_periodo"] = vhi.property("periodo")
    rotulo = item(vhi, "rotuloPeriodo")
    siguiente = item(vhi, "flechaSiguiente")
    r["hist_rotulo"] = rotulo.property("text")
    r["hist_siguiente_actual"] = siguiente.property("habilitada")
    tocar(item(vhi, "flechaAnterior"))
    r["hist_anterior"] = [dict(listas[-1]), rotulo.property("text"), siguiente.property("habilitada")]
    tocar(siguiente)
    r["hist_siguiente"] = [listas[-1]["fecha"], rotulo.property("text")]
    lista_hist = vhi.findChild(QObject, "listaHistorial")
    r["hist_textos"] = list(textos(lista_hist))

    if not falla:   # sin backend no hay ciclos que marcar ni abrir
        imprimir = item(vhi, "botonImprimirMarcados")
        r["hist_imprimir_sin_marcar"] = imprimir.property("habilitado")
        tocar(item(lista_hist, "casilla_91"))
        r["hist_marcados"] = historial.property("seleccionados")
        r["hist_cuenta"] = item(vhi, "cuentaMarcados").property("text")
        tocar(imprimir)
        r["hist_impresos"] = [list(i) for i in impresos]
        r["hist_aviso"] = item(vhi, "textoAvisoAccion").property("text")
        tocar(item(lista_hist, "casillaTodas"))
        r["hist_todos"] = historial.property("seleccionados")
        tocar(item(vhi, "botonEnviarMarcados"))
        r["hist_selector"] = item(vhi, "selectorDestino").property("visible")
        tocar(item(vhi, "destino_Mantenimiento"))
        r["hist_correos"] = list(correos)
        r["hist_aviso_correo"] = item(vhi, "textoAvisoAccion").property("text")
        tocar(item(vhi, "botonEnviarMarcados"))
        tocar(item(vhi, "destinoOtro"))
        r["hist_teclado"] = obj("panelTeclado").property("abierto")
        tocar(item(vhi, "botonCancelarDestino"))
        r["hist_teclado_cancelado"] = [obj("panelTeclado").property("abierto"),
                                       item(vhi, "selectorDestino").property("visible")]

        graficas_antes = len([p for p in pedidos if p.startswith("/cycle/history/")])
        vista_h = lista_hist.findChild(QObject, "vistaListaCiclos")
        tocar(vista_h, QPointF(vista_h.width() / 2, lista_hist.property("altoFila") * 1.5))
        r["hist_titulo"] = vhi.property("titulo")
        r["hist_pedido_grafica"] = [p for p in pedidos if p.startswith("/cycle/history/")][graficas_antes:]
        r["hist_detalle"] = vhi.findChild(QObject, "detalleCicloHistorial").isVisible()
        tocar(item(vhi, "botonImprimirCiclo"))
        r["hist_impreso_detalle"] = impresos[-1][1]
        tocar(item(vhi, "botonVolverHistorial"))
        r["hist_volvio"] = lista_hist.isVisible()
    QMetaObject.invokeMethod(vhi, "cerrar")

    # Reportes: resumen del periodo con flechas, imprimir y enviar por correo
    tocar(obj("tarjetaReportes"))
    vr = obj("ventanaReportes")
    r["rep_abierta"] = vr.property("visible")
    r["rep_pedido"] = [p for p in pedidos if p == "/report/summary"][-1:] and reporte.property("fecha")
    if not falla:
        tocar(item(vr, "filtro_mes"))
        r["rep_rotulo"] = item(vr, "rotuloPeriodo").property("text")
        tocar(item(vr, "flechaAnterior"))
        r["rep_anterior"] = [reporte.property("fecha"), item(vr, "rotuloPeriodo").property("text"),
                             item(vr, "flechaSiguiente").property("habilitada")]
        r["rep_textos"] = list(textos(vr.findChild(QObject, "resumenPeriodo")))
        tocar(item(vr, "botonImprimirResumen"))
        r["rep_impreso"] = list(impresos[-1])
        r["rep_aviso"] = item(vr, "textoAvisoAccion").property("text")
        tocar(item(vr, "botonEnviarResumen"))
        r["rep_selector"] = item(vr, "selectorDestinoReportes").property("visible")
        tocar(item(item(vr, "selectorDestinoReportes"), "destino_Mantenimiento"))
        r["rep_correos"] = list(correos)
        # D8-5.6: tocar una causa de fallo despliega sus ciclos; tocar uno abre su detalle
        tocar(item(vr, "causa_FALLO_SECADO"))
        listado = item(vr, "listadoFallo")
        lista_f = item(vr, "listaFallo")
        r["fal_pedido"] = [p for p in pedidos if p == "/report/failures"][-1:]
        r["fal_vista"] = [listado.isVisible(), vr.findChild(QObject, "resumenPeriodo").isVisible(),
                          item(vr, "botonImprimirResumen").isVisible(),
                          item(vr, "paginacionFallo").isVisible()]
        r["fal_titulo"] = item(vr, "tituloFallo").property("text")
        r["fal_textos"] = list(textos(lista_f))
        graficas_antes = len([p for p in pedidos if p.startswith("/cycle/history/")])
        vista_f = lista_f.findChild(QObject, "vistaListaCiclos")
        tocar(vista_f, QPointF(vista_f.width() / 2, lista_f.property("altoFila") * 0.5))
        r["fal_ciclo"] = [vr.property("titulo"), listado.isVisible(),
                          vr.findChild(QObject, "detalleCicloFallo").isVisible()]
        r["fal_grafica"] = [p for p in pedidos if p.startswith("/cycle/history/")][graficas_antes:]
        tocar(item(vr, "botonImprimirCicloFallo"))
        r["fal_impreso"] = list(impresos[-1])
        tocar(item(vr, "botonVolverFallo"))
        r["fal_volvio"] = [listado.isVisible(), vr.property("titulo")]
        tocar(item(vr, "botonVolverResumen"))
        r["fal_resumen"] = [listado.isVisible(), vr.findChild(QObject, "resumenPeriodo").isVisible(),
                            reporte.property("causaFallo")]
        # pestaña Consolidado: mismo periodo, solo correo
        tocar(item(vr, "pestana_consolidado"))
        r["con_visible"] = [vr.findChild(QObject, "consolidado").isVisible(),
                            vr.findChild(QObject, "resumenPeriodo").isVisible(),
                            item(vr, "botonImprimirResumen").isVisible()]
        r["con_cuenta"] = item(vr, "cuentaConsolidado").property("text")
        r["con_rotulo"] = item(vr, "rotuloPeriodo").property("text")
        tocar(item(vr, "botonEnviarResumen"))
        tocar(item(item(vr, "selectorDestinoReportes"), "destino_Mantenimiento"))
        r["con_correos"] = list(correos)
        r["con_aviso"] = item(vr, "textoAvisoAccion").property("text")
        # Diario conserva la fecha vista (septiembre), no vuelve a hoy
        tocar(item(vr, "filtro_dia"))
        r["con_dia"] = [item(vr, "rotuloPeriodo").property("text"), reporte.property("fecha")]
    else:
        r["rep_aviso_falla"] = item(vr, "avisoReporte").property("text")
        r["rep_botones_falla"] = [item(vr, "botonImprimirResumen").property("habilitado"),
                                  item(vr, "botonEnviarResumen").property("habilitado")]
    QMetaObject.invokeMethod(vr, "cerrar")

    # Información: abre el panel de información del equipo (el de la esquina
    # inferior izquierda de la pantalla de preciclo) y pide actualizar sus datos
    pe = obj("panelEquipoMenu")
    r["equipo_antes"] = pe.property("visible")
    tocar(obj("tarjetaInformacion"))
    r["equipo_abierto"] = pe.property("visible")
    r["equipo_actualizaciones"] = info.actualizaciones
    r["textos_equipo"] = list(textos(pe))
    QMetaObject.invokeMethod(pe, "cerrar")

    # Campana: abre el panel de notificaciones
    pn = obj("panelNotificacionesMenu")
    r["notif_antes"] = pn.property("visible")
    tocar(obj("zonaCampana"))
    r["notif_abierto"] = pn.property("visible")
    print("RESULTADO=" + json.dumps(r, ensure_ascii=False))
""")


def _correr(ancho, alto, modo="ok"):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, "-c", _SCRIPT, str(ancho), str(alto), modo],
                          capture_output=True, text=True, encoding="utf-8", env=env,
                          timeout=90, cwd=_RAIZ)
    linea = [l for l in proc.stdout.splitlines() if l.startswith("RESULTADO=")]
    assert linea, proc.stdout + proc.stderr
    return json.loads(linea[0][len("RESULTADO="):])


@pytest.fixture(scope="module")
def r():
    return _correr(1196, 1917)


@pytest.fixture(scope="module")
def r916():
    return _correr(1080, 1920)


@pytest.fixture(scope="module")
def rfalla():
    return _correr(1196, 1917, "falla")


def test_sin_avisos_qml(r, r916, rfalla):
    assert r["avisos"] == [] and r916["avisos"] == [] and rfalla["avisos"] == []


def test_activa_el_sondeo_del_resumen(r):
    assert r["sondeando"] is True


def test_estados_de_las_tarjetas(r):
    assert r["habilitadas"] == {
        "tarjetaIniciarSesion": True, "tarjetaHistorial": True,
        "tarjetaReportes": True,
        "tarjetaInformacion": True,
        "resumenCiclosTotales": True, "resumenCiclosHoy": True,
        "resumenMantenimiento": True, "resumenUltimoCiclo": True,
    }
    # informativas: se ven normales (no atenuadas) pero no son botón
    assert r["interactivas"] == {"resumenCiclosTotales": False,
                                 "resumenCiclosHoy": True}


def _m(v, ancho=1196):
    return round(v * ancho / 1196, 1)


def test_tarjetas_en_las_coordenadas_del_v3(r):
    # v3 desplazado (-5, -1) al marco de 1196 x 1917 (informe de Fase 3)
    assert r["geo"]["tarjetaIniciarSesion"] == [54, 499, 716, 320]
    assert r["geo"]["tarjetaHistorial"] == [789, 499, 350, 320]
    # U5 (tanda 3): sin la tarjeta de secado, cada una a mitad de ancho
    assert r["geo"]["tarjetaReportes"] == [54, 843, 533, 320]
    assert r["geo"]["tarjetaInformacion"] == [606, 843, 533, 320]
    assert "tarjetaSecado" not in r["geo"]
    assert r["geo"]["resumenCiclosTotales"] == [54, 1295, 230, 330]
    assert r["geo"]["resumenMantenimiento"] == [300, 1295, 293, 330]
    assert r["geo"]["resumenCiclosHoy"] == [609, 1295, 206, 330]
    assert r["geo"]["resumenUltimoCiclo"] == [831, 1295, 308, 330]
    # D8-5.2 (tanda 8): la barra mide lo mismo que la grilla de tarjetas (54 a 1139)
    assert r["geo"]["barraInferiorMenu"] == [54, 1746, 1085, 139]
    assert r["geo"]["encabezadoMenu"][:2] == [0, 0]


def test_9_16_barra_anclada_abajo_y_alto_repartido(r916):
    k = 1080 / 1196
    alto_escena = r916["escena"][1]
    barra = r916["geo"]["barraInferiorMenu"]
    # barra pegada al borde inferior con el mismo margen que en el marco (1917 - 1885)
    assert barra[1] + barra[3] == pytest.approx(alto_escena - 32 * k, abs=1)
    # las tarjetas de menú no se mueven; el resumen baja la mitad del alto sobrante
    assert r916["geo"]["tarjetaIniciarSesion"][1] == pytest.approx(499 * k, abs=0.5)
    extra = alto_escena / k - 1917
    assert extra > 100
    assert r916["geo"]["resumenUltimoCiclo"][1] == pytest.approx((1295 + extra / 2) * k, abs=1)
    # nada se solapa: el resumen termina antes de la barra
    ult = r916["geo"]["resumenUltimoCiclo"]
    assert ult[1] + ult[3] < barra[1]


def test_datos_del_resumen_en_pantalla(r):
    t = r["textos_resumen"]
    assert "1248" in t["resumenCiclosTotales"] and "Realizados" in t["resumenCiclosTotales"]
    assert "5" in t["resumenCiclosHoy"]
    assert "12/10/2026  14:25" in t["resumenUltimoCiclo"]
    # resultado real de la base (fase con que terminó): se agrupa como Fallo
    assert "02" in t["resumenUltimoCiclo"] and "Fallo" in t["resumenUltimoCiclo"]
    assert "—" in t["resumenMantenimiento"]          # MP-06b: sin fuente
    assert r["aviso_visible"] is False


def test_sin_conexion_aviso_y_raya(rfalla):
    assert rfalla["aviso_visible"] is True
    t = rfalla["textos_resumen"]
    assert "1248" not in t["resumenCiclosTotales"] and "—" in t["resumenCiclosTotales"]
    assert "—" in t["resumenUltimoCiclo"]


def test_senales_y_sin_engranaje(r):
    assert r["senales"] == {"sesion": 1}
    assert r["sin_engranaje"] is True


def test_ciclos_totales_solo_informativa(r):
    assert r["totales"] == {"senal": 0, "ventanas": []}


def test_ventana_de_ultimo_ciclo_pide_la_curva_solo_al_abrir(r):
    assert not any("/graph" in p for p in r["pedidos_antes"])
    assert r["ultimo_abierta"] is True
    assert "/cycle/history/42/graph" in r["pedidos_despues"]
    assert r["grafica_no_disponible"] is False
    tv = r["textos_ventana"]
    assert "12/10/2026  14:25" in tv and "02 · Instrumental 134" in tv and "Fallo" in tv
    assert "FALLO_CALENTAMIENTO" in tv   # el detalle del cierre, bajo el resultado
    assert "Operador" in tv and tv[tv.index("Operador") + 1] == "—"   # sin operador registrado: "—"
    assert r["ultimo_cerrada"] is True


def test_ventana_de_mantenimiento_sin_datos(r):
    assert r["mant_abierta"] is True
    # M1 (tanda 3): próximo vencimiento, último mantenimiento y ciclos restantes
    assert r["textos_mant"].count("—") == 3


def test_sin_conexion_la_ventana_dice_grafica_no_disponible(rfalla):
    assert rfalla["ultimo_abierta"] is True
    assert rfalla["grafica_no_disponible"] is True


def test_es_json_trae_las_claves_que_usa_el_menu():
    fuente = (_QML / "Pantallas" / "MenuPrincipal.qml").read_text(encoding="utf-8")
    usadas = set(re.findall(r'I18n\.t\("(\w+)\.(\w+)",\s*I18n\.lang', fuente))
    textos = json.loads((_RAIZ / "src" / "autoclave" / "i18n" / "es.json")
                        .read_text(encoding="utf-8"))
    assert usadas
    faltan = [(s, c) for s, c in usadas if c not in textos.get(s, {})]
    assert faltan == []
    for clave in ("completado", "fallo", "cancelado"):   # I18n.t("menu.resultado_" + clave, ...)
        assert f"resultado_{clave}" in textos["menu"]


def test_marcadores_todo_pendientes():
    fuente = (_QML / "Pantallas" / "MenuPrincipal.qml").read_text(encoding="utf-8")
    for marca in ("TODO(MP-06a)",):
        assert marca in fuente
    assert "TODO(MP-03)" not in fuente      # U2 (tanda 2): Salir retirado
    assert "TODO(MP-11)" not in fuente and "tarjetaSecado" not in fuente   # U5 (tanda 3)
    assert "TODO(MP-14b)" not in fuente                                    # O1 (tanda 3)


def test_informacion_abre_el_panel_del_equipo(r):
    assert r["equipo_antes"] is False
    assert r["equipo_abierto"] is True
    assert r["equipo_actualizaciones"] == 1
    assert "SPK-AVH-450" in r["textos_equipo"]


def test_campana_abre_las_notificaciones(r):
    assert r["notif_antes"] is False
    assert r["notif_abierto"] is True


def test_ciclos_hoy_listado_y_detalle(r):
    assert r["hoy_abierta"] is True
    # los mismos ciclos que cuenta la tarjeta: terminados desde las 00:00
    assert r["hoy_pedido"] == {"periodo": "dia", "terminados": "true"}
    t = r["hoy_textos_lista"]
    assert "91" in t and "90" in t and "Completado" in t and "Fallo" in t
    # tocar la segunda fila abre su detalle y pide su curva
    assert r["hoy_titulo"] == "CICLO 90"
    assert r["hoy_pedidos_grafica"][-1] == "/cycle/history/90/graph"
    assert r["hoy_detalle_visible"] is True and r["hoy_grafica_disponible"] is True
    td = r["hoy_textos_detalle"]
    assert "Fallo" in td and "FALLO_SECADO" in td and "02 · Instrumental 134" in td
    # volver al listado descarta la curva
    assert r["hoy_volvio"] is True and r["hoy_grafica_tras_volver"] is False


def test_historial_periodo_de_calendario_con_flechas(r):
    assert r["hist_abierta"] is True
    assert r["hist_pedidos"] == [{"periodo": p, "terminados": "false", "fecha": "2026-10-12"}
                                 for p in ("dia", "semana", "mes")]
    assert r["hist_periodo"] == "mes"
    assert r["hist_rotulo"] == "Octubre 2026"
    assert r["hist_siguiente_actual"] is False          # no se avanza al futuro
    pedido, rotulo, siguiente = r["hist_anterior"]
    assert pedido == {"periodo": "mes", "terminados": "false", "fecha": "2026-09-01"}
    assert rotulo == "Septiembre 2026" and siguiente is True
    assert r["hist_siguiente"] == ["2026-10-12", "Octubre 2026"]
    assert "91" in r["hist_textos"]


def test_historial_marcar_imprimir_y_enviar(r):
    assert r["hist_imprimir_sin_marcar"] is False
    assert r["hist_marcados"] == [91] and r["hist_cuenta"] == "1 seleccionados"
    assert r["hist_impresos"] == [["/cycle/history/print", {"ids": [91]}]]
    assert "impresora" in r["hist_aviso"]
    assert r["hist_todos"] == [91, 90]
    assert r["hist_selector"] is True
    assert r["hist_correos"] == ["mant@x.com"]
    assert "mant@x.com" in r["hist_aviso_correo"]
    # Otro correo abre el teclado; Cancelar lo cierra junto con la elección de destino
    assert r["hist_teclado"] is True
    assert r["hist_teclado_cancelado"] == [False, False]


def test_historial_abre_el_ciclo_con_sus_acciones(r):
    assert r["hist_titulo"] == "CICLO 90"
    assert r["hist_pedido_grafica"] == ["/cycle/history/90/graph"]
    assert r["hist_detalle"] is True
    assert r["hist_impreso_detalle"] == {"ids": [90]}
    assert r["hist_volvio"] is True


def test_reportes_resumen_del_periodo(r):
    assert r["rep_abierta"] is True
    assert r["rep_pedido"] == "2026-10-12"                       # Diario de hoy al abrir
    assert r["rep_rotulo"] == "Octubre 2026"
    assert r["rep_anterior"] == ["2026-09-01", "Septiembre 2026", True]
    t = r["rep_textos"]
    assert "4" in t and "75%" in t and "02 · Instrumental 134" in t and "FALLO_SECADO" in t


def test_reportes_imprimir_y_enviar(r):
    assert r["rep_impreso"] == ["/report/summary/print", {"periodo": "mes", "fecha": "2026-09-01"}]
    assert "impresora" in r["rep_aviso"]
    assert r["rep_selector"] is True
    assert r["rep_correos"][-1] == "mant@x.com"


def test_reportes_sin_conexion(rfalla):
    assert rfalla["rep_abierta"] is True
    assert rfalla["rep_aviso_falla"] == "Sin conexión con el equipo"
    assert rfalla["rep_botones_falla"] == [False, False]


def test_reportes_ciclos_de_un_fallo(r):
    # D8-5.6 (tanda 8): causa -> listado (operador en vez de resultado) -> detalle con imprimir
    assert r["fal_pedido"] == ["/report/failures"]
    assert r["fal_vista"] == [True, False, False, False]          # una sola página: sin paginación
    assert r["fal_titulo"] == "Ciclos con el fallo FALLO_SECADO: 1"
    assert "Operador" in r["fal_textos"] and "Ana Pérez" in r["fal_textos"] and "90" in r["fal_textos"]
    assert r["fal_ciclo"] == ["CICLO 90", False, True]
    assert r["fal_grafica"] == ["/cycle/history/90/graph"]
    assert r["fal_impreso"] == ["/cycle/history/print", {"ids": [90]}]
    assert r["fal_volvio"] == [True, "REPORTES"]
    assert r["fal_resumen"] == [False, True, ""]


def test_reportes_consolidado(r):
    # el consolidado se ve en su pestaña; el resumen y la impresión se ocultan
    assert r["con_visible"] == [True, False, False]
    assert r["con_cuenta"] == "4" and r["con_rotulo"] == "Septiembre 2026"   # periodo común
    assert len(r["con_correos"]) == len(r["rep_correos"]) + 1 and r["con_correos"][-1] == "mant@x.com"
    assert "consolidado" in r["con_aviso"] and "mant@x.com" in r["con_aviso"]


def test_filtros_conservan_la_fecha_vista(r):
    assert r["con_dia"] == ["Martes 1 sep 2026", "2026-09-01"]
