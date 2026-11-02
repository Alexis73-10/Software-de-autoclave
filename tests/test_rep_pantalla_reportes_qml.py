"""Pantalla Reportes (etapa E de planeacion_dashboard_reportes.md, REP-01..REP-14).

Carga qml/Pruebas/PruebaReportes.qml (la pantalla real) offscreen con un backend
REAL de solo lectura sobre una base temporal sembrada (tests/helpers/
reportes_ejemplo.py) y toca la pantalla como un operador: periodo, calendario,
panel del día, causas de fallo, acciones, correo sin sesión y sin conexión.
Cada escenario corre en un subproceso con su propio QGuiApplication.
"""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from tests.helpers.textos_caben_qml import ESTADOS_REPORTES, revisar_reportes  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.req("REP-01")

_SCRIPT = textwrap.dedent(r"""
    import json, sys, tempfile
    from pathlib import Path
    from PySide6.QtCore import QObject, QPointF, QUrl, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave import i18n
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml.bridge import i18n_qml
    from autoclave.ui_qml.bridge.acciones_ciclos import AccionesCiclos
    from autoclave.ui_qml.bridge.ciclos_historial import CiclosHistorial
    from autoclave.ui_qml.bridge.reporte_dashboard import ReporteDashboard
    from autoclave.ui_qml.exportacion import correo
    from autoclave.ui_qml.exportacion.config_correo import ConfigCorreo
    from tests.helpers.reportes_ejemplo import ClienteReportes, HOY
    from tests.helpers.smtp_falso import SMTPSinTLS, SmtpFalso

    cfg = json.loads(sys.argv[1])
    i18n.cargar()
    i18n.fijar_idioma(cfg["idioma"])
    i18n_qml.instancia._consultar = lambda: None
    qapp = QGuiApplication([])
    _cargar_fuentes()
    r = {}
    destinos = [{"nombre": "Mantenimiento", "correo": "mant@x.com"}]
    if cfg["modo"] == "rechazo":
        destinos.append({"nombre": "Calidad", "correo": "malo@x.com"})
    if cfg["modo"] == "sin_destinos":
        destinos = []
    correos, entregados = [], []
    pdf = lambda ruta, *a, **k: (open(ruta, "wb").write(b"%PDF"), [])[1]

    with SmtpFalso(rechazar={"malo@x.com"}) as smtp, \
            ClienteReportes(Path(tempfile.mkdtemp()), sin_conexion=(cfg["modo"] == "sin_conexion")) as cli:
        config = ConfigCorreo("equipo@x.com", "127.0.0.1", smtp.puerto, destinos, "clave")
        if cfg["modo"] == "rechazo":
            enviar = lambda c, m: correo.enviar(c, m, smtp=SMTPSinTLS)
        else:
            enviar = lambda c, m: (correos.append(m["To"]), correo.ResultadoEnvio((m["To"],), {}))[1]
        rd = ReporteDashboard(cli, ejecutar=lambda t: t(), hoy=lambda: HOY)
        hist = CiclosHistorial(cli, ejecutar=lambda t: t(), hoy=lambda: HOY)
        acc = AccionesCiclos(cli, cargar_config=lambda: config, ejecutar=lambda t: t(), generar_pdf=pdf,
                             generar_pdf_resumen=pdf, generar_pdf_consolidado=pdf, enviar=enviar)
        engine = QQmlApplicationEngine()
        avisos = []
        engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
        engine.addImportPath(QML_DIR)
        engine.setInitialProperties({"reporteDashboard": rd, "acciones": acc, "historial": hist})
        engine.load(QUrl.fromLocalFile(QML_DIR + "/Pruebas/PruebaReportes.qml"))
        v = engine.rootObjects()[0]
        v.setProperty("width", 1200); v.setProperty("height", 1920)
        v.show()
        QTest.qWait(700)

        def buscar(nombre, it=None):
            it = it or v.contentItem()
            for h in it.childItems():
                if h.objectName() == nombre:
                    return h
                e = buscar(nombre, h)
                if e is not None:
                    return e
            return None

        flick = buscar("contenidoReportes")

        def ver(o):
            # lleva el elemento a la zona visible del Flickable
            y = o.mapToItem(flick.property("contentItem"), QPointF(0, 0)).y()
            tope = max(0, flick.property("contentHeight") - flick.height())
            flick.setProperty("contentY", max(0, min(tope, y - 200)))
            QTest.qWait(150)

        def tocar(o, punto=None, scroll=True):
            if scroll:
                ver(o)
            p = o.mapToScene(punto if punto is not None else o.boundingRect().center()).toPoint()
            QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, p)
            QTest.qWait(250)

        def visible(nombre):
            o = buscar(nombre)
            return bool(o is not None and o.isVisible())

        def texto(nombre):
            return buscar(nombre).property("text")

        pantalla = buscar("pantallaReportes")
        r["avisos"] = [a for a in avisos if "Binding loop" not in a]
        r["secciones"] = {n: visible(n) for n in (
            "seccionPeriodo", "seccionIndicadores", "seccionResultado", "seccionCiclosDia", "seccionProgramas",
            "seccionCalendario", "seccionCausas", "seccionMantenimiento", "seccionAlarmas",
            "seccionOperadores", "seccionAcciones", "tarjetaErrorReportes", "seccionCargando")}
        r["orden_y"] = [buscar(n).mapToItem(flick.property("contentItem"), QPointF(0, 0)).y() for n in (
            "seccionPeriodo", "seccionIndicadores", "seccionResultado", "seccionCiclosDia", "seccionProgramas",
            "seccionCalendario", "seccionCausas")]
        r["titulo"] = texto("rotuloPeriodo")
        r["rd0"] = [rd.property("periodo"), rd.property("fecha"), rd.property("programa")]

        if cfg["modo"] == "sin_conexion":
            r["error"] = [visible("tarjetaErrorReportes"), texto("textoErrorReportes"), visible("cuerpoReportes"),
                          buscar("botonImprimirResumen") is None or buscar("botonImprimirResumen").property("habilitado")]
            cli.sin_conexion = False
            tocar(buscar("botonReintentarReportes"), scroll=False)
            r["reintento"] = [visible("tarjetaErrorReportes"), visible("cuerpoReportes")]
        elif cfg["modo"] == "rechazo":
            tocar(buscar("botonEnviarResumen"))
            tocar(buscar("destinoTodos"), scroll=False)
            a = buscar("avisoAccionReportes")
            t = buscar("textoAvisoAccion", a)
            r["aviso"] = {"visible": a.isVisible(), "error": a.property("error"),
                          "fondo": a.property("color").name(), "color_texto": t.property("color").name(),
                          "texto": t.property("text")}
            r["entregados"] = [e["para"] for e in smtp.entregados]
        elif cfg["modo"] == "sin_destinos":
            v.setProperty("sesionActiva", False)
            QTest.qWait(150)
            r["sin_destinos"] = [buscar("botonEnviarResumen").property("habilitado"),
                                 buscar("botonEnviarConsolidado").property("habilitado"),
                                 texto("notaDestinoReportes"), pantalla.property("hayDestinoCorreo")]
            v.setProperty("sesionActiva", True)
            QTest.qWait(150)
            r["sin_destinos_con_sesion"] = [buscar("botonEnviarResumen").property("habilitado"),
                                            pantalla.property("hayDestinoCorreo")]
        else:
            # --- periodo: Año, flecha anterior, Mes
            tocar(buscar("filtro_anio"))
            r["anio"] = [rd.property("periodo"), texto("rotuloPeriodo"),
                         buscar("calendarioEjecucion").property("vistaAnio")]
            tocar(buscar("filtro_mes"))
            r["mes"] = [rd.property("periodo"), texto("rotuloPeriodo")]
            tocar(buscar("flechaAnterior"))
            r["anterior"] = [rd.property("fecha"), texto("rotuloPeriodo"), buscar("flechaSiguiente").property("habilitada")]
            tocar(buscar("flechaSiguiente"))
            r["siguiente"] = [rd.property("fecha"), texto("rotuloPeriodo")]
            tocar(buscar("filtro_semana"))
            r["semana"] = [rd.property("periodo")]
            tocar(buscar("filtro_mes"))
            r["indicadores"] = [buscar("indicador_" + k).isVisible() for k in ("ciclos", "exito", "fallos", "duracion")]
            r["sin_escrituras"] = list(cli.escrituras)
            r["rutas_get"] = sorted({ruta for _, ruta, _ in cli.llamadas if not ruta.startswith("/cycle/history")})

            # --- panel del día: tocar un día y luego un intento abre el detalle del ciclo
            rd.elegirDia("2026-10-08")
            QTest.qWait(300)
            r["dia"] = [rd.property("diaElegido"), texto("estadoPanelDia"), len(rd.property("ciclosDia"))]
            tocar(buscar("intento_0"))
            r["ciclo"] = [visible("capaCiclo"), visible("detalleCicloReportes")]
            r["ciclo_grafica"] = [ruta for _, ruta, _ in cli.llamadas if ruta.startswith("/cycle/history/") and ruta.endswith("/graph")]
            tocar(buscar("botonImprimirCiclo"), scroll=False)
            r["ciclo_impreso"] = list(cli.escrituras[-1])
            tocar(buscar("botonVolverCiclo"), scroll=False)
            r["ciclo_volvio"] = visible("capaCiclo")
            rd.elegirDia("2026-10-14")
            QTest.qWait(300)
            r["dia_falto"] = [texto("estadoPanelDia"), texto("explicacionPanelDia")]
            rd.cerrarDia()

            # --- causa de fallo: lista paginada y de ahí al detalle
            tocar(buscar("causa_FALLO_SECADO"))
            r["fallo"] = [visible("listadoFallo"), texto("tituloFallo"),
                          [x[1:] for x in cli.llamadas if x[1] == "/report/failures"][-1:]]
            lista = buscar("listaFallo")
            vista = buscar("vistaListaCiclos", lista)
            tocar(vista, QPointF(vista.width() / 2, lista.property("altoFila") * 1.5), scroll=False)
            r["fallo_ciclo"] = [visible("capaCiclo"), visible("detalleCicloReportes")]
            tocar(buscar("botonVolverCiclo"), scroll=False)
            tocar(buscar("botonVolverResumen"), scroll=False)
            r["fallo_volvio"] = [visible("listadoFallo"), rd.property("causaFallo")]

            # --- alarmas: 8 filas, «Ver todas» (lista completa paginada) y detalle de una fila
            lista_al = buscar("listaAlarmasPeriodo")
            ver(lista_al)
            r["alarmas_corta"] = [buscar("filaAlarmaPeriodo_%d" % i) is not None for i in range(9)]
            tocar(buscar("botonVerTodasAlarmas"))
            r["alarmas_panel"] = [lista_al.property("panelAbierto"), lista_al.property("paginas"),
                                  texto("textoPaginaAlarmas"), buscar("filaAlarmaTodas_0") is not None]
            tocar(buscar("botonPaginaSiguienteAlarmas"), scroll=False)
            r["alarmas_pagina2"] = [lista_al.property("pagina"), buscar("filaAlarmaTodas_1") is not None,
                                    buscar("filaAlarmaTodas_2") is not None]
            tocar(buscar("filaAlarmaTodas_0"), scroll=False)
            r["alarma_detalle"] = bool(buscar("detalleAlarmaReportes").property("abierta"))
            buscar("detalleAlarmaReportes").cerrar()
            tocar(buscar("botonCerrarTodasAlarmas"), scroll=False)
            r["alarmas_cerrado"] = lista_al.property("panelAbierto")
            fila = buscar("filaAlarmaPeriodo_0")
            tocar(fila)
            r["alarma_detalle_corta"] = bool(buscar("detalleAlarmaReportes").property("abierta"))
            buscar("detalleAlarmaReportes").cerrar()

            # --- impresión del resumen
            tocar(buscar("botonImprimirResumen"))
            r["impreso"] = list(cli.escrituras[-1])
            QTest.qWait(300)

            # --- correo con sesión: ofrece «Otro correo»; consolidado grande pide confirmación
            tocar(buscar("botonEnviarResumen"))
            r["correo_con_sesion"] = [visible("selectorDestinoReportes"), visible("destinoOtro")]
            tocar(buscar("botonCancelarDestino"), scroll=False)
            pantalla.setProperty("umbralConsolidado", 100)
            tocar(buscar("botonEnviarConsolidado"))
            r["consolidado_grande"] = [visible("confirmarConsolidado"), visible("selectorDestinoReportes")]
            r["consolidado_texto"] = buscar("confirmarConsolidado").property("cuerpo")
            buscar("confirmarConsolidado").cerrar()
            pantalla.setProperty("umbralConsolidado", 100000)
            tocar(buscar("botonEnviarConsolidado"))
            r["consolidado_chico"] = [visible("confirmarConsolidado"), visible("selectorDestinoReportes")]
            tocar(buscar("botonCancelarDestino"), scroll=False)

            # --- correo sin sesión: solo los guardados
            v.setProperty("sesionActiva", False)
            QTest.qWait(150)
            tocar(buscar("botonEnviarResumen"))
            r["correo_sin_sesion"] = [visible("selectorDestinoReportes"), visible("destinoOtro"),
                                      visible("notaInicieSesion"), visible("destino_Mantenimiento")]
            tocar(buscar("botonCancelarDestino"), scroll=False)
            v.setProperty("sesionActiva", True)

            # --- Inicio y Salir
            tocar(buscar("botonInicioReportes"), scroll=False)
            tocar(buscar("botonSalirReportes"), scroll=False)
            r["botones"] = [v.property("inicios"), v.property("salidas")]
            r["avisos_final"] = [a for a in avisos if "Binding loop" not in a]

    print("RESULTADO=" + json.dumps(r, ensure_ascii=False, default=str))
""")


