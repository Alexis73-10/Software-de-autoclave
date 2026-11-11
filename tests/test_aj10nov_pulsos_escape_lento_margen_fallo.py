"""Ajuste 10-nov: pulsos del escape lento en DESCOMPRESION y margen de fallo
de la contrapresión (CIC-24) según la temperatura del líquido."""

import copy
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers import catalogo_parametros as cp
from autoclave.core.managers import cycle_manager as cm
from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.state_machine.cycle_phases import enfriamiento_contrapresion as ec
from autoclave.state_machine.cycle_phases.descompresion import (
    DescompresionFase, parametros_enfriamiento, valores_alarma_enfriamiento)
from autoclave.state_machine.cycle_phases.pulso_escape_lento import PulsoEscapeLento
from tests.test_descompresion_fase import _make_fase


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def avanzar(self, s):
        self.t += s


# ── PulsoEscapeLento (puro) ──────────────────────────────────────────────────

def test_pulso_abre_t_on_cierra_t_off_y_repite():
    r = Reloj()
    p = PulsoEscapeLento(ahora=r)
    assert p.decidir(True, 2, 3) is True            # arranca abierto
    r.avanzar(1.9); assert p.decidir(True, 2, 3) is True
    r.avanzar(0.1); assert p.decidir(True, 2, 3) is False   # 2 s: cierra
    r.avanzar(2.9); assert p.decidir(True, 2, 3) is False
    r.avanzar(0.1); assert p.decidir(True, 2, 3) is True    # 3 s cerrada: reabre


def test_pulso_off_cero_es_continuo_y_defectos_invalidos():
    r = Reloj()
    p = PulsoEscapeLento(ahora=r)
    for _ in range(5):
        assert p.decidir(True, 1, 0) is True
        r.avanzar(10)
    # valores no válidos -> defecto 1/0 (continuo), nunca cerrada para siempre
    for malo in (None, "x", True, -1, float("nan")):
        assert p.decidir(True, malo, malo) is True


def test_pulso_no_quiere_abierta_cierra_y_reinicia():
    r = Reloj()
    p = PulsoEscapeLento(ahora=r)
    p.decidir(True, 1, 5)
    r.avanzar(1); assert p.decidir(True, 1, 5) is False
    assert p.decidir(False, 1, 5) is False
    assert p.decidir(True, 1, 5) is True            # empieza abierto de nuevo


# ── Integración en DescompresionFase ─────────────────────────────────────────

def _lenta(set_do):
    return [c[0] for c in set_do.mock_calls if c[0] in
            ("descompresion_lenta_on", "descompresion_lenta_off")]


def test_modo_2_pulsa_la_lenta(monkeypatch):
    t = [5000.0]
    monkeypatch.setattr("autoclave.state_machine.cycle_phases.descompresion.time.monotonic",
                        lambda: t[0])
    extra = {("descompresion", "escape_lento_on"): 2, ("descompresion", "escape_lento_off"): 4}
    fase, estado, set_do = _make_fase(modo=2, pres=300.0, extra_params=extra)
    fase.update()                                   # inicia el modo
    secuencia = []
    for _ in range(14):
        set_do.reset_mock()
        fase.update()
        secuencia.append(_lenta(set_do)[-1])
        t[0] += 1.0
    # 2 s abierta, 4 s cerrada, repite
    esperado = (["descompresion_lenta_on"] * 2 + ["descompresion_lenta_off"] * 4) * 2
    assert secuencia[:12] == esperado


def test_modo_2_sin_parametros_sigue_continua():
    fase, estado, set_do = _make_fase(modo=2, pres=300.0)
    fase.update()
    for _ in range(5):
        set_do.reset_mock()
        fase.update()
        assert _lenta(set_do)[-1] == "descompresion_lenta_on"


def test_modo_3_cierra_la_lenta_al_cambiar_a_rapida():
    extra = {("descompresion", "escape_lento_on"): 1, ("descompresion", "escape_lento_off"): 0}
    fase, estado, set_do = _make_fase(modo=3, pres=300.0, extra_params=extra)
    fase.update(); fase.update()
    estado.sensores_pres = {"pres_camara": 140.0}   # <= presion_cambio 150
    set_do.reset_mock()
    fase.update()
    assert _lenta(set_do)[-1] == "descompresion_lenta_off"


# ── Margen de fallo de la contrapresión ──────────────────────────────────────

T_LIQ = 105.0
PSAT = p_saturacion_kpa(T_LIQ)          # ≈120,8 kPa


