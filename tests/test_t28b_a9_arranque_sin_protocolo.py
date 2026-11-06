"""Tanda 28 (A9, decisión de Cristian del 5-nov, reemplaza D9-1.1 en el
encendido normal): arranque con la cámara no segura sin protocolo activo.

- Encendido normal (el último ciclo terminó o no hay ciclo): NO se inicia el
  protocolo de estado seguro; PREPARACION iguala la presión (aire atmosférico
  con vacío, venteo con presión) con sus reglas. NO ABRIR y el bloqueo de
  apertura e inicio siguen (camara_segura sin cambio).
- Tras un ciclo interrumpido: el protocolo de arranque sigue igual, con el
  origen "ciclo_interrumpido" (solo la lenta mientras la carga líquida esté
  caliente).
- Sin saber si hubo ciclo interrumpido (sin base, error): se trata como
  interrumpido (falla segura).
- Antes de la liberación del arranque (tanda 26) no se enciende ninguna salida.

Con el ControlLoop REAL y la planta simulada de S9/T11.
"""

import threading
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime import camara_segura
from autoclave.state_machine.machine.enum_global import GlobalState
from tests import test_t11_programas_integracion as t11
from tests.test_e1_ensayo_simulador import programas  # noqa: F401
from tests.test_s9_planta_simulada import (
    DE_PROCESO, VALVULAS_PROHIBIDAS_LENTA, _caliente_a_presion, _en_vacio, _equipo, _tick,
)
from tests.test_t11_programas_integracion import psat

_SOLIDO = 2        # Instrumental 134
_LIQUIDO = 4       # Líquidos


def _segura(a) -> bool:
    loop = a["loop"]
    segura, _ = camara_segura.evaluar(a["estado"], a["config"], loop.programas_para_seguridad(),
                                      None, temp_max_ciclo=loop.temp_max_tras_ciclo())
    return segura is True


def _recorrer(a, limite_s):
    """Ticks hasta 3 lecturas seguras sin recuperación pendiente o el límite.
    Devuelve lo visto: protocolo, salidas abiertas, NO ABRIR mientras no es
    segura, LISTO con la cámara no segura."""
    visto = {"protocolo": False, "abiertas": set(), "abiertas_protocolo": set(), "causas": set(),
             "no_segura_con_listo": 0, "ticks_no_segura": 0, "aire_con_presion": 0}
    atm, rango = t11.P_ATM, float(a["config"].get("rango_presion_atm"))
    es = a["loop"].estado_seguro
    for _ in range(int(limite_s / t11.DT / 4)):
        _tick(a)
        visto["protocolo"] |= es.activo
        if es.causa:
            visto["causas"].add(es.causa)
        visto["abiertas"] |= {k for k in DE_PROCESO if a["modulo_es"].on(k)}
        if es.activo:
            visto["abiertas_protocolo"] |= {k for k in DE_PROCESO if a["modulo_es"].on(k)}
        if not _segura(a):
            visto["ticks_no_segura"] += 1
            if a["estado"].get_flag("LISTO_PARA_CICLO"):
                visto["no_segura_con_listo"] += 1
        if a["modulo_es"].on("aire_admosferico_camara") and a["p_publicada"] > atm + rango:
            visto["aire_con_presion"] += 1
        if a["loop"]._recuperacion_pendiente is None and not es.activo:
            break
    visto["segura_al_final"] = _segura(a)
    visto["pendiente_al_final"] = a["loop"]._recuperacion_pendiente is not None
    return visto


def _eventos(a):
    registro = []
    a["loop"].al_evento_seguridad = lambda ev, det: registro.append((ev, det))
    return registro


# ── 1. encendido normal ────────────────────────────────────────────────────

def test_arranque_normal_con_vacio_sin_protocolo_preparacion_abre_el_aire(programas, monkeypatch):  # noqa: F811
    a = _equipo(programas[_SOLIDO], monkeypatch, programas)
    eventos = _eventos(a)
    _en_vacio(a["planta"])
    a["loop"].recuperar_ciclo_interrumpido(a["programa"].copia(), interrumpido=False)
    assert not _segura(a)                       # NO ABRIR al arrancar
    v = _recorrer(a, 1800)
    assert v["protocolo"] is False and not v["causas"], v
    assert "aire_admosferico_camara" in v["abiertas"], v
    assert v["ticks_no_segura"] > 0 and v["no_segura_con_listo"] == 0, v
    assert v["aire_con_presion"] == 0, v
    assert v["segura_al_final"] is True and v["pendiente_al_final"] is False, v
    # un solo aviso en la bitácora, sin estado seguro
    avisos = [d for e, d in eventos if e == "arranque_camara_no_segura"]
    assert len(avisos) == 1 and avisos[0]["estado_seguro"] is False
    assert not any(e == "estado_seguro_iniciado" for e, _ in eventos)


