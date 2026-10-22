# tests/test_c2_correo_destinatarios.py
#
# C2 (tanda 7): envío con el smtplib REAL contra un SMTP falso local
# (tests/smtp_falso.py, sin red). El resultado sale de lo que el relay aceptó
# por destinatario: smtplib no lanza excepción si al menos uno se acepta
# (devuelve el dict de rechazados), y eso no puede leerse como "enviado".

import smtplib

import pytest

from autoclave.ui_qml.exportacion import correo
from autoclave.ui_qml.exportacion.config_correo import ConfigCorreo
from tests.smtp_falso import SMTPSinTLS, SmtpFalso

_ADJ = ("ciclo_000012.pdf", b"%PDF-1", "pdf")


def _config(puerto):
    return ConfigCorreo("equipo@x.com", "127.0.0.1", puerto, [], "clave-secreta")


def test_separar_destinos_quita_espacios_vacios_y_repetidos():
    assert correo.separar_destinos(" a@x.com, b@y.com;A@X.com ,, ") == ["a@x.com", "b@y.com"]
    assert correo.separar_destinos(["a@x.com", " b@y.com "]) == ["a@x.com", "b@y.com"]
    assert correo.separar_destinos("") == [] and correo.separar_destinos(None) == []


def test_mensaje_con_varios_destinatarios():
    m = correo.armar_mensaje("equipo@x.com", ["a@x.com", "b@y.com"], "A", "C", _ADJ)
    assert m["To"] == "a@x.com, b@y.com"


def test_un_destinatario_aceptado():
    with SmtpFalso() as s:
        r = correo.enviar(_config(s.puerto), correo.armar_mensaje(
            "equipo@x.com", ["juan@gmail.com"], "A", "C", _ADJ), smtp=SMTPSinTLS)
    assert r.aceptados == ("juan@gmail.com",) and r.rechazados == {}
    assert r.todos_aceptados and not r.ninguno_aceptado
    assert s.entregados[0]["para"] == ["juan@gmail.com"]
    assert s.entregados[0]["de"] == "equipo@x.com"


def test_mixto_llegan_todos_al_envelope():
    destinos = ["juan@gmail.com", "mant@x.com", "cal@x.com"]
    with SmtpFalso() as s:
        r = correo.enviar(_config(s.puerto), correo.armar_mensaje(
            "equipo@x.com", destinos, "A", "C", _ADJ), smtp=SMTPSinTLS)
    assert list(r.aceptados) == destinos
    assert s.rcpt == destinos and s.entregados[0]["para"] == destinos


def test_rechazo_parcial_no_se_pierde():
    with SmtpFalso(rechazar={"malo@x.com"}) as s:
        r = correo.enviar(_config(s.puerto), correo.armar_mensaje(
            "equipo@x.com", ["mant@x.com", "malo@x.com"], "A", "C", _ADJ), smtp=SMTPSinTLS)
    assert r.aceptados == ("mant@x.com",)
    assert r.rechazados == {"malo@x.com": 550}
    assert not r.todos_aceptados and not r.ninguno_aceptado
    assert s.entregados[0]["para"] == ["mant@x.com"]


def test_rechazo_total_devuelve_resultado_sin_aceptados():
    with SmtpFalso(rechazar={"malo@x.com"}) as s:
        r = correo.enviar(_config(s.puerto), correo.armar_mensaje(
            "equipo@x.com", ["malo@x.com"], "A", "C", _ADJ), smtp=SMTPSinTLS)
    assert r.aceptados == () and r.rechazados == {"malo@x.com": 550}
    assert r.ninguno_aceptado
    assert s.entregados == []


def test_relay_caido_lanza_oserror():
    with SmtpFalso() as s:
        puerto = s.puerto
    # el servidor ya se cerró: conexión rechazada
    with pytest.raises(OSError):
        correo.enviar(_config(puerto), correo.armar_mensaje(
            "equipo@x.com", ["a@x.com"], "A", "C", _ADJ), smtp=SMTPSinTLS)


def test_envelope_usa_los_destinatarios_explicitos():
    """Si se pasan destinatarios, son los del envelope (no se re-leen de To)."""
    with SmtpFalso() as s:
        m = correo.armar_mensaje("equipo@x.com", ["a@x.com"], "A", "C", _ADJ)
        r = correo.enviar(_config(s.puerto), m, smtp=SMTPSinTLS, destinatarios=["b@x.com"])
    assert r.aceptados == ("b@x.com",) and s.rcpt == ["b@x.com"]


def test_resultado_no_lleva_la_contrasena():
    with SmtpFalso(rechazar={"malo@x.com"}) as s:
        r = correo.enviar(_config(s.puerto), correo.armar_mensaje(
            "equipo@x.com", ["mant@x.com", "malo@x.com"], "A", "C", _ADJ), smtp=SMTPSinTLS)
    assert "clave-secreta" not in repr(r)