def _comp(**kw):
    r = Reloj()
    params = {"presion_camara_enfriamiento": 200.0,
              "presion_despresurizacion_chaqueta": 10.0,
              "timeout_despresurizacion_chaqueta": 5,
              "timeout_presurizacion_enfriamiento": 10}
    params.update(kw)
    c = ec.EnfriamientoContrapresion(params, modo_5=False, ahora=r)
    c.tick(200.0, 75.0, T_LIQ, 75.0, True)          # cumple (a) y (b): armada
    return c, r


def _sostener(c, r, pres, segundos, t=T_LIQ):
    res = None
    for _ in range(int(segundos)):
        r.avanzar(1)
        res = c.tick(pres, 75.0, t, 75.0, True)
        if res.fallo:
            return res
    return res


def test_liquido_a_105_con_presion_sobre_psat_mas_margen_no_falla():
    """La presión cayó bajo Psat + 30 (aviso) pero sigue sobre Psat + 10: no hay fallo."""
    c, r = _comp()
    res = _sostener(c, r, PSAT + 15.0, 120)
    assert res.fallo is None
    assert res.aviso_contrapresion is True          # el aviso CIC-25 sí rige


def test_falla_si_baja_de_psat_mas_margen_de_fallo_60_s():
    c, r = _comp()
    res = _sostener(c, r, PSAT + 5.0, 60)      # el conteo parte en el primer tick bajo: 59 s
    assert res.fallo is None
    res = _sostener(c, r, PSAT + 5.0, 1)       # 60 s
    assert res.fallo == ec.ENFR_CONTRAPRESION_BAJA


def test_margen_de_fallo_configurable_y_acotado_al_de_aviso():
    c, r = _comp(margen_fallo_contrapresion=0.0)
    assert _sostener(c, r, PSAT + 1.0, 120).fallo is None
    assert _sostener(c, r, PSAT - 1.0, 61).fallo == ec.ENFR_CONTRAPRESION_BAJA
    # un valor mayor que 30 se acota a 30 (el fallo nunca es más estricto que el aviso)
    c, r = _comp(margen_fallo_contrapresion=99.0)
    assert _sostener(c, r, PSAT + 31.0, 120).fallo is None
    assert _sostener(c, r, PSAT + 29.0, 61).fallo == ec.ENFR_CONTRAPRESION_BAJA


def test_recuperar_la_presion_reinicia_el_conteo_de_fallo():
    c, r = _comp()
    _sostener(c, r, PSAT + 5.0, 50)
    assert _sostener(c, r, PSAT + 15.0, 1).fallo is None
    assert _sostener(c, r, PSAT + 5.0, 59).fallo is None   # el conteo empezó de cero


def test_sin_lectura_de_temperatura_falla_cerrada():
    c, r = _comp()
    res = None
    for _ in range(61):
        r.avanzar(1)
        res = c.tick(300.0, 75.0, None, 75.0, True)
        if res.fallo:
            break
    assert res.fallo == ec.ENFR_CONTRAPRESION_BAJA


def test_solo_aviso_no_falla_nunca():
    r = Reloj()
    c = ec.EnfriamientoContrapresion(
        {"presion_camara_enfriamiento": 200.0, "presion_despresurizacion_chaqueta": 10.0,
         "timeout_despresurizacion_chaqueta": 5, "timeout_presurizacion_enfriamiento": 10},
        modo_5=False, solo_aviso=True, ahora=r)
    c.tick(200.0, 75.0, T_LIQ, 75.0, True)
    assert _sostener(c, r, PSAT - 5.0, 120).fallo is None


def test_parametros_enfriamiento_y_valores_de_la_alarma_usan_el_margen_de_fallo():
    cycle = MagicMock()
    vals = {("descompresion", "modo_4", "presion_camara_enfriamiento"): 200,
            ("descompresion", "modo_4", "presion_despresurizacion_chaqueta"): 20,
            ("descompresion", "modo_4", "timeout_despresurizacion_chaqueta"): 3,
            ("descompresion", "modo_4", "timeout_presurizacion_enfriamiento"): 3,
            ("descompresion", "modo_4", "margen_fallo_contrapresion"): 7.5}
    cycle.get_param.side_effect = lambda *k, default=None: vals.get(k, default)
    p = parametros_enfriamiento(cycle, "modo_4")
    assert p[ec.CLAVE_MARGEN_FALLO] == 7.5
    v = valores_alarma_enfriamiento(ec.ENFR_CONTRAPRESION_BAJA, p, 4, 75.0)
    assert v["margen"] == "7.5"
    # sin el parámetro: defecto
    vals.pop(("descompresion", "modo_4", "margen_fallo_contrapresion"))
    assert parametros_enfriamiento(cycle, "modo_4")[ec.CLAVE_MARGEN_FALLO] == \
        ec.MARGEN_FALLO_CONTRAPRESION_DEFECTO


