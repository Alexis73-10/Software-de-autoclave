# tests/test_t16_s1_esterilizacion.py
#
# Tanda 16, s1 (ESTERILIZACION):
#   - VCH E (modo chaqueta): actúa vapor_chaqueta, vapor_camara abierta,
#     aislamiento VCH-AIS (CIC-15 / CIC-16), inhibición D-CHQ, sin lectura,
#     COMPLETADO / FALLO cierran las dos;
#   - P5 / D-14.5: tope de reinicios de la exposición (CIC-17);
#   - P6 / D-14.6: debounce acumulado (5 s en 10 s) en las fallas, C-03 y C-13;
#   - SAF-05 (P8): el tramo sin lectura empieza en la última lectura válida;
#   - P8 / D-14.8: excursión confirmada que pierde la lectura.
# Reloj monotonic simulado (tests/helpers/t12_e12_apoyo.py).

from types import SimpleNamespace

import pytest

from autoclave.state_machine.cycle_phases import esterilizacion as est
from autoclave.state_machine.cycle_phases.aislamiento_camara import AislamientoCamara
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from tests.helpers import t12_e12_apoyo as ap

pytestmark = pytest.mark.req("T16-S1")

T_EST = 134.0
PRESION_ADD = 11.0
TECHO = ap.psat(T_EST) + PRESION_ADD          # P_control_max ≈ 315.2 kPa
# lectura dentro de todo: RECUPERACION (T < T_est + brecha 0.3 del doble)
T_OK = 134.0
P_OK = ap.psat(134.0)
# lectura en el techo sin otra falla: Tsat(315.2) ≈ 135.0, dT ≈ +0.5 K
T_TECHO = 134.5


def _con_params(f, **extras):
    base = f.cycle.get_param.side_effect

    def get_param(seccion, param, default=None):
        if param in extras:
            return extras[param]
        return base(seccion, param, default)

    f.cycle.get_param.side_effect = get_param


def _chaqueta(monkeypatch, temp=T_OK, pres=P_OK, extras=None, **kw):
    kw.setdefault("tiempo_min", 30)
    f, estado, set_do, reloj = ap.fase(monkeypatch, t_est=T_EST, presion_add=PRESION_ADD,
                                       temp=temp, pres=pres, **kw)
    estado.modo_vapor = "chaqueta"
    estado.inhibir_vapor_chaqueta = False
    if extras:
        _con_params(f, **extras)
    return f, estado, set_do, reloj


def _ticks(f, reloj, segundos, paso=0.5):
    res = []
    for _ in range(int(round(segundos / paso))):
        reloj.avanzar(paso)
        res.append(f.update())
    return res


def _aislar_y_liberar(f, estado, reloj):
    """Una entrada al aislamiento y su salida (techo, luego techo - 3 por 3 s)."""
    ap.poner(estado, T_TECHO, TECHO)
    reloj.avanzar(0.5)
    r = f.update()
    if r != FaseResult.EN_CURSO:
        return r
    ap.poner(estado, T_OK, TECHO - 3.0)
    for _ in range(7):
        reloj.avanzar(0.5)
        r = f.update()
        if r != FaseResult.EN_CURSO:
            return r
    return r


# ── VCH E: actuador ─────────────────────────────────────────────────────────

def test_modo_chaqueta_recuperacion_conmuta_chaqueta_y_deja_camara_abierta(monkeypatch):
    f, estado, set_do, _ = _chaqueta(monkeypatch)
    assert f.controla_vapor_chaqueta is True
    assert f.update() == FaseResult.EN_CURSO
    assert f._en_recuperacion is True
    set_do.vapor_chaqueta_on.assert_called()
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


