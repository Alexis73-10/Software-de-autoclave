"""RCB-06/07: la carga en la tirilla (tres modos, 24 columnas sin recorte,
tope de 15 con «y N más», «CARGA NO ESTÉRIL», reimpresión con el modo
guardado), en el PDF y el correo (lista completa y aviso de no estéril) y en
GET /cycle/history/{id}/ticket (HAZ-RCB-02)."""

import json
import os
import subprocess
import sys
import textwrap
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from autoclave.services.domain.logging import ticket_formatter as tf
from autoclave.services.domain.logging.ticket_formatter import Presentacion, format_ticket
from autoclave.ui_qml.domain import registro_carga as dom

pytestmark = pytest.mark.req("REQ-112")

P = Presentacion()


def _carga(n=3, impresion="lote_elementos"):
    elementos = [{"codigo": f"CX-{i:04d}", "nombre": f"Set de cirugía general número {i}",
                  "en_catalogo": True, "cantidad": i + 1, "manual": False} for i in range(n)]
    if n:
        elementos[-1] = {"codigo": "7701234567890", "nombre": None, "en_catalogo": False,
                         "cantidad": 1, "manual": True}
    return {"lote": "LT-241124-03", "impresion": impresion, "elementos": elementos}


def _texto(lineas):
    return " ".join(l.strip() for l in lineas)


# ── tirilla ─────────────────────────────────────────────────────────────────

def test_modo_ninguna_no_imprime_nada():
    assert tf.lineas_carga(_carga(impresion="ninguna"), P) == []
    assert tf.lineas_carga(None, P) == []
    assert tf.lineas_carga({"lote": "", "elementos": []}, P) == []


def test_modo_lote_solo_el_lote():
    lineas = tf.lineas_carga(_carga(impresion="lote"), P)
    assert "CARGA" in lineas and "Lote: LT-241124-03" in lineas
    assert not any("x " in l for l in lineas)


def test_modo_lote_elementos_partido_sin_recorte():
    lineas = tf.lineas_carga(_carga(), P)
    assert all(len(l) <= tf.ANCHO_TICKET for l in lineas)
    texto = _texto(lineas)
    assert "1x Set de cirugía general número 0" in texto
    assert "2x Set de cirugía general número 1" in texto
    assert "1x 7701234567890 (sin catálogo)" in texto
    assert "CX-0000" not in texto              # el código con catálogo no va en la tirilla
    # la continuación va sangrada bajo el nombre
    i = next(k for k, l in enumerate(lineas) if l.startswith("1x Set"))
    assert lineas[i + 1].startswith("   ")


def test_palabra_mas_larga_que_el_ancho_se_parte_sin_perder_nada():
    carga = {"lote": "Q" * 40, "impresion": "lote_elementos",
             "elementos": [{"codigo": "A", "nombre": "X" * 50, "cantidad": 999}]}
    lineas = tf.lineas_carga(carga, P)
    assert all(len(l) <= tf.ANCHO_TICKET for l in lineas)
    assert "".join(l.strip() for l in lineas).count("X") == 50
    assert "".join(l.strip() for l in lineas).count("Q") == 40


def test_tope_de_15_con_y_n_mas():
    lineas = tf.lineas_carga(_carga(20), P)
    texto = _texto(lineas)
    assert texto.count("x ") >= tf.MAX_ELEMENTOS_CARGA_TICKET
    assert "número 14" in texto and "número 15" not in texto
    assert "... y 5 más (ver reporte)" in texto


def test_encabezado_lleva_el_bloque_antes_de_las_columnas():
    cab = tf.format_header({"numero_ciclo": 1, "fecha_inicio": "2026-11-19T10:00:00",
                            "carga": _carga()}, P)
    lineas = cab.split("\n")
    assert lineas.index("CARGA") < len(lineas) - 1
    assert lineas[-1].strip().startswith("Hora")


def _ciclo(resultado, carga):
    return {"numero_ciclo": 7, "serie": "S", "modelo": "M", "version_sw": "1",
            "nombre_ciclo": "Instrumental", "tipo_ciclo": "inst", "temp_esterilizacion": 134,
            "tiempo_esterilizacion": 4, "fecha_inicio": "2026-11-19T10:00:00",
            "fecha_fin": "2026-11-19T10:40:00", "resultado": resultado, "carga": carga}