# ── Catálogo, migración y programas de fábrica ───────────────────────────────

_RUTAS = Path(cm.__file__).resolve().parents[2] / "cycles" / "factory"


def test_defectos_coinciden_entre_catalogo_y_componente():
    assert cp.MARGEN_FALLO_CONTRAPRESION_DEFECTO == ec.MARGEN_FALLO_CONTRAPRESION_DEFECTO


def test_migracion_agrega_los_parametros_con_defecto_e_idempotente():
    programa = json.loads((_RUTAS / "prion.json").read_text(encoding="utf-8"))
    params = copy.deepcopy(programa["parameters"])
    desc = params["descompresion"]
    for k in ("escape_lento_on", "escape_lento_off"):
        desc.pop(k, None)
    for m in ("modo_4", "modo_5"):
        desc[m].pop("margen_fallo_contrapresion", None)
    aud = []
    assert cm._agregar_claves_aj10nov(params, aud) is True
    assert desc["escape_lento_on"]["value"] == 1 and desc["escape_lento_off"]["value"] == 0
    assert desc["modo_4"]["margen_fallo_contrapresion"]["value"] == 10.0
    assert desc["modo_5"]["margen_fallo_contrapresion"]["value"] == 10.0
    assert len(aud) == 4 and all(a["anterior"] is None for a in aud)
    assert all(a["origen"] == cp.ORIGEN_MIGRACION_AJ_10NOV for a in aud)
    antes = copy.deepcopy(params)
    assert cm._agregar_claves_aj10nov(params, []) is False
    assert params == antes


def test_migracion_no_cambia_valores_existentes():
    params = {"descompresion": {"escape_lento_on": {"value": 3}, "escape_lento_off": {"value": 7},
                                "modo_4": {"margen_fallo_contrapresion": {"value": 4.0},
                                           "timeout": {"value": 120}}}}
    assert cm._agregar_claves_aj10nov(params, []) is False
    assert params["descompresion"]["escape_lento_on"]["value"] == 3
    assert params["descompresion"]["modo_4"]["margen_fallo_contrapresion"]["value"] == 4.0


@pytest.mark.parametrize("archivo", sorted(p.name for p in _RUTAS.glob("*.json")))
def test_programas_de_fabrica_validos_y_con_los_parametros(archivo):
    """Con o sin las claves en el JSON, tras la migración el programa es válido."""
    params = json.loads((_RUTAS / archivo).read_text(encoding="utf-8"))["parameters"]
    cm._agregar_claves_aj10nov(params, [])
    desc = params["descompresion"]
    assert desc["escape_lento_on"]["value"] >= 1 and desc["escape_lento_off"]["value"] >= 0
    for m in ("modo_4", "modo_5"):
        assert 0 <= desc[m]["margen_fallo_contrapresion"]["value"] <= 30
    assert cp.errores_programa(params) == []


def test_rangos_del_catalogo_rechazan_valores_fuera_de_rango():
    assert cp.CATALOGO[("descompresion", "escape_lento_on")][:2] == (1, 1000)
    assert cp.CATALOGO[("descompresion", "escape_lento_off")][:2] == (0, 1000)
    assert cp.CATALOGO[("descompresion", "modo_4.margen_fallo_contrapresion")][:2] == (0, 30)
    assert cp.CATALOGO[("descompresion", "modo_5.margen_fallo_contrapresion")][:2] == (0, 30)


def test_i18n_es_en_tienen_rotulos_y_descripciones():
    base = Path(cm.__file__).resolve().parents[2] / "i18n"
    for idioma in ("es", "en"):
        d = json.loads((base / f"{idioma}.json").read_text(encoding="utf-8"))
        for seccion in ("parametros", "parametros_desc"):
            desc = d[seccion]["descompresion"]
            assert desc["escape_lento_on"] and desc["escape_lento_off"]
            for m in ("modo_4", "modo_5"):
                assert desc[m]["margen_fallo_contrapresion"]