def test_modo_chaqueta_pwm_conmuta_solo_chaqueta(monkeypatch):
    # PWM_ACTIVO: T >= 134 + 0.3 + 0.3; banda dentro de [Psat(T)-2, Psat(T)+1]
    f, estado, set_do, reloj = _chaqueta(monkeypatch, temp=135.0, pres=ap.psat(135.0))
    f.update()
    for _ in range(12):
        reloj.avanzar(0.5)
        assert f.update() == FaseResult.EN_CURSO
    assert f._en_recuperacion is False
    set_do.vapor_chaqueta_on.assert_called()
    set_do.vapor_chaqueta_off.assert_called()          # el PWM cierra la chaqueta
    set_do.vapor_camara_off.assert_not_called()        # la cámara nunca se cierra
    assert set_do.vapor_camara_on.call_count >= 13     # ON en cada tick


def test_modo_camara_no_toca_la_chaqueta(monkeypatch):
    # D13: estado MagicMock -> modo cámara (comportamiento previo)
    f, estado, set_do, reloj = ap.fase(monkeypatch, t_est=T_EST)
    assert f.controla_vapor_chaqueta is False
    f.update()
    _ticks(f, reloj, 3)
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_not_called()


def test_inhibir_vapor_chaqueta_nunca_la_enciende(monkeypatch):
    f, estado, set_do, reloj = _chaqueta(monkeypatch)
    estado.inhibir_vapor_chaqueta = True
    f.update()
    _ticks(f, reloj, 2)
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_camara_on.assert_called()


def test_inhibir_solo_con_true_estricto(monkeypatch):
    from unittest.mock import MagicMock
    f, estado, set_do, _ = _chaqueta(monkeypatch)
    estado.inhibir_vapor_chaqueta = MagicMock()        # truthy pero no True
    f.update()
    set_do.vapor_chaqueta_on.assert_called()


# ── VCH-AIS: aislamiento ────────────────────────────────────────────────────

def test_aislamiento_entra_en_el_techo_y_fuerza_las_dos_off(monkeypatch):
    f, estado, set_do, reloj = _chaqueta(monkeypatch)
    f.update()
    set_do.reset_mock()
    ap.poner(estado, T_TECHO, TECHO)
    reloj.avanzar(0.5)
    assert f.update() == FaseResult.EN_CURSO
    assert isinstance(estado.aislamiento_camara, AislamientoCamara)
    assert estado.aislamiento_camara.aislado is True
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()
    set_do.vapor_chaqueta_on.assert_not_called()
    assert f._techo_recup_off is False                 # D12: sin el techo de C-08.3


def test_aislamiento_sale_con_histeresis_y_3_s(monkeypatch):
    f, estado, set_do, reloj = _chaqueta(monkeypatch)
    f.update()
    ap.poner(estado, T_TECHO, TECHO)
    reloj.avanzar(0.5)
    f.update()
    # por encima de techo - 3: no sale aunque pasen más de 3 s
    ap.poner(estado, T_OK, TECHO - 2.5)
    _ticks(f, reloj, 5)
    assert estado.aislamiento_camara.aislado is True
    # techo - 3 sostenido: sale a los 3 s
    ap.poner(estado, T_OK, TECHO - 3.0)
    reloj.avanzar(0.5)
    f.update()                                         # inicio del tramo bajo
    set_do.reset_mock()
    _ticks(f, reloj, 2.5)
    assert estado.aislamiento_camara.aislado is True
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_camara_on.assert_not_called()
    reloj.avanzar(0.5)                                 # 3.0 s bajo el umbral
    assert f.update() == FaseResult.EN_CURSO
    assert estado.aislamiento_camara.aislado is False
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_chaqueta_on.assert_called()           # RECUPERACION retoma la chaqueta


def test_histeresis_cierre_camara_del_programa(monkeypatch):
    f, estado, _, reloj = _chaqueta(monkeypatch, extras={"histeresis_cierre_camara": 5.0})
    f.update()
    ap.poner(estado, T_TECHO, TECHO)
    reloj.avanzar(0.5)
    f.update()
    ap.poner(estado, T_OK, TECHO - 4.0)
    _ticks(f, reloj, 5)
    assert estado.aislamiento_camara.aislado is True
    ap.poner(estado, T_OK, TECHO - 5.0)
    _ticks(f, reloj, 3.5)
    assert estado.aislamiento_camara.aislado is False


