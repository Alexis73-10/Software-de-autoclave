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

        def generar_pdf(ruta, datos, ticket, grafica, fases, textos):
            self.pdfs.append({"datos": datos, "ticket": ticket, "grafica": grafica, "fases": fases})
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
