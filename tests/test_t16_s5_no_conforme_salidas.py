"""P4 (tanda 16, D-14.4): «NO CONFORME» en el ticket (en vivo y en la
reimpresión), en el registro del ciclo (CycleLogger), en el PDF, en el correo
y en los datos del historial y de la pantalla final de la UI. Un ciclo
conforme no cambia.

Los textos nuevos viven en docs/informes/tanda16/i18n/s5.json hasta que la
sesión principal los una a i18n/*.json: la fixture `textos_s5` los inyecta en
el catálogo en memoria (si ya están unidos, no cambia nada)."""

import copy
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave import i18n
from autoclave.services.domain.logging.ticket_formatter import (
    CLAVE_NO_CONFORME, Presentacion, avisos_no_conforme, ciclo_no_conforme, format_footer,
    format_ticket)

pytestmark = pytest.mark.req("T16-S5")

_S5 = Path(__file__).resolve().parents[1] / "docs" / "informes" / "tanda16" / "i18n" / "s5.json"
_ES = Presentacion(idioma="es")
_EN = Presentacion(idioma="en")
_AVISO_NC = {"clave": CLAVE_NO_CONFORME, "sensor": "Referencia 1"}


@pytest.fixture(autouse=True)
def textos_s5(monkeypatch):
    fragmento = json.loads(_S5.read_text(encoding="utf-8"))
    cats = copy.deepcopy(i18n._todos())
    for idioma, textos in fragmento.items():
        for clave, texto in textos.items():
            nodo = cats[idioma]
            *ruta, hoja = clave.split(".")
            for parte in ruta:
                nodo = nodo.setdefault(parte, {})
            nodo.setdefault(hoja, texto)
    monkeypatch.setattr(i18n, "_catalogos", cats)
    return fragmento


def _ciclo(**extra):
    base = {"id": 7, "numero_ciclo": 7, "serie": "S", "modelo": "M", "version_sw": "1",
            "nombre_ciclo": "N", "tipo_ciclo": "t", "temp_esterilizacion": 134,
            "tiempo_esterilizacion": 4, "fecha_inicio": "2026-10-22T09:00:00",
            "fecha_fin": "2026-10-22T10:00:00", "resultado": "COMPLETADO", "operador": "ana"}
    base.update(extra)
    return base


def _avisos_json(*avisos):
    return json.dumps({"sin_datos_s": None, "avisos": list(avisos)})


# ── detección ───────────────────────────────────────────────────────────────

def test_deteccion_por_avisos():
    assert avisos_no_conforme([_AVISO_NC]) is True
    assert avisos_no_conforme(["texto", {"clave": "ticket_ciclo.aviso_excursion"}]) is False
    assert avisos_no_conforme(None) is False
    assert ciclo_no_conforme(_ciclo(avisos_ticket=_avisos_json(_AVISO_NC))) is True
    for texto in (None, "", "{", "[1]", _avisos_json("NO CONFORME")):
        assert ciclo_no_conforme(_ciclo(avisos_ticket=texto)) is False
    assert ciclo_no_conforme({}) is False


# ── ticket ──────────────────────────────────────────────────────────────────

def test_pie_en_vivo_lleva_la_marca_en_la_primera_linea():
    pie = format_footer("COMPLETADO", "2026-10-22T10:00:00", avisos=[_AVISO_NC], p=_ES)
    lineas = pie.split("\n")
    assert lineas[0] == "*** NO CONFORME ***"
    assert "Estado: COMPLETADO" in lineas      # el resultado técnico no cambia
    pie_en = format_footer("COMPLETADO", "2026-10-22T10:00:00", avisos=[_AVISO_NC], p=_EN)
    assert pie_en.split("\n")[0] == "*** NONCONFORMING ***"


def test_reimpresion_con_la_marca_en_encabezado_y_pie():
    texto = format_ticket(_ciclo(avisos_ticket=_avisos_json(_AVISO_NC)), [], _ES)
    assert texto.count("*** NO CONFORME ***") == 2
    encabezado = texto.split("Temp. final")[0]
    assert "*** NO CONFORME ***" in encabezado
    assert all(len(l) <= 24 for l in texto.split("\n") if l.startswith("***"))   # ancho del ticket