@pytest.mark.parametrize("valor, esperado", [(None, 3.0), (0.2, 1.0), (50, 10.0),
                                             (True, 3.0), (float("nan"), 3.0), (4, 4.0)])
def test_histeresis_cierre_camara_recortada(monkeypatch, valor, esperado):
    f, _, _, _ = _chaqueta(monkeypatch, extras={"histeresis_cierre_camara": valor})
    assert f._histeresis_cierre_kpa() == esperado


def test_aislamiento_compartido_se_reutiliza(monkeypatch):
    f, estado, _, reloj = _chaqueta(monkeypatch)
    ais = AislamientoCamara()
    estado.aislamiento_camara = ais
    ap.poner(estado, T_TECHO, TECHO)
    f.update()
    assert estado.aislamiento_camara is ais and ais.aislado is True


def test_aislamiento_sostenido_falla_cic15(monkeypatch):
    f, estado, set_do, reloj = _chaqueta(monkeypatch)
    f.update()
    ap.poner(estado, T_TECHO, TECHO)
    f.update()                                         # t = 0: entra
    res = _ticks(f, reloj, 180)                        # 180 s aislada: no falla aún
    assert FaseResult.FALLO not in res
    reloj.avanzar(0.5)                                 # > 180 s
    assert f.update() == FaseResult.FALLO
    codigo, valores = f.alarma_fallo
    assert codigo == "CIC-15"
    assert valores["minutos"] == "3" and valores["fase"] == "Esterilización"
    assert valores["maximo"] == pytest.approx(TECHO)
    assert getattr(estado.motivo_fallo, "codigo", None) == "ais_sostenida"
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_chaqueta_off.assert_called()


def test_aislamiento_recurrente_falla_cic16(monkeypatch):
    f, estado, set_do, reloj = _chaqueta(monkeypatch)
    f.update()
    for _ in range(5):
        assert _aislar_y_liberar(f, estado, reloj) == FaseResult.EN_CURSO
    ap.poner(estado, T_TECHO, TECHO)                   # sexta entrada en 15 min
    reloj.avanzar(0.5)
    assert f.update() == FaseResult.FALLO
    codigo, valores = f.alarma_fallo
    assert codigo == "CIC-16"
    assert valores == {"cantidad": 6, "minutos": "15", "fase": "Esterilización"}
    assert getattr(estado.motivo_fallo, "codigo", None) == "ais_recurrente"


def test_exposicion_y_f0_avanzan_durante_el_aislamiento(monkeypatch):
    f, estado, set_do, reloj = _chaqueta(monkeypatch, tiempo_min=1, f0_activo=True,
                                         f0_objetivo=1.0, f0_acumulado_inicial=5.0)
    f.cap = SimpleNamespace(has_liquid_sensor=True)
    f.update()                                         # fin en 60 s
    fin = f._timer_fin
    ap.poner(estado, T_TECHO, TECHO)
    res = _ticks(f, reloj, 59.5)
    assert estado.aislamiento_camara.aislado is True
    assert FaseResult.FALLO not in res and FaseResult.COMPLETADO not in res
    assert f._timer_fin == fin                         # el aislamiento no pausa
    set_do.reset_mock()
    reloj.avanzar(0.5)
    assert f.update() == FaseResult.COMPLETADO
    assert estado.f0_acumulado == 5.0                  # F0 no se toca
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_chaqueta_off.assert_called()


# ── Sin lectura (modo chaqueta) ─────────────────────────────────────────────

@pytest.mark.parametrize("sensor", ["temp", "pres"])
def test_sin_lectura_chaqueta_off_y_camara_abierta(monkeypatch, sensor):
    f, estado, set_do, reloj = _chaqueta(monkeypatch)
    f.update()
    set_do.reset_mock()
    if sensor == "temp":
        estado.sensores_temp["temp_camara"] = None
    else:
        estado.sensores_pres["pres_camara"] = None
    reloj.avanzar(0.5)
    assert f.update() == FaseResult.EN_CURSO
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


