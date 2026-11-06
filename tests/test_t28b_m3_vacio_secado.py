"""Tanda 28b (A13-M3, decisión de Cristian del 6-nov): el secado tras fallo
verifica el vacío.

El SECADO solo termina «hecho» si la presión de cámara bajó de
atm − rango_presion_atm y se sostuvo así `secado_tras_fallo_vacio_s`
segundos continuos (monotonic) mientras la bomba trabajaba. Si no:
«sin_vacio» (nunca «hecho»), con log, aviso CIC-20, bitácora y ticket. La
ruptura del vacío corre siempre (tope de 120 s). Falla cerrada: sin lectura
de presión no hay verificación.

Piezas reales: ProtocoloFallo y ProtocoloEstadoSeguro (arnés de A13).
"""

import pytest

from autoclave import i18n
from autoclave.core.runtime import bitacora
from autoclave.services.domain.logging.ticket_formatter import (
    CLAVE_SECADO_TRAS_FALLO, aviso_secado_tras_fallo,
)
from autoclave.state_machine.alarms.catalogo import CATALOGO, CIC_20, Nivel
from autoclave.state_machine.cycle_phases import protocolo_fallo as pf
from tests.test_t28b_a13_secado_tras_fallo import ATM, RANGO, VACIO, _Equipo


class _AlarmasRegistro:
    def __init__(self):
        self.codigos = []
        self.activadas = []

    def activas(self):
        return [type("I", (), {"codigo": c})() for c in self.codigos]

    def activar(self, codigo, origen=None, **valores):
        self.activadas.append((codigo, valores))

    def resolver(self, *a, **k):
        pass


def _equipo(monkeypatch, segundos=20, vacio_s=5):
    e = _Equipo(monkeypatch, segundos=segundos)
    e.config["secado_tras_fallo_vacio_s"] = vacio_s
    e.alarmas = _AlarmasRegistro()
    e.protocolo.alarm_manager = e.alarmas
    return e


def _hasta_ruptura(e, presion, limite=400):
    """Ticks del SECADO con la presión dada hasta llegar a la ruptura."""
    for _ in range(limite):
        if e.protocolo._secado_fase == "ruptura":
            return
        if e.protocolo._secado_fase == "secado":
            e.pres(presion() if callable(presion) else presion)
        e.tick()
    raise AssertionError("no llegó a la ruptura")


def _terminar_ruptura(e, limite=50):
    e.pres(ATM)
    for _ in range(limite):
        e.tick()
        if not e.protocolo.secando:
            return
    raise AssertionError("la ruptura no terminó")


# ── vacío logrado ───────────────────────────────────────────────────────────

def test_vacio_logrado_y_sostenido_da_hecho(monkeypatch):
    e = _equipo(monkeypatch)
    e.disparar()
    e.tick()                                          # empieza el secado
    _hasta_ruptura(e, 20.0)
    assert e.protocolo._vacio_logrado
    e.tick()
    assert e.salidas.on("aire_atmosferico_camara")    # ruptura con aire
    _terminar_ruptura(e)
    assert e.resultado()["estado"] == "hecho"
    assert e.alarmas.activadas == []


# ── vacío no logrado ────────────────────────────────────────────────────────

def test_bomba_que_no_hace_vacio_da_sin_vacio_con_aviso(monkeypatch):
    """Bomba desconectada: la presión se queda en la atmosférica todo el
    secado. Resultado sin_vacio (nunca hecho), aviso CIC-20, bitácora."""
    e = _equipo(monkeypatch)
    e.disparar()
    e.tick()
    _hasta_ruptura(e, ATM)
    _terminar_ruptura(e)
    r = e.resultado()
    assert r["estado"] == "sin_vacio" and r["estado"] != "hecho"
    assert r["segundos"] == 20
    assert [c for c, _ in e.alarmas.activadas] == [CIC_20]
    assert e.alarmas.activadas[0][1] == {"segundos": 5, "minimo": ATM - RANGO}
    terminado = [d for ev, d in e.eventos if ev == "estado_seguro_secado_terminado"]
    assert terminado and terminado[-1]["resultado"] == "sin_vacio"
    # el estado seguro sigue y termina con sus 3 lecturas (no se queda colgado)
    for _ in range(3):
        e.tick()
    assert not e.es.activo


def test_vacio_parcial_sin_sostener_da_sin_vacio_y_la_ruptura_abre_el_aire(monkeypatch):
    """La presión baja de la banda pero vuelve a subir antes de N s: no
    cuenta. La ruptura corre igual y abre el aire hasta la banda."""
    e = _equipo(monkeypatch, segundos=20, vacio_s=8)
    e.disparar()
    e.tick()
    vuelta = [0]

    def presion():
        vuelta[0] += 1
        # 6 s bajo la banda, 1 tick en la banda, y otra vez
        return ATM if vuelta[0] % 25 == 0 else ATM - RANGO - 3.0
    _hasta_ruptura(e, presion)
    assert not e.protocolo._vacio_logrado
    e.pres(ATM - RANGO - 3.0)                         # quedó en vacío al apagar
    e.tick()
    assert e.salidas.on("aire_atmosferico_camara")    # la ruptura no se omite
    _terminar_ruptura(e)
    assert not e.salidas.on("aire_atmosferico_camara")
    assert e.resultado()["estado"] == "sin_vacio"


def test_vacio_logrado_tarde_dentro_del_tiempo_cuenta(monkeypatch):
    e = _equipo(monkeypatch, segundos=20, vacio_s=5)
    e.disparar()
    e.tick()
    t0 = e.reloj[0]
    _hasta_ruptura(e, lambda: ATM if e.reloj[0] - t0 < 12 else 30.0)
    _terminar_ruptura(e)
    assert e.resultado()["estado"] == "hecho"