def test_arranque_normal_con_sobrepresion_solido_ventea_preparacion(programas, monkeypatch):  # noqa: F811
    a = _equipo(programas[_SOLIDO], monkeypatch, programas)
    planta = a["planta"]
    planta.t = planta.t_sonda = 40.0
    planta.p_v = psat(40.0)
    planta.p_aire = t11.P_ATM + 30.0 - planta.p_v          # 30 kPa de presión residual
    a["loop"].recuperar_ciclo_interrumpido(a["programa"].copia(), interrumpido=False)
    assert not _segura(a)
    v = _recorrer(a, 1800)
    assert v["protocolo"] is False and not v["causas"], v
    # venteo de PREPARACION (sólido: la rápida); nunca el aire con presión
    assert "descompresion_rapida" in v["abiertas"], v
    assert v["aire_con_presion"] == 0 and v["no_segura_con_listo"] == 0, v
    assert v["segura_al_final"] is True, v


def test_arranque_normal_programa_liquido_ventea_solo_por_la_lenta(programas, monkeypatch):  # noqa: F811
    """El programa del último ciclo (líquido) sigue contando en un encendido
    normal: PREPARACION ventea por la lenta (T1), nunca la rápida."""
    a = _equipo(programas[_LIQUIDO], monkeypatch, programas)
    planta = a["planta"]
    planta.t = planta.t_sonda = 40.0
    planta.p_v = psat(40.0)
    planta.p_aire = t11.P_ATM + 30.0 - planta.p_v
    a["loop"].recuperar_ciclo_interrumpido(a["programa"].copia(), interrumpido=False)
    v = _recorrer(a, 3 * 3600)
    assert v["protocolo"] is False, v
    assert "descompresion_lenta" in v["abiertas"], v
    assert "descompresion_rapida" not in v["abiertas"], v


# ── 2. tras un ciclo interrumpido ──────────────────────────────────────────

def test_ciclo_interrumpido_liquido_corre_el_protocolo_solo_por_la_lenta(programas, monkeypatch):  # noqa: F811
    a = _equipo(programas[_LIQUIDO], monkeypatch, programas)
    eventos = _eventos(a)
    _caliente_a_presion(a["planta"])
    a["loop"].recuperar_ciclo_interrumpido(a["programa"].copia(), interrumpido=True)
    v = _recorrer(a, 4 * 3600)
    assert v["protocolo"] is True and v["causas"] == {"ciclo_interrumpido"}, v
    assert "descompresion_lenta" in v["abiertas_protocolo"], v
    assert not v["abiertas_protocolo"] & set(VALVULAS_PROHIBIDAS_LENTA), v
    assert v["no_segura_con_listo"] == 0 and v["aire_con_presion"] == 0, v
    assert v["segura_al_final"] is True, v
    iniciados = [d for e, d in eventos if e == "estado_seguro_iniciado"]
    assert iniciados and iniciados[0]["origen"] == "ciclo_interrumpido"
    avisos = [d for e, d in eventos if e == "arranque_camara_no_segura"]
    assert avisos and avisos[0]["estado_seguro"] is True


def test_por_omision_se_trata_como_interrumpido(programas, monkeypatch):  # noqa: F811
    """Quien llama sin decir si hubo ciclo interrumpido obtiene el protocolo
    (falla segura)."""
    a = _equipo(programas[_SOLIDO], monkeypatch, programas)
    _caliente_a_presion(a["planta"])
    a["loop"].recuperar_ciclo_interrumpido(a["programa"].copia())
    _tick(a)
    assert a["loop"].estado_seguro.activo
    assert a["loop"].estado_seguro.causa == "ciclo_interrumpido"


# ── 3. retención del arranque (tanda 26): ninguna salida antes ─────────────

@pytest.mark.parametrize("interrumpido", [False, True])
def test_ninguna_salida_antes_de_la_liberacion(programas, monkeypatch, interrumpido):  # noqa: F811
    a = _equipo(programas[_SOLIDO], monkeypatch, programas)
    a["loop"].arranque_liberado = threading.Event()          # retenido
    _en_vacio(a["planta"])
    a["loop"].recuperar_ciclo_interrumpido(a["programa"].copia(), interrumpido=interrumpido)
    for _ in range(30):
        _tick(a)
        assert not {k for k in DE_PROCESO if a["modulo_es"].on(k)}
        assert not a["loop"].estado_seguro.activo
        assert not _segura(a)                                # NO ABRIR
    a["loop"].arranque_liberado.set()
    v = _recorrer(a, 1800)
    assert v["protocolo"] is interrumpido, v
    assert "aire_admosferico_camara" in v["abiertas"], v
    assert v["segura_al_final"] is True, v