def _correr(idioma: str, modo: str) -> dict:
    cfg = {"idioma": idioma, "modo": modo}
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    proc = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, json.dumps(cfg)],
                          capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ, timeout=300)
    linea = [x for x in proc.stdout.splitlines() if x.startswith("RESULTADO=")]
    assert linea, proc.stdout[-3000:] + proc.stderr[-3000:]
    return json.loads(linea[0][len("RESULTADO="):])


@pytest.fixture(scope="module")
def es():
    return _correr("es", "normal")


@pytest.fixture(scope="module")
def en():
    return _correr("en", "normal")


@pytest.fixture(scope="module")
def sin_conexion():
    return _correr("es", "sin_conexion")


@pytest.fixture(scope="module")
def rechazo():
    return _correr("es", "rechazo")


@pytest.fixture(scope="module")
def sin_destinos():
    return _correr("es", "sin_destinos")


def test_carga_sin_avisos_qml_en_es_y_en(es, en):
    assert es["avisos"] == [] and en["avisos"] == []
    assert es["avisos_final"] == [] and en["avisos_final"] == []


def test_secciones_visibles_sin_sesion_y_en_el_orden_del_plan(es):
    # DR-D09: todas las secciones se ven aunque no haya sesión (el arnés no la exige para leer)
    s = es["secciones"]
    for n in ("seccionPeriodo", "seccionIndicadores", "seccionResultado", "seccionCiclosDia", "seccionProgramas",
              "seccionCalendario", "seccionCausas", "seccionMantenimiento", "seccionAlarmas",
              "seccionOperadores", "seccionAcciones"):
        assert s[n] is True, n
    assert s["tarjetaErrorReportes"] is False and s["seccionCargando"] is False
    assert es["orden_y"] == sorted(es["orden_y"])        # Periodo, Indicadores, Resultado, Ciclos por día...
    assert es["rd0"] == ["mes", "2026-10-31", 1]          # se abre en Mes del mes actual y programa 01