def test_sin_lectura_con_aislamiento_en_curso_no_reabre_la_camara(monkeypatch):
    f, estado, set_do, reloj = _chaqueta(monkeypatch)
    f.update()
    ap.poner(estado, T_TECHO, TECHO)
    reloj.avanzar(0.5)
    f.update()
    set_do.reset_mock()
    estado.sensores_pres["pres_camara"] = None
    _ticks(f, reloj, 5)
    assert estado.aislamiento_camara.aislado is True
    set_do.vapor_camara_on.assert_not_called()
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()


# ── COMPLETADO / FALLO ──────────────────────────────────────────────────────

def test_completado_cierra_las_dos(monkeypatch):
    f, estado, set_do, reloj = _chaqueta(monkeypatch, tiempo_min=1)
    f.update()
    res = _ticks(f, reloj, 60)
    assert res[-1] == FaseResult.COMPLETADO
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_chaqueta_off.assert_called()


def test_fallo_cierra_las_dos(monkeypatch):
    f, estado, set_do, reloj = _chaqueta(monkeypatch, temp=137.5, pres=ap.psat(136.0))
    f.update()
    reloj.avanzar(5.0)
    assert f.update() == FaseResult.FALLO
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_chaqueta_off.assert_called()


# ── P5 / D-14.5: tope de reinicios ──────────────────────────────────────────

T_REF = 121.0          # banda de la Referencia: [120.9, 124.0]
R_DENTRO = 121.5


def _fase_refs(monkeypatch, max_reinicios=None, sensores=None, refs=None, **kw):
    kw.setdefault("tiempo_min", 30)
    f, estado, set_do, reloj = ap.fase(
        monkeypatch, t_est=T_REF, sensores=sensores or ap.ASIG_REF, temp=R_DENTRO,
        pres=ap.psat(R_DENTRO), refs=refs or {"temp_ref": R_DENTRO}, **kw)
    if max_reinicios is not None:
        _con_params(f, max_reinicios_exposicion=max_reinicios)
    return f, estado, set_do, reloj


def _excursion(f, estado, reloj, sensor="temp_ref", fuera=20.0, dentro=15.0):
    """Excursión de `fuera` s (confirma a los 5 s) y retorno de `dentro` s
    (más que la ventana de 10 s del debounce). Devuelve el primer resultado
    distinto de EN_CURSO o EN_CURSO."""
    estado.sensores_temp[sensor] = 119.0
    for r in _ticks(f, reloj, fuera):
        if r != FaseResult.EN_CURSO:
            return r
    estado.sensores_temp[sensor] = R_DENTRO
    for r in _ticks(f, reloj, dentro):
        if r != FaseResult.EN_CURSO:
            return r
    return FaseResult.EN_CURSO


def test_p5_tope_por_defecto_3_reinicios(monkeypatch):
    f, estado, set_do, reloj = _fase_refs(monkeypatch)
    f.update()
    for n in range(1, 4):
        assert _excursion(f, estado, reloj) == FaseResult.EN_CURSO
        assert f.reinicios_exposicion == n
    assert _excursion(f, estado, reloj) == FaseResult.FALLO   # 4.ª confirmada
    codigo, valores = f.alarma_fallo
    assert codigo == "CIC-17"
    assert valores == {"sensor": "Referencia", "reinicios": 3, "maximo": 3}
    assert getattr(estado.motivo_fallo, "codigo", None) == "est_tope_reinicios"
    set_do.vapor_camara_off.assert_called()


def test_p5_con_cero_la_primera_excursion_confirmada_falla(monkeypatch):
    f, estado, _, reloj = _fase_refs(monkeypatch, max_reinicios=0)
    f.update()
    estado.sensores_temp["temp_ref"] = 119.0
    f.update()                                          # t = 0: sale
    res = _ticks(f, reloj, 4.5)
    assert FaseResult.FALLO not in res
    reloj.avanzar(0.5)
    assert f.update() == FaseResult.FALLO
    assert f.alarma_fallo[0] == "CIC-17"


