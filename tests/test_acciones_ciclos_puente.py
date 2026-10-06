# tests/test_acciones_ciclos_puente.py
#
# AccionesCiclos (ui_qml/bridge/acciones_ciclos.py): reimprimir ciclos del
# Historial en la impresora térmica (POST /cycle/history/print) y enviarlos por
# correo como PDF con gráfica. Hilo de trabajo, PDF y SMTP simulados.

import os
import smtplib
import sys
from unittest.mock import MagicMock

import pytest
import requests

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from autoclave.ui_qml.app import cargar_textos
from autoclave.ui_qml.bridge.acciones_ciclos import AccionesCiclos
from autoclave.ui_qml.exportacion.config_correo import ConfigCorreo

_DESTINOS = [{"nombre": "Mantenimiento", "correo": "mant@x.com"}]


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    # QApplication (no QCoreApplication): este archivo corre antes que las pruebas
    # de vistas PySide, que reutilizan la instancia para crear widgets
    return QCoreApplication.instance() or QApplication(sys.argv)


def _ticket(i):
    return {"ciclo": {"id": i, "numero_ciclo": i, "serie": "S1", "modelo": "M", "version_sw": "1",
                      "nombre_ciclo": "Instrumental 134", "tipo_ciclo": "instrumental_134",
                      "temp_esterilizacion": 134, "tiempo_esterilizacion": 4,
                      "fecha_inicio": "2026-09-15T08:00:00", "fecha_fin": "2026-09-15T08:40:00",
                      "resultado": "FALLO_SECADO", "motivo_fallo": None},
            "lecturas": [{"fase_codigo": "C", "timestamp_rel": "00:01:00",
                          "temp_camara": 120.0, "pres_camara": 200.0}]}


def _grafica(i):
    return {"ciclo_db_id": i, "lecturas": [
        {"id": 1, "t_s": 0.0, "fase": "PRE_VACIO", "fase_ui": "vacio",
         "temp_camara": 40.0, "temp_ref": 35.0, "pres_camara": 101.3}]}


def _get(ruta, **k):
    i = int(ruta.split("/")[3])
    return _ticket(i) if ruta.endswith("/ticket") else _grafica(i)


class _Entorno:
    def __init__(self, config=None, post=None, get=_get, enviar=None):
        self.backend = MagicMock()
        self.backend.post.side_effect = post or (lambda ruta, body: {"ok": True, "impresos": len(body["ids"])})
        self.backend.get.side_effect = get
        self.pdfs = []
        self.enviados = []
        self.config = config or ConfigCorreo("equipo@gmail.com", "smtp.gmail.com", 587, _DESTINOS, "clave")

        def generar_pdf(ruta, datos, ticket, grafica, fases, textos, consigna=None):
            self.pdfs.append({"datos": datos, "ticket": ticket, "grafica": grafica, "fases": fases,
                              "consigna": consigna, "textos": textos})
            with open(ruta, "wb") as f:
                f.write(b"%PDF-" + datos["titulo"].encode())

        self.a = AccionesCiclos(self.backend, cargar_textos(), cargar_config=lambda: self.config,
                                ejecutar=lambda t: t(), generar_pdf=generar_pdf,
                                enviar=enviar or (lambda config, m: self.enviados.append(m)))
        self.terminadas = QSignalSpy(self.a.accionTerminada)

    def resultado(self):
        QCoreApplication.processEvents()
        assert self.terminadas.count() == 1
        return tuple(self.terminadas.at(0))


def _error_http(codigo, detalle=None):
    respuesta = MagicMock(status_code=codigo)
    respuesta.json.return_value = {"detail": detalle}
    return requests.HTTPError(response=respuesta)


# ── imprimir ─────────────────────────────────────────────────────────────

def test_imprimir_pide_al_backend_los_ciclos_marcados():
    e = _Entorno()
    e.a.imprimir([12, 11.0])
    exito, mensaje = e.resultado()
    e.backend.post.assert_called_once_with("/cycle/history/print", {"ids": [12, 11]})
    assert exito and "2" in mensaje
    assert e.a.ocupado is False


def test_imprimir_durante_un_ciclo():
    def post(ruta, body):
        raise _error_http(409)
    e = _Entorno(post=post)
    e.a.imprimir([12])
    exito, mensaje = e.resultado()
    assert not exito and "ciclo en curso" in mensaje


