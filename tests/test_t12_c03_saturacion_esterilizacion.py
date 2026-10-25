# tests/test_t12_c03_saturacion_esterilizacion.py
#
# Tanda 12, C-03: falla de saturación durante la exposición (solo sólidos).
# dT = Tsat(P) - T_principal; > +2 K sostenido 5 s -> CIC-12 (aire / gases no
# condensables); < -2 K sostenido 5 s -> CIC-13 (vapor sobrecalentado o falla
# de la sonda). Reloj monotonic simulado.

from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.alarms.catalogo import CATALOGO
from tests.helpers import t12_e12_apoyo as ap

T_EST = 134.0


def _aire(monkeypatch, **kw):
    # T dentro de la banda (134.5) y P de saturación de 137.0: dT = +2.5 K
    return ap.fase(monkeypatch, t_est=T_EST, temp=134.5, pres=ap.psat(137.0), **kw)


def test_aire_4_9_s_no_falla_5_s_falla_con_cic12(monkeypatch):
    f, estado, set_do, reloj = _aire(monkeypatch)
    assert f.update() == FaseResult.EN_CURSO          # t = 0: empieza el conteo
    reloj.avanzar(4.9)
    assert f.update() == FaseResult.EN_CURSO
    reloj.avanzar(0.1)
    assert f.update() == FaseResult.FALLO
    codigo, valores = f.alarma_fallo
    assert codigo == "CIC-12"
    assert round(valores["dt"], 1) == 2.5
    assert round(valores["tsat"], 1) == 137.0
    assert valores["temp"] == 134.5
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()
    assert getattr(estado.motivo_fallo, "codigo", None) == "est_aire"
    CATALOGO["CIC-12"].renderizar(valores)            # la plantilla tiene sus campos


def test_sobrecalentado_5_s_falla_con_cic13(monkeypatch):
    # T = 136.5 (bajo el límite alto 137) y P de saturación de 134.0: dT = -2.5 K
    f, estado, _, reloj = ap.fase(monkeypatch, t_est=T_EST, temp=136.5, pres=ap.psat(134.0))
    f.update()
    reloj.avanzar(4.9)
    assert f.update() == FaseResult.EN_CURSO
    reloj.avanzar(0.1)
    assert f.update() == FaseResult.FALLO
    codigo, valores = f.alarma_fallo
    assert codigo == "CIC-13"
    assert round(valores["dt"], 1) == 2.5             # magnitud del sobrecalentamiento
    assert getattr(estado.motivo_fallo, "codigo", None) == "est_sobrecalentado"
    CATALOGO["CIC-13"].renderizar(valores)


def test_una_lectura_dentro_reinicia_el_conteo(monkeypatch):
    f, estado, _, reloj = _aire(monkeypatch)
    f.update()
    reloj.avanzar(4.0)
    assert f.update() == FaseResult.EN_CURSO
    ap.poner(estado, temp=134.5, pres=ap.psat(134.5))  # dT = 0
    reloj.avanzar(0.5)
    assert f.update() == FaseResult.EN_CURSO
    ap.poner(estado, temp=134.5, pres=ap.psat(137.0))  # vuelve a +2.5 K
    for _ in range(10):
        reloj.avanzar(0.5)
        assert f.update() == FaseResult.EN_CURSO       # 4.5 s desde que volvió
    reloj.avanzar(0.5)
    assert f.update() == FaseResult.FALLO              # 5.0 s continuos


def test_dentro_de_2_k_no_falla(monkeypatch):
    f, _, _, reloj = ap.fase(monkeypatch, t_est=T_EST, temp=134.5, pres=ap.psat(136.4))
    for _ in range(30):
        assert f.update() == FaseResult.EN_CURSO
        reloj.avanzar(1.0)


def test_con_liquido_no_aplica(monkeypatch):
    f, _, _, reloj = _aire(monkeypatch, tipo_carga="liquido")
    for _ in range(30):
        assert f.update() == FaseResult.EN_CURSO
        reloj.avanzar(1.0)
    assert f.alarma_fallo is None


def test_solido_explicito_aplica(monkeypatch):
    f, _, _, reloj = _aire(monkeypatch, tipo_carga="solido")
    f.update()
    reloj.avanzar(5.0)
    assert f.update() == FaseResult.FALLO
    assert f.alarma_fallo[0] == "CIC-12"


def test_ciclo_state_registra_la_alarma_propia(monkeypatch):
    """Mismo mecanismo que CIC-11: CicloState registra alarma_fallo."""
    from unittest.mock import MagicMock
    from autoclave.state_machine.states.ciclo import CicloState
    from autoclave.state_machine.alarms.alarm_manager import AlarmManager
    estado = MagicMock()
    estado.motivo_fallo = ""
    am = AlarmManager()
    ciclo = CicloState(estado, MagicMock(), MagicMock(), MagicMock(), am)
    for codigo, valores in (("CIC-12", {"tsat": 137.0, "temp": 134.5, "dt": 2.5}),
                            ("CIC-13", {"tsat": 134.0, "temp": 136.5, "dt": 2.5}),
                            ("CIC-14", {"sensor": "Referencia", "minutos": "5"})):
        fase = MagicMock()
        fase.alarma_fallo = (codigo, valores)
        ciclo._registrar_fallo_de_fase("ESTERILIZACION", fase)
        assert estado.codigo_fallo == codigo
        assert codigo in [i.codigo for i in am.activas()]
