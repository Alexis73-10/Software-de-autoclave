"""Tanda 26b: respuestas de Cristian a las preguntas abiertas de R26.

(A) ARQ-07: los 409 `arranque_retenido` y `arranque_no_iniciado` llegan a la
    UI como códigos conocidos, con texto propio en es y en (no el genérico).
(B) ARQ-06: el latido de apagado arranca al quedar el contexto operable o al
    recibir POST /arranque/iniciar, lo que ocurra primero; el ticket sigue
    esperando el contexto operable (hasta el plazo) y a la interfaz.
(C) Detalle de NO ABRIR por temperatura alta: «el menor entre el del equipo
    y el del programa» solo con límite del programa; sin él, rige el del equipo.
"""

import threading
import time
from types import SimpleNamespace

import pytest

from autoclave import i18n
from autoclave.backend import main as backend_main
from autoclave.backend.arranque.registro import RegistroArranque
from autoclave.devices.printer import arranque_equipo


# ── (A) ARQ-07 ────────────────────────────────────────────────────────────────

_CODIGOS_ARRANQUE = {
    "arranque_retenido": "sesion.arranque_retenido",
    "arranque_no_iniciado": "sesion.arranque_no_iniciado",
}


@pytest.mark.req("ARQ-07")
@pytest.mark.parametrize("codigo,clave", sorted(_CODIGOS_ARRANQUE.items()))
@pytest.mark.parametrize("ruta", ["/cycle/start", "/doors/puerta_1/open", "/io/test/enter",
                                  "/safe-state/confirm", "/fault/reset",
                                  "/io/test/output/vapor_camara", "/arranque/interfaz-lista", ""])
def test_codigo_de_arranque_es_conocido_en_toda_ruta(codigo, clave, ruta):
    sb = pytest.importorskip("autoclave.ui_qml.sesion_backend")
    assert codigo in sb.codigos_conocidos(ruta)
    r = sb.interpretar(409, {"codigo": codigo, "detail": "x"}, ruta)
    assert r.causa == codigo and r.estado_http == 409
    assert sb.clave_mensaje(codigo, ruta) == clave
    assert sb.clave_mensaje(codigo) == clave


@pytest.mark.req("ARQ-07")
@pytest.mark.parametrize("codigo,clave", sorted(_CODIGOS_ARRANQUE.items()))
@pytest.mark.parametrize("idioma", i18n.IDIOMAS)
def test_texto_propio_en_cada_idioma(codigo, clave, idioma):
    sb = pytest.importorskip("autoclave.ui_qml.sesion_backend")
    texto = i18n.t(clave, idioma)
    generico = i18n.t(sb.clave_mensaje(sb.ERROR_GENERICO), idioma)
    assert i18n.existe(clave, idioma)
    assert texto.strip() and texto != clave and texto != generico


def test_los_dos_textos_son_distintos():
    for idioma in i18n.IDIOMAS:
        assert i18n.t("sesion.arranque_retenido", idioma) != i18n.t("sesion.arranque_no_iniciado", idioma)


# ── (B) ARQ-06 ────────────────────────────────────────────────────────────────

def _servidor():
    return SimpleNamespace(_contexto_operable=threading.Event(),
                           context=SimpleNamespace(profile="P"),
                           registro_arranque=RegistroArranque())


def _instrumentar(monkeypatch):
    marcas = {"latido": [], "ticket": []}
    monkeypatch.setattr(arranque_equipo, "iniciar_latido",
                        lambda: marcas["latido"].append(time.monotonic()) or "ULTIMO")

    def ticket(perfil, leer_ultimo=None, arrancar_latido=None, **kw):
        marcas["ticket"].append((perfil, leer_ultimo(), time.monotonic()))
        arrancar_latido()        # no debe volver a arrancar el latido
    monkeypatch.setattr(arranque_equipo, "iniciar", ticket)
    return marcas


def _lanzar(srv, plazo_s):
    h = threading.Thread(target=backend_main.latido_y_ticket, args=(srv,),
                         kwargs={"plazo_s": plazo_s, "tope_interfaz_s": 0.1}, daemon=True)
    h.start()
    return h


def _esperar(cond, plazo=3.0):
    fin = time.monotonic() + plazo
    while time.monotonic() < fin:
        if cond():
            return True
        time.sleep(0.01)
    return cond()


@pytest.mark.req("ARQ-06")
def test_latido_arranca_al_recibir_iniciar_sin_esperar_el_plazo(monkeypatch):
    marcas = _instrumentar(monkeypatch)
    srv = _servidor()
    h = _lanzar(srv, plazo_s=30.0)
    time.sleep(0.2)
    assert marcas["latido"] == []                 # nada aún: ni iniciar ni operable
    t0 = time.monotonic()
    srv.registro_arranque.marcar_iniciado()
    assert _esperar(lambda: marcas["latido"])
    assert marcas["latido"][0] - t0 < 1.0         # no espera los 30 s
    assert marcas["ticket"] == []                 # el ticket sigue esperando el perfil
    srv._contexto_operable.set()
    assert _esperar(lambda: marcas["ticket"])
    h.join(2)
    assert marcas["ticket"][0][:2] == ("P", "ULTIMO")   # último apagado leído antes del latido
    assert len(marcas["latido"]) == 1                    # una sola vez


