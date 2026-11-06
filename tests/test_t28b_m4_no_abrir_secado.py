"""Tanda 28b (A13-M4, decisión de Cristian del 6-nov; resuelve AJ28B-07):
NO ABRIR durante el secado tras fallo.

`camara_segura` (y con ella /status.camara_segura, el interlock de puertas,
el inicio de ciclo y «Apagar equipo») da «no segura» con el motivo
`secando_vapor_residual` mientras el protocolo seca (vacío, apagado y
ruptura), desde el primer tick y también con el resultado todavía pendiente
(CicloState esperando la confirmación) si nada más lo impide.
"""

from unittest.mock import MagicMock

import pytest

from autoclave import i18n
from autoclave.core.runtime import camara_segura, motivos
from autoclave.ui_qml.domain import detalle_aviso
from tests.test_t28b_a13_secado_tras_fallo import ATM, RANGO, _Equipo
from tests.test_t28b_a13r_secado_revision import _ciclo_real

SECANDO = "secando_vapor_residual"


def _evaluar(e):
    return camara_segura.evaluar(e.estado, e.config, [e.programa])


def _codigo(motivo):
    return getattr(motivo, "codigo", None)


# ── primer tick, vacío, ruptura ─────────────────────────────────────────────

def test_primer_tick_del_secado_ya_es_no_abrir(monkeypatch):
    """Presión en la banda y temperatura baja: sin M4 la cámara se veía
    segura en el tick en que empieza el secado."""
    e = _Equipo(monkeypatch)
    e.disparar()
    e.tick()                                          # este tick empieza el secado
    assert e.protocolo.secando and e.estado.secando_tras_fallo is True
    segura, motivo = _evaluar(e)
    assert segura is False and _codigo(motivo) == SECANDO
    assert [_codigo(m) for m in camara_segura.motivos(e.estado, e.config, [e.programa])] == [SECANDO]


def test_durante_el_vacio_el_motivo_es_el_secado_y_no_el_vacio(monkeypatch):
    e = _Equipo(monkeypatch)
    e.disparar()
    e.tick()
    e.pres(20.0)
    e.tick()
    segura, motivo = _evaluar(e)
    assert segura is False and _codigo(motivo) == SECANDO


def test_durante_la_ruptura_y_el_apagado_es_no_abrir(monkeypatch):
    e = _Equipo(monkeypatch, segundos=2)
    e.config["secado_tras_fallo_vacio_s"] = 1
    e.disparar()
    e.tick()
    e.pres(20.0)
    vistas = set()
    for _ in range(40):
        fase = e.protocolo._secado_fase
        if fase is None:
            break
        if fase == "ruptura":
            e.pres(ATM - RANGO - 0.5)                  # casi en la banda
        vistas.add(fase)
        segura, motivo = _evaluar(e)
        assert segura is False and _codigo(motivo) == SECANDO, fase
        e.tick()
    assert {"secado", "apagando", "ruptura"} <= vistas


def test_al_terminar_la_ruptura_deja_de_ser_motivo(monkeypatch):
    e = _Equipo(monkeypatch, segundos=2)
    e.config["secado_tras_fallo_vacio_s"] = 1
    e.disparar()
    e.tick()
    e.pres(20.0)
    while e.protocolo._secado_fase != "ruptura":
        e.tick()
    e.pres(ATM)
    e.tick()                                          # ruptura completa
    assert not e.protocolo.secando and e.estado.secando_tras_fallo is False
    assert e.resultado()["estado"] == "hecho"
    assert _evaluar(e) == (True, "")


def test_secado_cortado_libera_el_motivo(monkeypatch):
    e = _Equipo(monkeypatch)
    e.disparar()
    e.tick()
    e.estado.sensores_di["puerta_1_cerrada"] = 0     # una puerta se abre: corta
    e.tick()
    assert e.resultado()["estado"] == "cortado"
    assert e.estado.secando_tras_fallo is False
    segura, motivo = _evaluar(e)
    assert _codigo(motivo) != SECANDO


# ── pendiente ───────────────────────────────────────────────────────────────

def test_pendiente_con_la_camara_por_lo_demas_segura_es_no_abrir(monkeypatch):
    """Resultado pendiente (el protocolo lo arrancará al llegar a la banda):
    entre el tick del lazo y el del protocolo, la cámara no se ve segura."""
    e = _Equipo(monkeypatch)
    e.protocolo.ejecutar()                            # sin ningún update todavía
    assert e.resultado()["estado"] == "pendiente"
    segura, motivo = _evaluar(e)
    assert segura is False and _codigo(motivo) == SECANDO