def test_ticket_de_ciclo_conforme_no_cambia():
    for ciclo in (_ciclo(), _ciclo(avisos_ticket=_avisos_json("Aviso cualquiera"))):
        texto = format_ticket(ciclo, [], _ES)
        assert "CONFORME" not in texto
    pie = format_footer("COMPLETADO", "2026-10-22T10:00:00", avisos=None, p=_ES)
    assert pie.split("\n")[0].startswith("Temp. final")


# ── CycleLogger: defensa en profundidad ─────────────────────────────────────

def test_logger_anota_el_aviso_si_solo_esta_la_bandera(tmp_path):
    from tests.test_t8_modo_sin_bd import _correr_ciclo, _logger
    db = MagicMock()
    db.crear_ciclo.return_value = 5
    cl, estado, printer, respaldo = _logger(tmp_path, db, sin_bd=False)
    estado.no_conforme = True
    _correr_ciclo(cl, estado)
    avisos = db.cerrar_ciclo.call_args.kwargs["avisos_ticket"]["avisos"]
    assert [a["clave"] for a in avisos if isinstance(a, dict)] == [CLAVE_NO_CONFORME]
    cierre = respaldo.leer(respaldo.pendientes()[0])["cierre"]
    assert avisos_no_conforme(cierre["avisos_ticket"]["avisos"]) is True
    impreso = "\n".join(c.args[0] for c in printer.enqueue.call_args_list)
    assert "*** NO CONFORME ***" in impreso


def test_logger_no_duplica_el_aviso(tmp_path):
    from tests.test_t8_modo_sin_bd import _correr_ciclo, _logger
    db = MagicMock()
    db.crear_ciclo.return_value = 5
    cl, estado, _, _ = _logger(tmp_path, db, sin_bd=False)
    estado.no_conforme = True
    estado.avisos_ciclo = [dict(_AVISO_NC)]
    _correr_ciclo(cl, estado)
    assert db.cerrar_ciclo.call_args.kwargs["avisos_ticket"]["avisos"] == [_AVISO_NC]


def test_logger_ciclo_conforme_no_cambia(tmp_path):
    from tests.test_t8_modo_sin_bd import _correr_ciclo, _logger
    db = MagicMock()
    db.crear_ciclo.return_value = 5
    cl, estado, printer, _ = _logger(tmp_path, db, sin_bd=False)
    _correr_ciclo(cl, estado)
    assert "avisos_ticket" not in db.cerrar_ciclo.call_args.kwargs
    impreso = "\n".join(c.args[0] for c in printer.enqueue.call_args_list)
    assert "CONFORME" not in impreso


# ── PDF y correo ────────────────────────────────────────────────────────────

pytest.importorskip("PySide6")
from tests.test_acciones_ciclos_puente import _Entorno, _grafica, _ticket, qt_app  # noqa: E402,F401


def _get_con_no_conforme(nc_ids):
    def get(ruta, **k):
        i = int(ruta.split("/")[3])
        if not ruta.endswith("/ticket"):
            return _grafica(i)
        t = _ticket(i)
        t["ciclo"]["resultado"] = "COMPLETADO"
        if i in nc_ids:
            t["ciclo"]["avisos_ticket"] = _avisos_json(_AVISO_NC)
            t["ciclo"]["no_conforme"] = True
        return t
    return get


def test_pdf_y_correo_de_un_ciclo_no_conforme():
    e = _Entorno(get=_get_con_no_conforme({12}))
    e.a.enviarCorreo([12, 13], "mant@x.com")
    exito, _ = e.resultado()
    assert exito
    campos12 = dict(e.pdfs[0]["datos"]["campos"])
    campos13 = dict(e.pdfs[1]["datos"]["campos"])
    assert campos12["Resultado"].startswith("NO CONFORME — ")
    assert "Completado" in campos12["Resultado"]
    assert "NO CONFORME" not in campos13["Resultado"]
    assert "*** NO CONFORME ***" in e.pdfs[0]["ticket"]
    m = e.enviados[0]
    assert m["Subject"].startswith("[NO CONFORME] ")
    cuerpo = m.get_body(preferencelist=("plain",)).get_content()
    assert "000012" in cuerpo.split("ATENCIÓN")[1] and "000013" not in cuerpo.split("ATENCIÓN")[1]


def test_pdf_detecta_por_avisos_sin_campo_del_backend():
    def get(ruta, **k):
        g = _get_con_no_conforme({12})(ruta, **k)
        if ruta.endswith("/ticket"):
            g["ciclo"].pop("no_conforme", None)
        return g
    e = _Entorno(get=get)
    e.a.enviarCorreo([12], "mant@x.com")
    e.resultado()
    assert dict(e.pdfs[0]["datos"]["campos"])["Resultado"].startswith("NO CONFORME")