@pytest.mark.parametrize("estado, texto", [
    ("desconectada", "La impresora no está conectada"),
    ("sin_papel", "La impresora no tiene papel"),
    ("no_instalada", "La impresora no está instalada"),
    ("error", "La impresora reporta un error"),
    ("otro", "La impresora reporta un error"),
])
def test_imprimir_avisa_si_la_impresora_no_esta_lista(estado, texto):
    def post(ruta, body):
        raise _error_http(503, {"impresora": estado})
    e = _Entorno(post=post)
    e.a.imprimir([12])
    exito, mensaje = e.resultado()
    assert not exito and mensaje == texto


def test_imprimir_sin_backend():
    def post(ruta, body):
        raise requests.ConnectionError()
    e = _Entorno(post=post)
    e.a.imprimir([12])
    exito, mensaje = e.resultado()
    assert not exito and "conexión" in mensaje


def test_imprimir_sin_ciclos_no_hace_nada():
    e = _Entorno()
    e.a.imprimir([])
    QCoreApplication.processEvents()
    e.backend.post.assert_not_called() 
    assert e.terminadas.count() == 0


def test_no_acepta_otra_accion_mientras_trabaja():
    pendientes = []
    e = _Entorno()
    e.a._ejecutar = pendientes.append
    e.a.imprimir([12])
    assert e.a.ocupado is True
    e.a.imprimir([13])
    e.a.enviarCorreo([13], "mant@x.com")
    assert len(pendientes) == 1


# ── correo ───────────────────────────────────────────────────────────────

def test_destinos_y_estado_de_la_configuracion():
    e = _Entorno()
    assert e.a.correoConfigurado is True and e.a.destinos == _DESTINOS
    e.config = ConfigCorreo(destinos=_DESTINOS)
    espia = QSignalSpy(e.a.correoChanged)
    e.a.actualizarCorreo()
    assert e.a.correoConfigurado is False and espia.count() == 1


def test_enviar_un_ciclo_con_su_pdf_y_grafica():
    e = _Entorno()
    e.a.enviarCorreo([12], "mant@x.com")
    exito, mensaje = e.resultado()
    assert exito and "mant@x.com" in mensaje
    pdf = e.pdfs[0]
    assert "000012" in pdf["datos"]["titulo"] and "Instrumental 134" in pdf["datos"]["titulo"]
    assert "Ciclo No.: 000012" in pdf["ticket"]            # el mismo ticket de la impresora
    assert pdf["grafica"]["temp_camara"] == [40.0]
    assert pdf["fases"] == [{"clave": "vacio", "inicioMin": 0.0}]
    # la curva de ejemplo no llega a esterilizar: sin consigna
    assert pdf["consigna"] is None
    assert pdf["textos"]["consignas"]["temp"] == "Consigna temp."
    campos = dict(pdf["datos"]["campos"])
    assert "Fallo" in campos["Resultado"]                   # texto del resultado (FALLO_SECADO)
    m = e.enviados[0]
    assert m["To"] == "mant@x.com" and m["From"] == "equipo@gmail.com"
    adjunto = next(m.iter_attachments())
    assert adjunto.get_filename() == "ciclo_000012.pdf"


def test_enviar_varios_ciclos_en_un_zip():
    e = _Entorno()
    e.a.enviarCorreo([12, 13], "mant@x.com")
    exito, _ = e.resultado()
    assert exito and len(e.pdfs) == 2
    assert next(e.enviados[0].iter_attachments()).get_content_type() == "application/zip"


def test_destino_invalido_no_envia():
    e = _Entorno()
    e.a.enviarCorreo([12], "sin-arroba")
    exito, mensaje = e.resultado()
    assert not exito and "no es válido" in mensaje
    assert e.enviados == []


def test_correo_no_configurado_no_envia():
    e = _Entorno(config=ConfigCorreo(destinos=_DESTINOS))
    e.a.enviarCorreo([12], "mant@x.com")
    exito, mensaje = e.resultado()
    assert not exito and "no configurado" in mensaje.lower()
    assert e.enviados == [] and e.pdfs == []


def test_sin_backend_no_envia():
    def get(ruta, **k):
        raise requests.ConnectionError()
    e = _Entorno(get=get)
    e.a.enviarCorreo([12], "mant@x.com")
    exito, mensaje = e.resultado()
    assert not exito and "conexión con el equipo" in mensaje
    assert e.enviados == []