def test_p5_cuenta_las_excursiones_de_cualquier_referencia(monkeypatch):
    sensores = {"temp_camara": "principal", "temp_2_camara": "referencia",
                "temp_ref": "referencia"}
    f, estado, _, reloj = _fase_refs(monkeypatch, max_reinicios=1, sensores=sensores,
                                     refs={"temp_ref": R_DENTRO, "temp_2_camara": R_DENTRO})
    f.update()
    assert _excursion(f, estado, reloj, sensor="temp_ref") == FaseResult.EN_CURSO
    assert f.reinicios_exposicion == 1
    assert _excursion(f, estado, reloj, sensor="temp_2_camara") == FaseResult.FALLO
    assert f.alarma_fallo[0] == "CIC-17"


@pytest.mark.parametrize("valor, esperado", [(None, 3), (-1, 0), (11, 10), (2.7, 2),
                                             (True, 3), (float("inf"), 3)])
def test_p5_max_reinicios_recortado(monkeypatch, valor, esperado):
    f, _, _, _ = _fase_refs(monkeypatch, max_reinicios=valor)
    assert f._max_reinicios() == esperado


# ── P6 / D-14.6: debounce acumulado ─────────────────────────────────────────

def test_p6_principal_oscilante_confirma(monkeypatch):
    # alterna 133.8 (fuera, < 134 - 0.1) y 134.0 cada 0.5 s: con 5 s
    # continuos nunca confirmaba; acumulado 5 s en 10 s, sí
    f, estado, _, reloj = ap.fase(monkeypatch, t_est=T_EST, tiempo_min=30)
    resultado = f.update()
    for i in range(40):
        ap.poner(estado, 133.8 if i % 2 == 0 else 134.0, ap.psat(134.0))
        reloj.avanzar(0.5)
        resultado = f.update()
        if resultado != FaseResult.EN_CURSO:
            break
    assert resultado == FaseResult.FALLO
    assert getattr(estado.motivo_fallo, "codigo", None) == "est_temp_baja"
    assert reloj.t - 1000.0 <= 11.0


def test_p6_saturacion_oscilante_confirma(monkeypatch):
    f, estado, _, reloj = ap.fase(monkeypatch, t_est=T_EST, tiempo_min=30,
                                  temp=134.5, pres=ap.psat(134.5))
    f.update()
    resultado = FaseResult.EN_CURSO
    for i in range(40):
        p = ap.psat(137.0) if i % 2 == 0 else ap.psat(134.5)     # dT +2.5 / 0
        ap.poner(estado, 134.5, p)
        reloj.avanzar(0.5)
        resultado = f.update()
        if resultado != FaseResult.EN_CURSO:
            break
    assert resultado == FaseResult.FALLO
    assert f.alarma_fallo[0] == "CIC-12"


def test_p6_referencia_oscilante_confirma_la_excursion(monkeypatch):
    f, estado, _, reloj = _fase_refs(monkeypatch)
    f.update()
    detenida = False
    for i in range(40):
        estado.sensores_temp["temp_ref"] = 119.0 if i % 2 == 0 else R_DENTRO
        reloj.avanzar(0.5)
        assert f.update() in (FaseResult.EN_CURSO, FaseResult.FALLO)
        if f.exposicion_detenida:
            detenida = True
            break
    assert detenida


def test_p6_ruido_por_debajo_del_umbral_no_confirma(monkeypatch):
    # 1 tick fuera de cada 4 (25 %): nunca suma 5 s en 10 s
    f, estado, _, reloj = ap.fase(monkeypatch, t_est=T_EST, tiempo_min=30)
    f.update()
    for i in range(80):
        ap.poner(estado, 133.8 if i % 4 == 0 else 134.0, ap.psat(134.0))
        reloj.avanzar(0.5)
        assert f.update() == FaseResult.EN_CURSO