def test_vacio_que_llega_demasiado_tarde_da_sin_vacio(monkeypatch):
    e = _equipo(monkeypatch, segundos=20, vacio_s=5)
    e.disparar()
    e.tick()
    t0 = e.reloj[0]
    _hasta_ruptura(e, lambda: ATM if e.reloj[0] - t0 < 17 else 30.0)
    _terminar_ruptura(e)
    assert e.resultado()["estado"] == "sin_vacio"


def test_ruptura_que_no_llega_sin_vacio_logrado_sigue_dando_sin_ruptura(monkeypatch):
    """Con la ruptura vencida el aviso es la ruptura (la cámara queda en
    vacío: NO ABRIR por presión); nunca hecho."""
    e = _equipo(monkeypatch, segundos=2, vacio_s=5)
    e.disparar()
    e.tick()
    _hasta_ruptura(e, 20.0)
    for _ in range(int((pf._RUPTURA_LIMITE_S + 5) / 0.25)):
        e.tick()
        if not e.protocolo.secando:
            break
    assert e.resultado()["estado"] == "sin_ruptura"


# ── falla cerrada: sin lectura ──────────────────────────────────────────────

def test_sin_lectura_de_presion_nunca_da_hecho(monkeypatch):
    """Presión sin lectura durante el secado: no se verifica nada; el secado
    se corta (bomba y vacío apagados ya) y el resultado no es hecho."""
    e = _equipo(monkeypatch)
    e.disparar()
    e.tick()
    e.pres(20.0)
    e.tick()
    e.pres(None)
    e.tick()
    assert not any(e.salidas.on(s) for s in VACIO)
    r = e.resultado()
    assert r["estado"] == "cortado" and r["motivo"] == "sin_presion"
    assert not e.protocolo._vacio_logrado


@pytest.mark.parametrize("pres", [None, float("nan"), float("inf"), "x", True])
def test_seguir_vacio_sin_lectura_reinicia_el_conteo(monkeypatch, pres):
    e = _equipo(monkeypatch)
    p = e.protocolo
    p._ai_vigente_tick = True
    p._seguir_vacio(20.0, ATM, RANGO, 100.0)
    assert p._vacio_desde == 100.0
    p._seguir_vacio(pres, ATM, RANGO, 103.0)
    assert p._vacio_desde is None and not p._vacio_logrado
    p._seguir_vacio(20.0, ATM, RANGO, 104.0)
    p._seguir_vacio(20.0, ATM, RANGO, 108.0)
    assert not p._vacio_logrado                       # 4 s < 5 s: el conteo volvió a cero


def test_seguir_vacio_con_la_trama_ai_vencida_no_cuenta(monkeypatch):
    e = _equipo(monkeypatch)
    p = e.protocolo
    p._ai_vigente_tick = False
    p._seguir_vacio(20.0, ATM, RANGO, 100.0)
    p._seguir_vacio(20.0, ATM, RANGO, 200.0)
    assert p._vacio_desde is None and not p._vacio_logrado


def test_presion_en_la_banda_no_es_vacio(monkeypatch):
    e = _equipo(monkeypatch)
    p = e.protocolo
    p._ai_vigente_tick = True
    for t in range(0, 30):
        p._seguir_vacio(ATM - RANGO, ATM, RANGO, 100.0 + t)    # justo en el borde
    assert not p._vacio_logrado


# ── parámetro ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("valor", [None, 0, 61, -1, "10", True, float("nan")])
def test_parametro_invalido_usa_el_defecto(monkeypatch, valor):
    e = _equipo(monkeypatch)
    e.config["secado_tras_fallo_vacio_s"] = valor
    assert e.protocolo._segundos_vacio() == pf.VACIO_DEFECTO_S


def test_parametro_leido_en_cada_uso(monkeypatch):
    e = _equipo(monkeypatch, segundos=20, vacio_s=60)
    e.disparar()
    e.tick()
    e.config["secado_tras_fallo_vacio_s"] = 3          # cambiado en vuelo
    _hasta_ruptura(e, 20.0)
    _terminar_ruptura(e)
    assert e.resultado()["estado"] == "hecho"


# ── catálogo, bitácora, ticket ──────────────────────────────────────────────

def test_cic20_aviso_no_bloqueante():
    d = CATALOGO[CIC_20]
    assert d.nivel is Nivel.AVISO and d.bloquea_inicio is False
    for idioma in ("es", "en"):
        assert i18n.existe(f"alarmas.{CIC_20}.titulo", idioma)


def test_eventos_del_secado_clasificados_en_seguridad():
    for ev in ("estado_seguro_secado_iniciado", "estado_seguro_secado_terminado"):
        assert ev in bitacora.EVENTOS_REGISTRADOS
        assert bitacora.categoria_de(ev) == "seguridad"


@pytest.mark.parametrize("idioma,esperado", [("es", "sin lograr vacío"),
                                             ("en", "without reaching vacuum")])
def test_linea_del_ticket_sin_vacio(idioma, esperado):
    from autoclave.services.domain.logging import ticket_formatter as tf
    aviso = aviso_secado_tras_fallo({"estado": "sin_vacio", "motivo": None, "segundos": 60})
    assert aviso == {"clave": CLAVE_SECADO_TRAS_FALLO, "estado": "sin_vacio", "segundos": 60,
                     "motivo": None}
    p = type("P", (), {"idioma": idioma})()
    linea = tf._linea_secado(aviso, p)
    assert esperado in linea and "60" in linea


def test_sin_vacio_en_los_estados_publicados():
    assert pf.SECADO_SIN_VACIO in pf.ESTADOS_SECADO