def test_error_de_autenticacion():
    def enviar(config, m):
        raise smtplib.SMTPAuthenticationError(535, b"bad")
    e = _Entorno(enviar=enviar)
    e.a.enviarCorreo([12], "mant@x.com")
    exito, mensaje = e.resultado()
    assert not exito and "contraseña" in mensaje


def test_error_de_red_al_enviar():
    def enviar(config, m):
        raise OSError("sin internet")
    e = _Entorno(enviar=enviar)
    e.a.enviarCorreo([12], "mant@x.com")
    exito, mensaje = e.resultado()
    assert not exito and "internet" in mensaje
    assert e.a.ocupado is False


# ── resumen por periodo (pantalla Reportes) ──────────────────────────────

_RESUMEN = {
    "periodo": "mes", "desde": "2026-09-01", "hasta": "2026-09-30", "serie": "SPK-1", "modelo": "AVH",
    "totales": {"total": 3, "completados": 2, "fallos": 1, "cancelados": 0, "sin_cierre": 0},
    "por_programa": [{"programa_id": "instrumental_134", "programa_nombre": "Instrumental 134",
                      "programa_numero": 2, "total": 3, "completados": 2, "fallos": 1,
                      "cancelados": 0, "sin_cierre": 0}],
    "causas_fallo": [{"causa": "FALLO_SECADO", "cantidad": 1}],
}


def test_imprimir_resumen():
    e = _Entorno(post=lambda ruta, body: {"ok": True})
    e.a.imprimirResumen("mes", "2026-09-15")
    exito, mensaje = e.resultado()
    e.backend.post.assert_called_once_with("/report/summary/print", {"periodo": "mes", "fecha": "2026-09-15"})
    assert exito and "impresora" in mensaje


def test_imprimir_resumen_con_la_impresora_desconectada():
    def post(ruta, body):
        raise _error_http(503, {"impresora": "desconectada"})
    e = _Entorno(post=post)
    e.a.imprimirResumen("mes", "2026-09-15")
    assert e.resultado() == (False, "La impresora no está conectada")


def test_enviar_resumen_en_pdf():
    pdfs = []
    e = _Entorno(get=lambda ruta, params=None: _RESUMEN)
    e.a._generar_pdf_resumen = lambda ruta, datos, textos: (pdfs.append(datos), open(ruta, "wb").write(b"%PDF-r"))
    e.a.enviarResumen("mes", "2026-09-15", "mant@x.com")
    exito, mensaje = e.resultado()
    e.backend.get.assert_called_once_with("/report/summary", params={"periodo": "mes", "fecha": "2026-09-15"})
    assert exito and "mant@x.com" in mensaje
    datos = pdfs[0]
    assert datos["titulo"] == "Resumen de ciclos" and "01/09/2026" in datos["periodo"]
    assert datos["resumen"]["total"] == "3"
    m = e.enviados[0]
    adjunto = next(m.iter_attachments())
    assert adjunto.get_filename() == "resumen_2026-09-01_2026-09-30.pdf"
    assert "SPK-1" in m["Subject"]


def test_enviar_resumen_sin_backend():
    def get(ruta, **k):
        raise requests.ConnectionError()
    e = _Entorno(get=get)
    e.a.enviarResumen("mes", "2026-09-15", "mant@x.com")
    exito, mensaje = e.resultado()
    assert not exito and "conexión con el equipo" in mensaje and e.enviados == []


def test_enviar_resumen_destino_invalido():
    e = _Entorno(get=lambda ruta, params=None: _RESUMEN)
    e.a.enviarResumen("mes", "2026-09-15", "x")
    assert e.resultado()[0] is False and e.enviados == []



def test_pdf_de_un_ciclo_con_consignas_de_esterilizacion():
    def get(ruta, **k):
        i = int(ruta.split("/")[3])
        if ruta.endswith("/ticket"):
            return _ticket(i)
        return {"ciclo_db_id": i, "lecturas": [
            {"id": 1, "t_s": 0.0, "fase": "PRE_VACIO", "fase_ui": "vacio",
             "temp_camara": 40.0, "temp_ref": 35.0, "pres_camara": 101.3},
            {"id": 2, "t_s": 600.0, "fase": "ESTERILIZACION", "fase_ui": "esterilizacion",
             "temp_camara": 134.5, "temp_ref": 134.0, "pres_camara": 304.0},
            {"id": 3, "t_s": 900.0, "fase": "SECADO", "fase_ui": "secado",
             "temp_camara": 110.0, "temp_ref": 108.0, "pres_camara": 150.0}]}
    e = _Entorno(get=get)
    e.a.enviarCorreo([12], "mant@x.com")
    assert e.resultado()[0] is True
    c = e.pdfs[0]["consigna"]
    assert (c["temp"], c["desde_min"], c["hasta_min"]) == (134.0, 10.0, 15.0)