def test_periodo_dia_semana_mes_anio_y_flechas(es, en):
    assert es["titulo"] == "Octubre 2026" and en["titulo"] == "October 2026"
    assert es["anio"] == ["anio", "2026", True]
    assert es["mes"] == ["mes", "Octubre 2026"]
    assert es["anterior"] == ["2026-09-01", "Septiembre 2026", True]
    assert es["siguiente"][1] == "Octubre 2026"
    assert es["semana"] == ["semana"]
    assert es["indicadores"] == [True, True, True, True]


def test_solo_lectura_nada_escribe_al_backend(es):
    assert es["sin_escrituras"] == []
    assert set(es["rutas_get"]) <= {"/report/dashboard", "/report/calendar", "/report/day-cycles",
                                    "/report/failures", "/maintenance", "/maintenance/records"}


def test_panel_del_dia_y_detalle_del_ciclo(es):
    assert es["dia"][0] == "2026-10-08" and es["dia"][2] == 2
    assert es["ciclo"] == [True, True]
    assert es["ciclo_grafica"], "al abrir el ciclo se pide su curva como en el Historial"
    assert es["ciclo_impreso"][0] == "/cycle/history/print" and es["ciclo_impreso"][1]["ids"]
    assert es["ciclo_volvio"] is False
    assert es["dia_falto"][0] == "Faltó"
    assert "4 ciclos de otros programas" in es["dia_falto"][1]