@pytest.mark.parametrize("resultado", ["FALLO_ESTERILIZACION", "CANCELADO", "INTERRUMPIDO"])
def test_no_completado_con_carga_dice_carga_no_esteril(resultado):
    texto = format_ticket(_ciclo(resultado, _carga()), [], P)
    assert "CARGA NO ESTÉRIL" in texto
    assert "Lote: LT-241124-03" in texto


def test_completado_no_dice_no_esteril():
    texto = format_ticket(_ciclo("COMPLETADO", _carga()), [], P)
    assert "NO ESTÉRIL" not in texto


def test_reimpresion_con_el_modo_guardado_del_ciclo():
    """El modo del programa pudo cambiar después: rige el guardado."""
    texto = format_ticket(_ciclo("COMPLETADO", _carga(impresion="lote")), [], P)
    assert "Lote: LT-241124-03" in texto and "Set de cirugía" not in texto
    texto = format_ticket(_ciclo("COMPLETADO", _carga(impresion="ninguna")), [], P)
    assert "LT-241124-03" not in texto
    sin = format_ticket(_ciclo("COMPLETADO", None), [], P)
    assert "CARGA" not in sin


# ── PDF, correo, detalle ────────────────────────────────────────────────────

def _t(clave, **params):
    from autoclave import i18n
    return i18n.t(clave, idioma="es", **params) if "idioma" in i18n.t.__code__.co_varnames \
        else i18n.t(clave, **params)


def test_seccion_pdf_lista_completa_y_marcas():
    seccion = dom.seccion_carga(_carga(20), "COMPLETADO", "Laura Gómez", _t)
    assert len(seccion["filas"]) == 20                        # sin tope
    assert seccion["no_esteril"] == ""
    assert "LT-241124-03" in seccion["resumen"] and "Laura Gómez" in seccion["resumen"]
    assert "20 " in seccion["resumen"]
    ultima = seccion["filas"][-1]
    assert ultima[1] == ultima[2] == "7701234567890"
    assert "manual" in ultima[3].lower() and "catálogo" in ultima[3].lower()
    assert seccion["filas"][0][2] == "CX-0000"               # el código sí va en el PDF


@pytest.mark.parametrize("resultado", ["FALLO_ESTERILIZACION", "CANCELADO", "INTERRUMPIDO", None])
def test_seccion_pdf_no_esteril(resultado):
    seccion = dom.seccion_carga(_carga(), resultado, None, _t)
    assert "NO ESTÉRIL" in seccion["no_esteril"]


def test_sin_carga_sin_seccion():
    assert dom.seccion_carga(None, "COMPLETADO") is None
    assert dom.seccion_carga({"lote": None}, "COMPLETADO") is None


def test_cuerpo_del_correo():
    ciclos = [{"numero_ciclo": 7, "resultado": "CANCELADO", "carga": _carga()},
              {"numero_ciclo": 8, "resultado": "COMPLETADO", "carga": _carga()},
              {"numero_ciclo": 9, "resultado": "COMPLETADO"}]
    lineas = dom.lineas_cuerpo_correo(ciclos, _t)
    assert len(lineas) == 2
    assert "000007" in lineas[0] and "NO ESTÉRIL" in lineas[0]
    assert "000008" in lineas[1] and "NO ESTÉRIL" not in lineas[1]


def test_correo_y_pdf_de_acciones_ciclos_llevan_la_carga():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication
    from autoclave.ui_qml.bridge.acciones_ciclos import AccionesCiclos
    from autoclave.ui_qml.exportacion import correo
    from autoclave.ui_qml.exportacion.config_correo import ConfigCorreo
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    ciclo = {**_ciclo("FALLO_ESTERILIZACION", _carga()), "id": 7, "operador": "Laura"}
    backend = MagicMock()
    backend.get.side_effect = lambda ruta, **k: (
        {"ciclo": ciclo, "lecturas": []} if ruta.endswith("/ticket")
        else {"ciclo_db_id": 7, "lecturas": []})
    backend.post.return_value = {"ok": True}
    pdfs, enviados = [], []

    def generar_pdf(ruta, datos, ticket, grafica, fases, textos, consigna=None):
        pdfs.append((datos, ticket))
        with open(ruta, "wb") as f:
            f.write(b"%PDF-")

    def enviar(config, m):
        enviados.append(m)
        return correo.ResultadoEnvio(tuple(correo.separar_destinos(m["To"])), {})

    a = AccionesCiclos(backend, cargar_config=lambda: ConfigCorreo(
        "e@x.com", "smtp.x.com", 587, [{"nombre": "M", "correo": "m@x.com"}], "c"),
        ejecutar=lambda t: t(), generar_pdf=generar_pdf, enviar=enviar,
        sesion_activa=lambda: True)
    a.enviarCorreo([7], "m@x.com")
    datos, ticket = pdfs[0]
    assert datos["carga"]["filas"] and "NO ESTÉRIL" in datos["carga"]["no_esteril"].upper()
    assert ("Lote", "LT-241124-03") in datos["campos"]
    assert "Lote: LT-241124-03" in ticket and "CARGA NO ESTÉRIL" in ticket
    cuerpo = enviados[0].get_body(("plain",)).get_content()
    assert "LT-241124-03" in cuerpo and "NO ESTÉRIL" in cuerpo