def test_p6_falla_en_conteo_bloquea_completar(monkeypatch):
    f, estado, _, reloj = ap.fase(monkeypatch, t_est=T_EST, tiempo_min=1)
    f.update()
    _ticks(f, reloj, 59.5)
    ap.poner(estado, 133.8, ap.psat(134.0))             # condición activa al final
    reloj.avanzar(0.5)
    assert f.update() == FaseResult.EN_CURSO
    assert f._falla_en_conteo() is True
    ap.poner(estado, 134.0, ap.psat(134.0))
    reloj.avanzar(0.5)
    assert f.update() == FaseResult.COMPLETADO


# ── SAF-05 (P8) ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("modo", ["camara", "chaqueta"])
def test_saf05_hueco_desde_la_ultima_lectura_valida(monkeypatch, modo):
    if modo == "chaqueta":
        f, estado, _, reloj = _chaqueta(monkeypatch)
    else:
        f, estado, _, reloj = ap.fase(monkeypatch, t_est=T_EST, tiempo_min=30)
    f.update()                                          # t = 0
    reloj.avanzar(1.0)
    f.update()                                          # t = 1: última válida
    fin = f._timer_fin
    estado.sensores_pres["pres_camara"] = None
    reloj.avanzar(2.0)
    f.update()                                          # t = 3: primer tick sin dato
    reloj.avanzar(2.0)
    f.update()                                          # t = 5
    estado.sensores_pres["pres_camara"] = P_OK
    reloj.avanzar(1.0)
    f.update()                                          # t = 6: vuelve
    assert f.sin_lectura_s == pytest.approx(5.0)        # antes: 3 (desde t = 3)
    assert f._timer_fin == pytest.approx(fin + 5.0)
    assert f.pausa_total_s == 0.0


def test_saf05_sin_lectura_desde_el_primer_tick(monkeypatch):
    f, estado, _, reloj = ap.fase(monkeypatch, t_est=T_EST, tiempo_min=30)
    estado.sensores_temp["temp_camara"] = None
    f.update()                                          # t = 0, nunca hubo lectura
    fin = f._timer_fin
    reloj.avanzar(4.0)
    estado.sensores_temp["temp_camara"] = T_OK
    f.update()
    assert f.sin_lectura_s == pytest.approx(4.0)
    assert f._timer_fin == pytest.approx(fin + 4.0)


# ── P8 / D-14.8 ─────────────────────────────────────────────────────────────

def test_p8_excursion_confirmada_que_pierde_la_lectura(monkeypatch):
    f, estado, _, reloj = _fase_refs(monkeypatch, timeout_exc=1)
    f.update()
    estado.sensores_temp["temp_ref"] = 119.0
    f.update()                                          # t = 0: inicio
    _ticks(f, reloj, 6)                                 # confirmada
    assert f.exposicion_detenida is True
    estado.sensores_temp["temp_ref"] = None             # pierde la lectura
    res = _ticks(f, reloj, 53.5)                        # t = 59.5
    assert FaseResult.FALLO not in res
    assert f.exposicion_detenida is True
    assert estado.exposicion_restante_s == pytest.approx(30 * 60)
    reloj.avanzar(0.5)                                  # t = 60: timeout 1 min
    assert f.update() == FaseResult.FALLO
    assert f.alarma_fallo[0] == "CIC-14"


def test_p8_excursion_sin_confirmar_que_pierde_la_lectura_se_descarta(monkeypatch):
    f, estado, _, reloj = _fase_refs(monkeypatch)
    f.update()
    estado.sensores_temp["temp_ref"] = 119.0
    _ticks(f, reloj, 4.0)
    estado.sensores_temp["temp_ref"] = None
    _ticks(f, reloj, 2.0)
    assert f._ref_fuera == {}
    estado.sensores_temp["temp_ref"] = 119.0            # vuelve fuera: conteo nuevo
    _ticks(f, reloj, 4.5)
    assert f.exposicion_detenida is False
    _ticks(f, reloj, 1.0)
    assert f.exposicion_detenida is True


def test_constantes_p6():
    assert est._DEBOUNCE_FALLA_S == 5.0
    assert est._DEBOUNCE_VENTANA_S == 10.0
