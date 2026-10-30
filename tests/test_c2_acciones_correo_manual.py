# tests/test_c2_acciones_correo_manual.py
#
# C2 (tanda 7): AccionesCiclos con el smtplib real contra el SMTP falso local
# (tests/helpers/smtp_falso.py). Guardadas, manual, mixtas, dirección inválida,
# rechazo parcial del relay y relay caído. El mensaje sale de lo que el relay
# ACEPTÓ; la dirección escrita a mano no se agrega a los guardados; cada
# intento queda en la bitácora (POST /email/sent) sin la contraseña.

import json
import os
import sys
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from autoclave.ui_qml.bridge.acciones_ciclos import AccionesCiclos
from autoclave.ui_qml.exportacion import correo
from autoclave.ui_qml.exportacion.config_correo import ConfigCorreo
from tests.helpers.smtp_falso import SMTPSinTLS, SmtpFalso

_GUARDADOS = [{"nombre": "Mantenimiento", "correo": "mant@x.com"},
              {"nombre": "Calidad", "correo": "cal@x.com"}]
_CLAVE = "clave-secreta-123"


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QApplication(sys.argv)


def _get(ruta, **k):
    i = int(ruta.split("/")[3])
    if ruta.endswith("/ticket"):
        return {"ciclo": {"id": i, "numero_ciclo": i, "serie": "S1", "modelo": "M",
                          "version_sw": "1", "nombre_ciclo": "Instrumental 134",
                          "tipo_ciclo": "instrumental_134", "temp_esterilizacion": 134,
                          "tiempo_esterilizacion": 4, "fecha_inicio": "2026-09-15T08:00:00",
                          "fecha_fin": "2026-09-15T08:40:00", "resultado": "COMPLETADO",
                          "motivo_fallo": None}, "lecturas": []}
    return {"ciclo_db_id": i, "lecturas": []}


class _Entorno:
    def __init__(self, puerto, smtp=SMTPSinTLS):
        self.backend = MagicMock()
        self.posts = []
        self.backend.post.side_effect = lambda ruta, body, **k: (self.posts.append((ruta, body)),
                                                                 {"ok": True})[1]
        self.backend.get.side_effect = _get
        self.config = ConfigCorreo("equipo@x.com", "127.0.0.1", puerto,
                                   [dict(d) for d in _GUARDADOS], _CLAVE)
        self.guardados_antes = json.dumps(self.config.destinos)

        def generar_pdf(ruta, *a):
            with open(ruta, "wb") as f:
                f.write(b"%PDF-x")

        self.a = AccionesCiclos(self.backend, cargar_config=lambda: self.config,
                                ejecutar=lambda t: t(), generar_pdf=generar_pdf,
                                enviar=lambda c, m: correo.enviar(c, m, smtp=smtp))
        self.terminadas = QSignalSpy(self.a.accionTerminada)

    def resultado(self):
        QCoreApplication.processEvents()
        assert self.terminadas.count() == 1
        return tuple(self.terminadas.at(0))

    def bitacora(self):
        filas = [b for r, b in self.posts if r == "/email/sent"]
        assert len(filas) == 1, self.posts
        assert _CLAVE not in json.dumps(filas[0])
        return filas[0]


def test_guardada():
    with SmtpFalso() as s:
        e = _Entorno(s.puerto)
        e.a.enviarCorreo([12], "mant@x.com")
        exito, mensaje = e.resultado()
    assert exito and "mant@x.com" in mensaje
    assert s.entregados[0]["para"] == ["mant@x.com"]
    b = e.bitacora()
    assert b["tipo"] == "ciclos" and b["resultado"] == "enviado"
    assert b["destinatarios"] == ["mant@x.com"] and b["manuales"] == []
    assert b["aceptados"] == ["mant@x.com"] and b["rechazados"] == {}
    assert b["ciclos"] == [12]


def test_todas_las_guardadas():
    with SmtpFalso() as s:
        e = _Entorno(s.puerto)
        e.a.enviarCorreo([12], "mant@x.com,cal@x.com")
        exito, mensaje = e.resultado()
    assert exito and "mant@x.com" in mensaje and "cal@x.com" in mensaje
    assert s.entregados[0]["para"] == ["mant@x.com", "cal@x.com"]