_SCRIPT_PDF = textwrap.dedent(r"""
    import json, sys
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtPdf import QPdfDocument
    from autoclave.ui_qml.app import _cargar_fuentes
    from autoclave.ui_qml.exportacion.pdf_ciclo import generar_pdf
    salida, seccion = sys.argv[1], json.loads(sys.argv[2])
    app = QGuiApplication([])
    _cargar_fuentes()
    textos = {"fases": {}, "series": {}, "eje_tiempo": "t", "eje_temp": "C", "eje_pres": "kPa",
              "sin_grafica": "-", "ticket": "Registro del ciclo"}
    datos = {"empresa": "E", "titulo": "Ciclo", "campos": [("Lote", "L1")], "carga": seccion}
    vacia = {"t_min": [], "temp_camara": [], "temp_ref": [], "pres_camara": []}
    generar_pdf(salida, datos, "linea\n" * 20, vacia, [], textos)
    doc = QPdfDocument()
    doc.load(salida)
    print(json.dumps({"paginas": doc.pageCount()}))
""")


def test_pdf_real_con_200_elementos_pasa_de_pagina(tmp_path):
    pytest.importorskip("PySide6")
    seccion = dom.seccion_carga(_carga(200), "CANCELADO", "Ana", _t)
    salida = tmp_path / "c.pdf"
    r = subprocess.run([sys.executable, "-c", _SCRIPT_PDF, str(salida), json.dumps(seccion)],
                       capture_output=True, text=True, timeout=90,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout.strip().splitlines()[-1])["paginas"] >= 3


# ── historial ──────────────────────────────────────────────────────────────

def test_ticket_del_historial_publica_la_carga_y_la_reimpresion_la_usa(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from autoclave.services.domain.logging.db_manager import DbManager
    from tests.helpers.backend_doble import cargar_servidor, modulo_backend
    db = DbManager(tmp_path / "h.db")
    con = db.crear_ciclo(numero=1, tipo="t", nombre="N", temp_ester=134, tiempo_ester=4,
                         modelo="M", serie="S", version_sw="1",
                         carga={"lote": "L9", "impresion": "lote",
                                "elementos": [{"codigo": "A1", "nombre": "Pinza",
                                               "en_catalogo": True, "cantidad": 2}]})
    db.cerrar_ciclo(con, "FALLO_X")
    sin = db.crear_ciclo(numero=2, tipo="t", nombre="N", temp_ester=134, tiempo_ester=4,
                         modelo="M", serie="S", version_sw="1")
    ctx = MagicMock()
    ctx.db = db
    srv, _ = cargar_servidor(ctx)
    client = TestClient(srv.app)
    c = client.get(f"/cycle/history/{con}/ticket").json()["ciclo"]
    assert c["carga"]["lote"] == "L9" and c["carga"]["impresion"] == "lote"
    assert c["carga"]["elementos"][0]["nombre"] == "Pinza"
    s = client.get(f"/cycle/history/{sin}/ticket").json()["ciclo"]
    assert "carga" not in s and "lote_carga" not in s and "impresion_carga" not in s
    impresos = []
    monkeypatch.setattr(modulo_backend("rutas.historial"), "_encolar_en_impresora",
                        lambda tickets: impresos.extend(tickets))
    assert client.post("/cycle/history/print", json={"ids": [con]}).status_code == 200
    assert "Lote: L9" in impresos[0] and "Pinza" not in impresos[0]   # modo guardado «lote»
    assert "CARGA NO ESTÉRIL" in impresos[0]
    db.close()