@pytest.mark.req("ARQ-06")
def test_latido_arranca_al_quedar_operable(monkeypatch):
    marcas = _instrumentar(monkeypatch)
    srv = _servidor()
    h = _lanzar(srv, plazo_s=30.0)
    time.sleep(0.2)
    t0 = time.monotonic()
    srv._contexto_operable.set()
    h.join(3)
    assert not h.is_alive()
    assert len(marcas["latido"]) == 1 and marcas["latido"][0] - t0 < 1.0
    assert marcas["ticket"][0][:2] == ("P", "ULTIMO")


@pytest.mark.req("ARQ-06")
def test_iniciar_sin_contexto_operable_latido_sin_ticket_al_vencer_el_plazo(monkeypatch):
    marcas = _instrumentar(monkeypatch)
    srv = _servidor()
    srv.registro_arranque.marcar_iniciado()
    inicio = time.monotonic()
    backend_main.latido_y_ticket(srv, plazo_s=0.4, tope_interfaz_s=0.1)
    assert marcas["latido"][0] - inicio < 0.3            # de inmediato
    perfil, ultimo, t_ticket = marcas["ticket"][0]
    assert perfil is None and ultimo == "ULTIMO"         # sin perfil no hay ticket
    assert t_ticket - inicio >= 0.35                     # el plazo del ticket no cambia


@pytest.mark.req("ARQ-06")
def test_sin_iniciar_ni_operable_latido_al_vencer_el_plazo(monkeypatch):
    marcas = _instrumentar(monkeypatch)
    srv = _servidor()
    inicio = time.monotonic()
    backend_main.latido_y_ticket(srv, plazo_s=0.3, tope_interfaz_s=0.1)
    assert marcas["latido"][0] - inicio >= 0.25
    assert marcas["ticket"][0][0] is None


def test_marcar_iniciado_fija_el_evento():
    r = RegistroArranque()
    assert not r.evento_iniciado.is_set()
    r.marcar_iniciado()
    assert r.evento_iniciado.is_set() and r.iniciado is True
    r.marcar_iniciado()                                  # idempotente
    assert r.evento_iniciado.is_set()


def test_iniciar_latido_lee_antes_de_arrancar():
    orden = []
    ultimo = arranque_equipo.iniciar_latido(leer_ultimo=lambda: orden.append("leer") or "U",
                                            arrancar_latido=lambda: orden.append("latido"))
    assert ultimo == "U" and orden == ["leer", "latido"]


def test_tope_del_ticket_no_cambia():
    assert backend_main.TOPE_INTERFAZ_S == 75.0


# ── (C) NO ABRIR temp_alta ────────────────────────────────────────────────────

def _ctx(limites):
    return {"noAbrir": {"codigo": "temp_alta", "valores": {"temp": 87.4},
                        "limites": limites, "motivo": "", "textos": {}}}


_FRASE = {"es": "el menor entre el del equipo y el del programa",
          "en": "the lower of the equipment limit and that of"}
_EQUIPO = {"es": "rige el límite del equipo", "en": "the equipment limit applies"}


@pytest.mark.parametrize("idioma", i18n.IDIOMAS)
def test_temp_alta_con_programa_menciona_el_menor(idioma):
    from autoclave.ui_qml.domain import detalle_aviso as d
    texto = d.armar("no_abrir", _ctx({"temp_max_apertura": 60.0, "temp_max_apertura_equipo": 80.0,
                                      "temp_max_apertura_ciclo": 60.0}))["descripciones"][idioma]
    assert _FRASE[idioma] in texto and _EQUIPO[idioma] not in texto
    assert "87.4" in texto and "60.0" in texto


@pytest.mark.parametrize("limites", [
    {"temp_max_apertura": 80.0, "temp_max_apertura_equipo": 80.0, "temp_max_apertura_ciclo": None},
    {"temp_max_apertura": 80.0},                       # campo ausente = sin programa
])
@pytest.mark.parametrize("idioma", i18n.IDIOMAS)
def test_temp_alta_sin_programa_rige_el_equipo(idioma, limites):
    from autoclave.ui_qml.domain import detalle_aviso as d
    texto = d.armar("no_abrir", _ctx(limites))["descripciones"][idioma]
    assert _EQUIPO[idioma] in texto and _FRASE[idioma] not in texto
    assert "87.4" in texto and "80.0" in texto
    assert not texto.startswith("aviso_detalle.")