# ── 4. el contexto decide si hubo ciclo interrumpido ───────────────────────

def _contexto():
    from autoclave.backend.context import BackendContext
    return BackendContext()


def test_sin_base_se_trata_como_interrumpido():
    ctx = _contexto()
    ctx._ciclo_interrumpido = None
    ctx._marca_interrumpido = None
    ctx.sin_base_de_datos = True
    assert ctx.hubo_ciclo_interrumpido() is True


def test_sin_consulta_de_la_base_se_trata_como_interrumpido():
    ctx = _contexto()                           # nunca se cerraron los ciclos
    assert not hasattr(ctx, "_ciclo_interrumpido")
    assert ctx.hubo_ciclo_interrumpido() is True


def test_fallo_al_cerrar_ciclos_se_trata_como_interrumpido(monkeypatch):
    from autoclave.backend.context import BackendContext
    contador = MagicMock()
    contador.en_curso.return_value = None
    monkeypatch.setattr(BackendContext, "contador_ciclos", property(lambda self: contador))
    ctx = _contexto()
    ctx.db = MagicMock()
    ctx.db.max_numero_ciclo.return_value = 0
    ctx.db.cerrar_ciclos_interrumpidos.side_effect = RuntimeError("base")
    ctx._reimportar_respaldos = lambda: None
    ctx._numeracion_y_ciclos_interrumpidos()
    assert ctx.hubo_ciclo_interrumpido() is True


@pytest.mark.parametrize("fila, marca, esperado", [
    (None, None, False),
    ({"id": 7, "numero_ciclo": 3}, None, True),
    (None, {"programa": None}, True),
])
def test_ciclo_interrumpido_segun_la_base_o_la_marca(fila, marca, esperado):
    ctx = _contexto()
    ctx._ciclo_interrumpido = fila
    ctx._marca_interrumpido = marca
    ctx.sin_base_de_datos = False
    assert ctx.hubo_ciclo_interrumpido() is esperado


def test_construir_control_pasa_si_hubo_ciclo_interrumpido(monkeypatch):
    from autoclave.backend import context as ctx_mod
    loop = MagicMock()
    monkeypatch.setattr(ctx_mod, "build_enlace", lambda units, al_conectar=None: MagicMock())
    monkeypatch.setattr(ctx_mod, "build_doors_cfg", lambda profile: [])
    for nombre in ("SetOutput", "ServicioPuertas", "RealtimePrinter", "CycleLogger"):
        monkeypatch.setattr(ctx_mod, nombre, MagicMock())
    monkeypatch.setattr(ctx_mod, "ControlLoop", MagicMock(return_value=loop))
    ctx = _contexto()
    ctx._ciclo_interrumpido = None
    ctx._marca_interrumpido = None
    ctx.construir_control()
    assert loop.recuperar_ciclo_interrumpido.call_args.kwargs == {"interrumpido": False}


# ── 5. presentación ────────────────────────────────────────────────────────

def test_causa_arranque_retirada_y_ciclo_interrumpido_con_texto():
    from autoclave import i18n
    from autoclave.ui_qml.bridge.ui_bridge import _CAUSAS_ESTADO_SEGURO
    assert "arranque" not in _CAUSAS_ESTADO_SEGURO
    assert "ciclo_interrumpido" in _CAUSAS_ESTADO_SEGURO
    for idioma in ("es", "en"):
        assert i18n.existe("sistema.estado_seguro_causa_ciclo_interrumpido", idioma)
        assert not i18n.existe("sistema.estado_seguro_causa_arranque", idioma)
    assert "interrumpido" in i18n.t("sistema.estado_seguro_causa_ciclo_interrumpido", "es")


def test_detalle_ald_nombra_el_ciclo_interrumpido():
    from autoclave import i18n
    from autoclave.ui_qml.domain import detalle_aviso
    fila = detalle_aviso.armar("estado_seguro_en_curso", {"causa": "ciclo_interrumpido"})
    assert i18n.t("sistema.estado_seguro_causa_ciclo_interrumpido", "es") in fila["descripciones"]["es"]