def test_correo_de_ciclos_conformes_no_cambia():
    e = _Entorno(get=_get_con_no_conforme(set()))
    e.a.enviarCorreo([12], "mant@x.com")
    e.resultado()
    m = e.enviados[0]
    assert "CONFORME" not in m["Subject"]
    assert "CONFORME" not in m.get_body(preferencelist=("plain",)).get_content()
    assert "CONFORME" not in dict(e.pdfs[0]["datos"]["campos"])["Resultado"]


def test_correo_en_ingles(textos_s5):
    i18n.fijar_idioma("en")
    try:
        e = _Entorno(get=_get_con_no_conforme({12}))
        e.a.enviarCorreo([12], "mant@x.com")
        e.resultado()
        assert e.enviados[0]["Subject"].startswith("[NONCONFORMING] ")
        assert dict(e.pdfs[0]["datos"]["campos"])["Result"].startswith("NONCONFORMING — ")
    finally:
        i18n.fijar_idioma("es")


# ── datos de la UI: historial y pantalla final ──────────────────────────────

def test_historial_presentable_lleva_no_conforme():
    from autoclave.ui_qml.domain import resumen_sistema as rs
    lista = rs.lista_presentable({"ciclos": [{"id": 1, "resultado": "COMPLETADO", "no_conforme": True},
                                             {"id": 2, "resultado": "COMPLETADO"},
                                             {"id": 3, "resultado": "COMPLETADO", "no_conforme": "si"}]})
    assert [c["no_conforme"] for c in lista["ciclos"]] == [True, False, False]
    assert all(c["resultado"] == "COMPLETADO" for c in lista["ciclos"])
    assert rs.ultimo_no_conforme({"ultimo_ciclo": {"no_conforme": True}}) is True
    assert rs.ultimo_no_conforme({"ultimo_ciclo": None}) is False
    assert rs.ultimo_no_conforme(None) is False


def test_progreso_normalizado_lleva_no_conforme():
    from autoclave.ui_qml.domain.ciclo_en_curso import normalizar_progreso
    base = {"activo": True, "resultado": "exitoso", "fases": []}
    r = normalizar_progreso({**base, "no_conforme": True, "motivo_no_conforme": CLAVE_NO_CONFORME,
                             "no_conforme_reconocido": False})
    assert (r["no_conforme"], r["motivo_no_conforme"], r["no_conforme_reconocido"]) == \
        (True, CLAVE_NO_CONFORME, False)
    # falla cerrada: reconocido sin NO CONFORME o valores no booleanos no cuentan
    r = normalizar_progreso({**base, "no_conforme": 1, "no_conforme_reconocido": True})
    assert (r["no_conforme"], r["no_conforme_reconocido"]) == (False, False)
    r = normalizar_progreso({**base})
    assert (r["no_conforme"], r["motivo_no_conforme"], r["no_conforme_reconocido"]) == (False, "", False)
    assert normalizar_progreso(None)["no_conforme"] is False


def test_bridge_reconocer_no_conforme_envia_con_token(monkeypatch):
    from autoclave.cliente.session_manager import SessionManager
    from autoclave.ui_qml.bridge.comandos_ciclo_en_curso import ComandosCicloEnCurso
    ui = MagicMock()
    puente = MagicMock(connected=True)
    c = ComandosCicloEnCurso(puente, ui, ejecutar=lambda t: t())
    monkeypatch.setattr(SessionManager, "token", classmethod(lambda cls: "tok123"))
    resultados = []
    c.terminado.connect(lambda accion, ok: resultados.append((accion, ok)))
    c.reconocerNoConforme()
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.processEvents()
    ui.backend.post.assert_called_once_with(
        path="/cycle/acknowledge-no-conforme", headers={"Authorization": "Bearer tok123"})
    assert resultados == [("reconocer_no_conforme", True)]
    assert c.error == ""
    # rechazo del backend: queda el error y no se da por reconocido
    ui.backend.post.side_effect = RuntimeError("409")
    c.reconocerNoConforme()
    QCoreApplication.processEvents()
    assert resultados[-1] == ("reconocer_no_conforme", False)
    assert c.error == "reconocer_no_conforme"
