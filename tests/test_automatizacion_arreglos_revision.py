"""Arreglos de la revisión de automatización: PDF, pantallas, puente."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFontMetricsF

from autoclave.ui_qml.bridge.acciones_ciclos import texto_empresa
from autoclave.ui_qml.bridge import puente_instalacion as pi
from autoclave.ui_qml.exportacion import pdf_ciclo

MODELO = "M" * 80
SERIE = "S" * 40


def test_empresa_automatizacion_no_atribuye_fabricacion():
    for idioma, pref in (("es", "Automatizado por"), ("en", "Automated by")):
        t = texto_empresa(MODELO, SERIE, idioma, serial_especifika="SNA00001")
        assert t.startswith(pref)
        assert f"Autoclave {MODELO}" not in t
        assert "SNA00001" in t


def test_empresa_fabricacion_igual():
    assert texto_empresa("ZZ", "AB1", "es") == "Especifika S.A.S. · Autoclave ZZ · Serie AB1"


def test_encabezado_pdf_envuelve_y_conserva_serial(tmp_path):
    texto = texto_empresa(MODELO, SERIE, "es", serial_especifika="SNA00001")
    with pdf_ciclo.Documento(tmp_path / "a.pdf") as doc:
        l = doc.l
        l.fuente(8)
        lineas = pdf_ciclo._envolver(l, texto, l.ancho)
        fm = QFontMetricsF(l.p.font(), l.p.device())
        assert all(fm.horizontalAdvance(x) <= l.ancho + 0.5 for x in lineas)
        assert "SNA00001" in "".join(lineas)
        corto = "Especifika S.A.S. · Autoclave ZZ · Serie AB1"
        assert pdf_ciclo._envolver(l, corto, l.ancho) == [corto]
        pdf_ciclo._encabezado(l, {"empresa": texto, "titulo": "t"})


def test_validar_codigo_misma_fecha_y_limpia_codigo():
    vistos = []

    class R:
        def __init__(s, ok): s.ok = ok; s.motivo = "x"

    def ver(*a, **k):
        vistos.append(k.get("hoy"))
        return R(len(vistos) == 1)
    p = pi.PuenteInstalacion(verificar_codigo=ver)
    assert p.validarCodigo("SN", "c", "fabricacion") == ""
    assert p._codigo == "c"
    p.validarCodigo("SN", "c", "fabricacion")
    assert p._codigo == ""
    assert vistos[0] == pi.ahora_local().date()


def test_normalizar_original():
    p = pi.PuenteInstalacion()
    assert p.normalizarOriginal("modelo", "  abc  def ") == p.normalizarOriginal("modelo", "ABC DEF")
    assert p.normalizarOriginal("serie", "") == ""