# ── reporte consolidado del periodo ──────────────────────────────────────

def _lista(ids):
    return {"periodo": "mes", "truncado": False, "ciclos": [
        {"id": i, "numero_ciclo": i, "fecha_inicio": f"2026-09-{i:02d}T08:00:00",
         "fecha_fin": f"2026-09-{i:02d}T08:40:00", "programa_id": "instrumental_134",
         "programa_nombre": "Instrumental 134", "programa_numero": 2,
         "resultado": "COMPLETADO", "operador": None} for i in ids]}


class _Consolidado:
    def __init__(self, total=3, ids=(13, 12, 11), get_falla=None):
        self.pedidos = []
        self.generados = []

        def get(ruta, params=None, **k):
            self.pedidos.append((ruta, params))
            if get_falla and get_falla(ruta):
                raise requests.ConnectionError()
            if ruta == "/report/summary":
                return dict(_RESUMEN, totales=dict(_RESUMEN["totales"], total=total))
            if ruta == "/cycle/list":
                return _lista(list(ids))
            return _get(ruta)

        self.e = _Entorno(get=get)

        def generar(ruta, portada, ciclos, textos, progreso=None):
            self.generados.append({"portada": portada, "ciclos": ciclos})
            progreso(0.5)
            progreso(1.0)
            with open(ruta, "wb") as f:
                f.write(b"%PDF-consolidado")
            return list(range(2, 2 + len(ciclos)))

        self.e.a._generar_pdf_consolidado = generar
        self.avances = QSignalSpy(self.e.a.progresoChanged)


def test_consolidado_en_un_pdf_con_los_ciclos_en_orden_de_inicio():
    c = _Consolidado()
    c.e.a.enviarConsolidado("mes", "2026-09-15", "mant@x.com")
    exito, mensaje = c.e.resultado()
    assert exito and "3 ciclos" in mensaje and "mant@x.com" in mensaje
    assert ("/cycle/list", {"periodo": "mes", "terminados": "false", "fecha": "2026-09-15",
                            "limite": 200}) in c.pedidos
    g = c.generados[0]
    assert [x["indice"][0] for x in g["ciclos"]] == ["000011", "000012", "000013"]   # más antiguo primero
    assert g["ciclos"][0]["indice"] == ["000011", "11/09/2026", "08:00", "02 · Instrumental 134",
                                        "Fallo (FALLO_SECADO)"]
    assert g["portada"]["resumen"]["total"] == "3"
    adjunto = next(c.e.enviados[0].iter_attachments())
    assert adjunto.get_filename() == "consolidado_2026-09-01_2026-09-30.pdf"
    assert adjunto.get_content() == b"%PDF-consolidado"
    # avance visible mientras trabaja y limpio al terminar
    assert c.avances.count() >= 3 and c.e.a.progreso == ""


def test_consolidado_sin_ciclos():
    c = _Consolidado(total=0, ids=())
    c.e.a.enviarConsolidado("dia", "2026-10-06", "mant@x.com")
    assert c.e.resultado() == (False, "No hay ciclos en este periodo")
    assert c.generados == [] and c.e.enviados == []


def test_consolidado_con_demasiados_ciclos():
    c = _Consolidado(total=250)
    c.e.a.enviarConsolidado("mes", "2026-09-15", "mant@x.com")
    exito, mensaje = c.e.resultado()
    assert not exito and "250" in mensaje and "200" in mensaje
    assert c.generados == []


def test_consolidado_sin_backend():
    c = _Consolidado(get_falla=lambda ruta: ruta.endswith("/graph"))
    c.e.a.enviarConsolidado("mes", "2026-09-15", "mant@x.com")
    exito, mensaje = c.e.resultado()
    assert not exito and "conexión con el equipo" in mensaje and c.e.enviados == []
    assert c.e.a.progreso == ""


def test_consolidado_destino_invalido_no_consulta():
    c = _Consolidado()
    c.e.a.enviarConsolidado("mes", "2026-09-15", "x")
    assert c.e.resultado()[0] is False and c.pedidos == []