def test_causa_de_fallo_lista_y_detalle(es):
    assert es["fallo"][0] is True and es["fallo"][1] == "Ciclos con el fallo FALLO_SECADO: 2"
    assert es["fallo"][2][0][1]["causa"] == "FALLO_SECADO"
    assert es["fallo_ciclo"] == [True, True]
    assert es["fallo_volvio"] == [False, ""]


def test_alarmas_del_periodo_y_detalle(es):
    # REP-10: máximo 8 filas en la tarjeta y «Ver todas» con la lista completa paginada
    assert es["alarmas_corta"] == [True] * 8 + [False]
    assert es["alarmas_panel"] == [True, 2, "Página 1 de 2", True]
    assert es["alarmas_pagina2"] == [2, True, False]                 # 10 códigos: 2 en la 2.ª página
    assert es["alarma_detalle"] is True and es["alarma_detalle_corta"] is True
    assert es["alarmas_cerrado"] is False


def test_imprimir_resumen_del_periodo(es):
    assert es["impreso"] == ["/report/summary/print", {"periodo": "mes", "fecha": "2026-10-31"}]


def test_correo_con_sesion_sin_sesion_y_consolidado_grande(es, en):
    assert es["correo_con_sesion"] == [True, True]                   # con sesión: «Otro correo»
    assert es["correo_sin_sesion"] == [True, False, True, True]      # sin sesión: solo guardados + nota
    assert es["consolidado_grande"] == [True, False]                 # pide confirmación antes del destino
    assert "100" not in es["consolidado_texto"] and "MB" in es["consolidado_texto"]
    assert en["consolidado_texto"].startswith("The consolidated report includes ")
    assert es["consolidado_chico"] == [False, True]                  # bajo el umbral va directo al destino


