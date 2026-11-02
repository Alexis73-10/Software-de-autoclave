# tests/test_rep13_acciones_sin_sesion.py
#
# REP-13 / DR-H08 (tanda dashboard-reportes): defensa en profundidad del
# control de la pantalla. Sin sesión, AccionesCiclos ignora las direcciones
# escritas a mano (las que no están entre las guardadas) y solo envía a las
# guardadas; si no queda ninguna, no envía. Con sesión, igual que antes.
# SMTP falso local (tests/helpers/smtp_falso.py) con el smtplib real.

import os
import sys
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from autoclave.cliente.session_manager import SessionManager
from autoclave.ui_qml.bridge.acciones_ciclos import AccionesCiclos
from autoclave.ui_qml.exportacion import correo
from autoclave.ui_qml.exportacion.config_correo import ConfigCorreo
from tests.helpers.smtp_falso import SMTPSinTLS, SmtpFalso

_GUARDADOS = [{"nombre": "Mantenimiento", "correo": "mant@x.com"},
              {"nombre": "Calidad", "correo": "cal@x.com"}]


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


def _generar_pdf(ruta, *a):
    with open(ruta, "wb") as f:
        f.write(b"%PDF-x")


def _acciones(puerto, posts, **kw):
    backend = MagicMock()
    backend.get.side_effect = _get
    backend.post.side_effect = lambda ruta, body, **k: (posts.append((ruta, body)), {"ok": True})[1]
    config = ConfigCorreo("equipo@x.com", "127.0.0.1", puerto, [dict(d) for d in _GUARDADOS], "c")
    a = AccionesCiclos(backend, cargar_config=lambda: config, ejecutar=lambda t: t(),
                       generar_pdf=_generar_pdf,
                       enviar=lambda c, m: correo.enviar(c, m, smtp=SMTPSinTLS), **kw)
    return a, QSignalSpy(a.accionTerminada)


def _resultado(espia):
    QCoreApplication.processEvents()
    assert espia.count() == 1
    return tuple(espia.at(0))


def test_sin_sesion_la_manual_sola_no_se_envia():
    posts = []
    with SmtpFalso() as s:
        a, espia = _acciones(s.puerto, posts, sesion_activa=lambda: False)
        a.enviarCorreo([12], "juan@gmail.com")
        exito, mensaje = _resultado(espia)
    assert not exito and "Inicie sesión" in mensaje
    assert s.rcpt == [] and s.entregados == []
    assert posts == []                       # sin intento, nada en la bitácora


def test_sin_sesion_mixta_solo_llega_a_las_guardadas():
    posts = []
    with SmtpFalso() as s:
        a, espia = _acciones(s.puerto, posts, sesion_activa=lambda: False)
        a.enviarCorreo([12], "juan@gmail.com,mant@x.com,cal@x.com")
        exito, mensaje = _resultado(espia)
    assert exito and "juan@gmail.com" not in mensaje
    assert s.rcpt == ["mant@x.com", "cal@x.com"]
    filas = [b for r, b in posts if r == "/email/sent"]
    assert len(filas) == 1 and filas[0]["manuales"] == []
    assert filas[0]["destinatarios"] == ["mant@x.com", "cal@x.com"]


def test_sin_sesion_las_guardadas_se_envian_como_antes():
    posts = []
    with SmtpFalso() as s:
        a, espia = _acciones(s.puerto, posts, sesion_activa=lambda: False)
        a.enviarCorreo([12], "MANT@x.com")    # sin distinguir mayúsculas
        exito, _ = _resultado(espia)
    assert exito and s.rcpt == ["MANT@x.com"]


def test_con_sesion_la_manual_se_envia():
    posts = []
    with SmtpFalso() as s:
        a, espia = _acciones(s.puerto, posts, sesion_activa=lambda: True)
        a.enviarCorreo([12], "juan@gmail.com")
        exito, _ = _resultado(espia)
    assert exito and s.rcpt == ["juan@gmail.com"]


def test_error_al_consultar_la_sesion_falla_cerrado():
    def rota():
        raise RuntimeError("x")
    posts = []
    with SmtpFalso() as s:
        a, espia = _acciones(s.puerto, posts, sesion_activa=rota)
        a.enviarCorreo([12], "juan@gmail.com")
        exito, _ = _resultado(espia)
    assert not exito and s.rcpt == []


def test_por_defecto_usa_la_sesion_de_la_ventana():
    SessionManager.logout()
    posts = []
    with SmtpFalso() as s:
        a, espia = _acciones(s.puerto, posts)
        a.enviarResumen("mes", "2026-09-15", "juan@gmail.com")
        exito, _ = _resultado(espia)
    assert not exito and s.rcpt == []


# Trazabilidad (matriz REQ-37..REQ-50, dashboard de Reportes)
import pytest as _pytest  # noqa: E402

pytestmark = [_pytest.mark.req("REQ-49")]