def test_manual_sola_llega_y_no_se_guarda():
    with SmtpFalso() as s:
        e = _Entorno(s.puerto)
        e.a.enviarCorreo([12], " Juan@Gmail.com ")
        exito, mensaje = e.resultado()
    assert exito and "Juan@Gmail.com" in mensaje
    assert s.rcpt == ["Juan@Gmail.com"] and s.entregados[0]["para"] == ["Juan@Gmail.com"]
    assert json.dumps(e.config.destinos) == e.guardados_antes
    assert e.a.destinos == _GUARDADOS
    b = e.bitacora()
    assert b["manuales"] == ["Juan@Gmail.com"] and b["resultado"] == "enviado"


def test_mixta_manual_y_guardadas():
    with SmtpFalso() as s:
        e = _Entorno(s.puerto)
        e.a.enviarCorreo([12, 13], "juan@gmail.com,mant@x.com,cal@x.com")
        exito, mensaje = e.resultado()
    assert exito
    assert s.entregados[0]["para"] == ["juan@gmail.com", "mant@x.com", "cal@x.com"]
    assert json.dumps(e.config.destinos) == e.guardados_antes
    b = e.bitacora()
    assert b["manuales"] == ["juan@gmail.com"] and b["ciclos"] == [12, 13]


def test_direccion_invalida_no_envia_y_dice_cual():
    with SmtpFalso() as s:
        e = _Entorno(s.puerto)
        e.a.enviarCorreo([12], "mant@x.com,juan@gmail")
        exito, mensaje = e.resultado()
    assert not exito and "juan@gmail" in mensaje
    assert s.rcpt == [] and s.entregados == []
    assert [r for r, _ in e.posts] == []          # sin intento: nada en la bitácora


def test_rechazo_parcial_lo_dice_con_la_direccion():
    with SmtpFalso(rechazar={"malo@x.com"}) as s:
        e = _Entorno(s.puerto)
        e.a.enviarCorreo([12], "mant@x.com,malo@x.com")
        exito, mensaje = e.resultado()
    assert exito is False                          # aviso, no "todo bien"
    assert "malo@x.com" in mensaje and "mant@x.com" in mensaje
    assert s.entregados[0]["para"] == ["mant@x.com"]
    b = e.bitacora()
    assert b["resultado"] == "parcial"
    assert b["aceptados"] == ["mant@x.com"] and b["rechazados"] == {"malo@x.com": 550}


def test_rechazo_total_nunca_dice_enviado():
    with SmtpFalso(rechazar={"malo@x.com"}) as s:
        e = _Entorno(s.puerto)
        e.a.enviarCorreo([12], "malo@x.com")
        exito, mensaje = e.resultado()
    assert not exito and "malo@x.com" in mensaje
    assert "Se envi" not in mensaje
    assert e.bitacora()["resultado"] == "rechazado"


def test_relay_caido():
    with SmtpFalso() as s:
        puerto = s.puerto
    e = _Entorno(puerto)
    e.a.enviarCorreo([12], "juan@gmail.com")
    exito, mensaje = e.resultado()
    assert not exito and "internet" in mensaje
    b = e.bitacora()
    assert b["resultado"] == "error_conexion" and b["aceptados"] == []
    assert b["destinatarios"] == ["juan@gmail.com"]


def test_resumen_y_consolidado_tambien_por_destinatario():
    with SmtpFalso(rechazar={"malo@x.com"}) as s:
        e = _Entorno(s.puerto)
        e.backend.get.side_effect = lambda ruta, **k: {
            "desde": "2026-09-01", "hasta": "2026-09-30", "serie": "S", "modelo": "M",
            "totales": {"total": 1, "completados": 1, "fallos": 0, "cancelados": 0,
                        "sin_cierre": 0}, "por_programa": [], "causas_fallo": []}
        e.a._generar_pdf_resumen = lambda ruta, *a: open(ruta, "wb").write(b"%PDF")
        e.a.enviarResumen("mes", "2026-09-15", "juan@gmail.com,malo@x.com")
        exito, mensaje = e.resultado()
    assert not exito and "malo@x.com" in mensaje and "juan@gmail.com" in mensaje
    b = e.bitacora()
    assert b["tipo"] == "resumen" and b["resultado"] == "parcial"


def test_la_bitacora_caida_no_cambia_el_resultado():
    with SmtpFalso() as s:
        e = _Entorno(s.puerto)
        e.backend.post.side_effect = ConnectionError("sin backend")
        e.a.enviarCorreo([12], "juan@gmail.com")
        exito, mensaje = e.resultado()
    assert exito and "juan@gmail.com" in mensaje