def test_sin_destinatarios_guardados_y_sin_sesion_no_se_puede_enviar(sin_destinos):
    r = sin_destinos
    assert r["sin_destinos"][:2] == [False, False]
    assert r["sin_destinos"][2] == "No hay destinatarios guardados" and r["sin_destinos"][3] is False
    assert r["sin_destinos_con_sesion"] == [True, True]                  # con sesión basta escribir uno


def test_rechazo_parcial_del_correo_en_rojo_con_la_direccion(rechazo):
    a = rechazo["aviso"]
    assert a["visible"] is True and a["error"] is True
    assert a["fondo"] == "#ffecec" and a["color_texto"] == "#d00000"        # Colores.peligro*
    assert "malo@x.com" in a["texto"] and "mant@x.com" in a["texto"]
    assert rechazo["entregados"] == [["mant@x.com"]]


def test_sin_conexion_tarjeta_de_error_y_reintento(sin_conexion):
    visible_error, texto, cuerpo, _ = sin_conexion["error"]
    assert visible_error is True and cuerpo is False
    assert texto == "No se pudieron cargar los datos"
    assert sin_conexion["reintento"] == [False, True]


def test_inicio_y_salir(es):
    assert es["botones"] == [1, 1]


@pytest.mark.parametrize("idioma", ["es", "en"])
@pytest.mark.parametrize("ancho,alto", [(1200, 1920), (1024, 1638), (1080, 1920)])
def test_textos_caben_en_todos_los_estados(idioma, ancho, alto):
    r = revisar_reportes(idioma, ancho, alto)
    assert r["avisos"] == []
    assert [p["estado"] for p in r["pasos"]] == list(ESTADOS_REPORTES)
    for paso in r["pasos"]:
        assert paso["problemas"] == [], paso["estado"]