def test_pendiente_con_sobrepresion_muestra_la_sobrepresion(monkeypatch):
    e = _Equipo(monkeypatch)
    e.pres(250.0)
    e.protocolo.ejecutar()
    segura, motivo = _evaluar(e)
    assert segura is False and _codigo(motivo) == "sobrepresion"
    assert [_codigo(m) for m in camara_segura.motivos(e.estado, e.config, [e.programa])] \
        == ["sobrepresion"]


def test_omitido_no_es_motivo(monkeypatch):
    e = _Equipo(monkeypatch, tipo="liquido")
    e.protocolo.ejecutar()
    assert e.resultado()["estado"] == "omitido"
    assert _evaluar(e) == (True, "")


def test_finalizar_con_el_secado_pendiente_lo_omite(monkeypatch):
    """Un cierre forzado (terminar() al entrar a un ciclo) no deja el
    «pendiente» publicado: NO ABRIR no queda pegado."""
    e = _Equipo(monkeypatch)
    e.pres(250.0)
    e.protocolo.ejecutar()
    e.protocolo.finalizar()
    assert e.resultado() == {"estado": "omitido", "motivo": "no_aplica", "segundos": None}
    e.pres(ATM)
    assert _evaluar(e) == (True, "")


def test_ciclo_esperando_confirmacion_con_el_secado_en_curso(monkeypatch):
    """CicloState real: FALLO esperando la confirmación, el secado corre
    en el propio ciclo; /status (camara_segura) dice NO ABRIR por el secado."""
    e = _Equipo(monkeypatch)
    ciclo = _ciclo_real(e)
    segura, motivo = _evaluar(e)                      # pendiente, antes del primer run
    assert segura is False and _codigo(motivo) == SECANDO
    ciclo.run()
    assert e.protocolo.secando
    segura, motivo = _evaluar(e)
    assert segura is False and _codigo(motivo) == SECANDO


def test_reset_del_protocolo_limpia_todo(monkeypatch):
    e = _Equipo(monkeypatch)
    e.disparar()
    e.tick()
    assert e.estado.secando_tras_fallo is True
    e.protocolo.reset()
    assert e.estado.secando_tras_fallo is False and e.estado.secado_tras_fallo is None
    assert _evaluar(e) == (True, "")


# ── consumidores y presentación ─────────────────────────────────────────────

def test_sin_datos_vigentes_sigue_primero():
    estado = MagicMock()
    estado.secando_tras_fallo = True
    segura, motivo = camara_segura.evaluar(estado, {}, [], datos_vigentes=False)
    assert segura is False and _codigo(motivo) == "sin_datos_vigentes"


def test_doble_sin_el_atributo_no_cambia_nada():
    """Un MagicMock (pruebas anteriores) no se lee como secando."""
    assert camara_segura.secado_en_curso(MagicMock()) is False
    assert camara_segura.secado_pendiente(MagicMock()) is False


def test_preparado_no_permite_iniciar_durante_el_secado(monkeypatch):
    from autoclave.state_machine.states.preparado import preparado_state as PreparadoState
    e = _Equipo(monkeypatch)
    e.disparar()
    e.tick()
    p = PreparadoState.__new__(PreparadoState)
    p.estado, p.config, p.cycle, p.profile = e.estado, e.config, e.programa, None
    p.programas_seguridad = None
    p.temp_max_ciclo = None
    assert p.camara_segura() is False


def test_no_es_un_motivo_de_sensor():
    lista = [camara_segura._motivo_secando()]
    assert camara_segura.solo_por_sensor(lista) is False


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_textos_del_motivo(idioma):
    assert SECANDO in motivos.CODIGOS
    m = camara_segura._motivo_secando()
    assert motivos.texto(m, idioma) == i18n.t("puerta." + SECANDO, idioma)
    desc, accion = detalle_aviso._motivo_no_abrir({"codigo": SECANDO, "valores": {},
                                                   "limites": {}}, idioma)
    assert desc and accion and "{" not in desc + accion
    assert desc == i18n.t(f"aviso_detalle.no_abrir_motivos.{SECANDO}.descripcion", idioma)
